# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class DisciplinaryIncident(Document):
    def validate(self):
        self.set_student_from_pe()
        self.set_occurrence_number()
        self.validate_assessment_required()
        self.set_defaults()

    def set_defaults(self):
        if not self.status:
            self.status = "Reported"
        if not self.reported_by:
            self.reported_by = frappe.session.user

    def set_student_from_pe(self):
        if not self.student and self.pe:
            self.student = frappe.db.get_value("Program Enrollment", self.pe, "student")

    def set_occurrence_number(self):
        if self.occurrence_number:
            return
        from seminary.seminary.disciplinary import compute_occurrence_number

        self.occurrence_number = compute_occurrence_number(
            self.student, self.reason, exclude_name=self.name
        )

    def validate_assessment_required(self):
        requires_course = (
            frappe.db.get_value("Disciplinary Reason", self.reason, "requires_course")
            if self.reason
            else 0
        )
        if requires_course and not (self.cei and self.assessment):
            frappe.throw(
                _(
                    "This reason requires the course enrollment and the assessment involved."
                )
            )
