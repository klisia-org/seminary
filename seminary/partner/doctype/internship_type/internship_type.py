# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

SUBMITTABLE_LOG = "Submittable Log"
INHERIT_EVAL = "Inherited from Course"


class InternshipType(Document):
    def validate(self):
        self._validate_evaluation_model()
        self._validate_hour_log_template()
        self._validate_multi_site()

    def _validate_evaluation_model(self):
        """Evaluation follows the course when one is set; otherwise the type must
        declare its own Pass/Fail or Graded model (ADR 054 §5)."""
        if self.course:
            if self.evaluation_model != INHERIT_EVAL:
                frappe.throw(
                    _(
                        "A backing course governs evaluation, so the evaluation model "
                        'must be "Inherited from Course". Clear the course to grade this '
                        "type as Pass/Fail or Graded."
                    )
                )
        else:
            if self.evaluation_model == INHERIT_EVAL:
                frappe.throw(
                    _(
                        'Choose a backing course for "Inherited from Course", or set the '
                        "evaluation model to Pass/Fail or Graded."
                    )
                )

    def _validate_hour_log_template(self):
        """Config QA (ADR 054 §8): a Submittable Log type needs exactly one template
        marked as the hour log. We warn while no templates exist yet (the type is
        usually saved before its templates), and hard-block once they do."""
        templates = frappe.get_all(
            "Internship Requirement Template",
            filters={"internship_type": self.name},
            fields=["name", "is_hour_log"],
        )
        hour_logs = [t for t in templates if t.is_hour_log]

        if self.hours_tracking == SUBMITTABLE_LOG:
            if templates and not hour_logs:
                frappe.throw(
                    _(
                        "A Submittable Log internship needs one requirement template "
                        'marked "Is Hour Log". Add or flag one for this type.'
                    )
                )
            if not templates:
                frappe.msgprint(
                    _(
                        "Remember to add a requirement template marked "
                        '"Is Hour Log" — a Submittable Log internship needs one.'
                    ),
                    indicator="orange",
                    alert=True,
                )
        elif hour_logs:
            frappe.msgprint(
                _(
                    '"Is Hour Log" only applies to Submittable Log internships; it is '
                    "ignored for this type's tracking mode."
                ),
                indicator="orange",
                alert=True,
            )

    def _validate_multi_site(self):
        if self.allow_multi_site and (self.max_sites or 0) < 1:
            frappe.throw(_("Set Max Sites to at least 1 when multi-site is allowed."))


def claim_advisor_slot(internship_type):
    """Pick the advisor with the most remaining capacity, increment their count,
    and return the instructor — or None when the type opts out or the pool is full.
    Used by Internship Application on acceptance (ADR 054 §7)."""
    doc = frappe.get_doc("Internship Type", internship_type)
    if not doc.auto_assign_faculty or not doc.advisor_slots:
        return None

    def remaining(slot):
        # max_students 0 means unlimited — treat as effectively infinite capacity.
        cap = slot.max_students or 0
        return float("inf") if cap == 0 else cap - (slot.current_students or 0)

    candidates = [s for s in doc.advisor_slots if remaining(s) > 0]
    if not candidates:
        return None

    chosen = max(candidates, key=remaining)
    chosen.current_students = (chosen.current_students or 0) + 1
    doc.save(ignore_permissions=True)
    return chosen.instructor


def release_advisor_slot(internship_type, instructor):
    """Decrement an advisor's assigned count when an application is withdrawn or
    its advisor changes."""
    if not internship_type or not instructor:
        return
    doc = frappe.get_doc("Internship Type", internship_type)
    for slot in doc.advisor_slots:
        if slot.instructor == instructor and (slot.current_students or 0) > 0:
            slot.current_students -= 1
            doc.save(ignore_permissions=True)
            break
