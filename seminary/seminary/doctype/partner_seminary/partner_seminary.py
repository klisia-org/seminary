import frappe
from frappe import _
from frappe.model.document import Document


class PartnerSeminary(Document):
    def validate(self):
        self._lock_is_internal_legacy()
        self._validate_defaults_submitted()

    def on_trash(self):
        if self.is_internal_legacy:
            frappe.throw(
                _(
                    "Cannot delete a Partner Seminary flagged as Internal Legacy. "
                    "Set status to Archived instead."
                )
            )
        self._block_delete_if_referenced()

    def _lock_is_internal_legacy(self):
        if self.is_new():
            return
        previous = frappe.db.get_value(
            "Partner Seminary", self.name, "is_internal_legacy"
        )
        if previous is None:
            return
        if bool(self.is_internal_legacy) != bool(previous):
            frappe.throw(_("'Is Internal Legacy' cannot be changed after creation."))

    def _validate_defaults_submitted(self):
        if self.default_grading_scale:
            docstatus = frappe.db.get_value(
                "Grading Scale", self.default_grading_scale, "docstatus"
            )
            if docstatus != 1:
                frappe.throw(
                    _("Default Grading Scale '{0}' must be submitted.").format(
                        self.default_grading_scale
                    )
                )
        if self.default_conversion_policy:
            docstatus = frappe.db.get_value(
                "Grade Conversion Policy",
                self.default_conversion_policy,
                "docstatus",
            )
            if docstatus != 1:
                frappe.throw(
                    _("Default Conversion Policy '{0}' must be submitted.").format(
                        self.default_conversion_policy
                    )
                )

    def _block_delete_if_referenced(self):
        references = frappe.db.count(
            "Partner Seminary Course Equivalence",
            filters={"partner_seminary": self.name},
        )
        if references:
            frappe.throw(
                _(
                    "Cannot delete Partner Seminary '{0}': {1} Course Equivalence record(s) reference it. "
                    "Set status to Archived instead."
                ).format(self.name, references)
            )
        transcript_refs = frappe.db.count(
            "Program Enrollment Course",
            filters={"partner_seminary": self.name},
        )
        if transcript_refs:
            frappe.throw(
                _(
                    "Cannot delete Partner Seminary '{0}': {1} transcript row(s) reference it. "
                    "Set status to Archived instead."
                ).format(self.name, transcript_refs)
            )
