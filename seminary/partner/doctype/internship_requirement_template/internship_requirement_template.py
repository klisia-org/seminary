# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class InternshipRequirementTemplate(Document):
    def validate(self):
        if not (self.student_submits or self.seminary_submits or self.partner_submits):
            frappe.throw(
                _(
                    "At least one party (student, seminary, or partner) must submit this requirement."
                )
            )
