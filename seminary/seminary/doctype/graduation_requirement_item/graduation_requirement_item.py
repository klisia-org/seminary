# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class GraduationRequirementItem(Document):
    def before_cancel(self):
        """Block cancellation while any non-cancelled program policy or
        student snapshot still references this Library row.

        Forces an explicit substitution flow: registrar must amend (creates
        Foo-1), repoint every `Program Grad Req Items` row to the new name,
        then cancel the old Library entry. Existing student snapshots that
        already reference the old name keep resolving by name (snapshot
        semantics, ADR 012).
        """
        program_refs = frappe.get_all(
            "Program Grad Req Items",
            filters={"grad_requirement_item": self.name, "docstatus": ("!=", 2)},
            fields=["parent"],
            limit=5,
        )
        if program_refs:
            sample = ", ".join({r.parent for r in program_refs})
            frappe.throw(
                _(
                    "Cannot cancel Graduation Requirement Item {0}: still referenced by "
                    "Program Graduation Requirement(s): {1}. Substitute the reference "
                    "before cancelling."
                ).format(self.name, sample)
            )

        student_refs = frappe.get_all(
            "Student Graduation Requirement",
            filters={"grad_requirement_item": self.name, "docstatus": ("!=", 2)},
            fields=["parent"],
            limit=5,
        )
        if student_refs:
            sample = ", ".join({r.parent for r in student_refs})
            frappe.throw(
                _(
                    "Cannot cancel Graduation Requirement Item {0}: still snapshotted on "
                    "active Program Enrollment(s): {1}. Resnapshot or close those "
                    "enrollments first."
                ).format(self.name, sample)
            )
