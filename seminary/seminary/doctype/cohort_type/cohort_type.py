# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CohortType(Document):
    def validate(self):
        if self.graduates_to == self.name:
            frappe.throw(_("A Cohort Type cannot graduate into itself."))
