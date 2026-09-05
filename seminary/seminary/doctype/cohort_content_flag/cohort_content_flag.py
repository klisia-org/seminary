# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CohortContentFlag(Document):
    def validate(self):
        if self.target_doctype not in ("Cohort Post", "Cohort Post Comment"):
            frappe.throw(_("Only posts and replies can be flagged."))
        if not self.cohort:
            self.cohort = self._resolve_cohort()

    def _resolve_cohort(self):
        if self.target_doctype == "Cohort Post":
            return frappe.db.get_value("Cohort Post", self.target_name, "cohort")
        return frappe.db.get_value("Cohort Post Comment", self.target_name, "cohort")
