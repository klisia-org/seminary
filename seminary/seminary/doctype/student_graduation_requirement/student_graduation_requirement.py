# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class StudentGraduationRequirement(Document):
    def validate(self):
        self._stamp_status_transitions()

    def _stamp_status_transitions(self):
        if self.waived and not self.waived_by:
            self.waived_by = frappe.session.user
            self.waived_on = now_datetime()
            self.status = "Waived"
        if not self.waived and self.status == "Waived":
            self.status = "Not Started"
            self.waived_by = None
            self.waived_on = None

        if self.status == "Fulfilled" and not self.fulfilled_on:
            self.fulfilled_on = frappe.utils.today()

        if (
            self.requirement_type == "Manual Verification"
            and self.staff_evidence_attachment
            and self.status not in ("Fulfilled", "Waived", "Failed")
            and not self.verified_by
        ):
            self.verified_by = frappe.session.user
            self.verified_on = now_datetime()
            self.status = "Fulfilled"

        if (
            self.requirement_type == "Manual Verification"
            and self.student_evidence_attachment
            and self.status == "Not Started"
        ):
            self.status = "Submitted"
