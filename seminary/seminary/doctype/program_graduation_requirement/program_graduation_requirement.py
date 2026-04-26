# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ProgramGraduationRequirement(Document):
    def validate(self):
        self._validate_date_window()
        self._validate_no_active_overlap()
        self._validate_linked_doc_status_values()

    def _validate_date_window(self):
        if (
            self.active_from
            and self.active_until
            and self.active_until < self.active_from
        ):
            frappe.throw(_("Active Until cannot be earlier than Active From."))

    def _validate_no_active_overlap(self):
        if not self.active or not self.program_name:
            return

        filters = {
            "program_name": self.program_name,
            "active": 1,
            "name": ("!=", self.name or ""),
        }
        others = frappe.get_all(
            "Program Graduation Requirement",
            filters=filters,
            fields=["name", "active_from", "active_until"],
        )

        for other in others:
            if _windows_overlap(
                self.active_from,
                self.active_until,
                other.active_from,
                other.active_until,
            ):
                frappe.throw(
                    _(
                        "Active date window overlaps with {0}. "
                        "Two policies for the same program cannot be active simultaneously."
                    ).format(other.name)
                )

    def _validate_linked_doc_status_values(self):
        """Catch typos in linked_doc_status at policy authoring time."""
        for row in self.pgr_items or []:
            if row.activation_mode != "On Document Status":
                continue
            if not row.on_document or not row.linked_doc_status:
                continue
            if not _status_value_exists(row.on_document, row.linked_doc_status):
                frappe.throw(
                    _(
                        "Row {0}: '{1}' is not a valid workflow_state or status value on {2}."
                    ).format(row.idx, row.linked_doc_status, row.on_document)
                )


def _windows_overlap(a_start, a_end, b_start, b_end):
    """Closed-interval overlap with open ends (None means open-ended)."""
    if a_end and b_start and a_end < b_start:
        return False
    if b_end and a_start and b_end < a_start:
        return False
    return True


def _status_value_exists(doctype, value):
    """Check value exists as a Workflow State or as a Select option on workflow_state/status."""
    workflow_name = frappe.db.get_value(
        "Workflow", {"document_type": doctype, "is_active": 1}, "name"
    )
    if workflow_name:
        states = frappe.get_all(
            "Workflow Document State",
            filters={"parent": workflow_name},
            pluck="state",
        )
        if value in states:
            return True

    meta = frappe.get_meta(doctype)
    for fieldname in ("workflow_state", "status"):
        field = meta.get_field(fieldname)
        if field and field.fieldtype == "Select" and field.options:
            if value in [
                opt.strip() for opt in field.options.split("\n") if opt.strip()
            ]:
                return True

    return False
