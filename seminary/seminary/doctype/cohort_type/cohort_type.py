# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CohortType(Document):
    def validate(self):
        self._validate_course_in_program()
        if self.graduates_to == self.name:
            frappe.throw(_("A Cohort Type cannot graduate into itself."))

    def _validate_course_in_program(self):
        """If both a program and a backing course are set, the course must be one
        of that program's courses — the same binding the culminating-project types
        rely on so auto-enroll targets a course the member can actually take."""
        if not (self.program and self.course):
            return
        in_program = frappe.db.exists(
            "Program Course", {"parent": self.program, "course": self.course}
        )
        if not in_program:
            frappe.throw(
                _("Course {0} is not part of Program {1}.").format(
                    frappe.bold(self.course), frappe.bold(self.program)
                )
            )
