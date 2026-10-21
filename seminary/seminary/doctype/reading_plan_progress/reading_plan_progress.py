# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ReadingPlanProgress(Document):
    def validate(self):
        # One mark per member and step; `mark_step` relies on it.
        if frappe.db.exists(
            "Reading Plan Progress",
            {
                "cohort_reading_plan": self.cohort_reading_plan,
                "person": self.person,
                "step": self.step,
                "name": ["!=", self.name],
            },
        ):
            frappe.throw(_("This step is already marked as read."))
