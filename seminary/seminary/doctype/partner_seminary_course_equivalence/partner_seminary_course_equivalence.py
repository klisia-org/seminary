import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PartnerSeminaryCourseEquivalence(Document):
    def validate(self):
        self._validate_partner_is_selectable()
        self._validate_mapping_type_consistent_with_partner()
        self._validate_policy_override_submitted()
        self._validate_no_conflicting_submitted_equivalence()

    def _validate_partner_is_selectable(self):
        """Draft equivalences cannot target Inactive/Archived partners; already-submitted records
        are unaffected so existing transcripts never break when a partnership ends."""
        if self.docstatus == 1:
            return
        if not self.partner_seminary:
            return
        status = frappe.db.get_value(
            "Partner Seminary", self.partner_seminary, "status"
        )
        if status in ("Inactive", "Archived"):
            frappe.throw(
                _(
                    "Partner Seminary '{0}' has status '{1}' and cannot be referenced by new Course Equivalences."
                ).format(self.partner_seminary, status)
            )

    def _validate_mapping_type_consistent_with_partner(self):
        if not self.partner_seminary:
            return
        is_legacy = frappe.db.get_value(
            "Partner Seminary", self.partner_seminary, "is_internal_legacy"
        )
        if is_legacy and self.mapping_type != "legacy_identity":
            frappe.throw(
                _(
                    "Partner Seminary '{0}' is an Internal Legacy record; mapping_type must be 'legacy_identity'."
                ).format(self.partner_seminary)
            )
        if not is_legacy and self.mapping_type == "legacy_identity":
            frappe.throw(
                _(
                    "'legacy_identity' mapping_type is reserved for Internal Legacy partners. "
                    "Use 'equivalence' for external partners."
                )
            )

    def _validate_policy_override_submitted(self):
        if not self.conversion_policy_override:
            return
        docstatus = frappe.db.get_value(
            "Grade Conversion Policy",
            self.conversion_policy_override,
            "docstatus",
        )
        if docstatus != 1:
            frappe.throw(
                _("Conversion Policy Override '{0}' must be submitted.").format(
                    self.conversion_policy_override
                )
            )

    def _validate_no_conflicting_submitted_equivalence(self):
        """Prevent two simultaneously-active submitted equivalences for the same mapping.
        An amended_from chain is fine because the predecessor is cancelled (docstatus=2).
        """
        if self.docstatus != 1:
            return
        existing = frappe.db.get_all(
            "Partner Seminary Course Equivalence",
            filters={
                "name": ("!=", self.name),
                "partner_seminary": self.partner_seminary,
                "source_course_code": self.source_course_code,
                "internal_course": self.internal_course,
                "docstatus": 1,
            },
            pluck="name",
            limit=1,
        )
        if existing:
            frappe.throw(
                _(
                    "An active submitted equivalence already exists for {0} \u2192 {1}: '{2}'. "
                    "Cancel and amend the existing record instead of creating a parallel one."
                ).format(self.source_course_code, self.internal_course, existing[0])
            )


@frappe.whitelist()
def create_legacy_integration(partner_seminary):
    """Bulk-create submitted legacy_identity equivalences for every Course in the catalog
    against the given Partner Seminary. Intended for System Manager-driven migrations where
    course names were not changed between the legacy system and SeminaryERP. Idempotent:
    courses already mapped are skipped."""
    frappe.only_for("System Manager")

    partner = frappe.get_doc("Partner Seminary", partner_seminary)
    if not partner.is_internal_legacy:
        frappe.throw(
            _("Partner Seminary '{0}' is not flagged as Internal Legacy.").format(
                partner_seminary
            )
        )

    courses = frappe.get_all(
        "Course",
        fields=["name", "coursecode", "course_credits"],
    )

    created = 0
    skipped = 0
    for course in courses:
        source_code = course.coursecode or course.name
        existing = frappe.db.get_value(
            "Partner Seminary Course Equivalence",
            {
                "partner_seminary": partner_seminary,
                "source_course_code": source_code,
                "internal_course": course.name,
                "docstatus": ("!=", 2),
            },
            "name",
        )
        if existing:
            skipped += 1
            continue

        doc = frappe.new_doc("Partner Seminary Course Equivalence")
        doc.partner_seminary = partner_seminary
        doc.source_course_code = source_code
        doc.source_course_name = course.name
        doc.internal_course = course.name
        doc.source_credit_value = flt(course.course_credits)
        doc.mapping_type = "legacy_identity"
        doc.insert()
        doc.submit()
        created += 1

    frappe.db.commit()
    return {"created": created, "skipped": skipped}
