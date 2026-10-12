# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from seminary.seminary.discipleship import reading_plans


class CohortReadingPlan(Document):
    def validate(self):
        reading_plans.validate_run(self)

    def on_trash(self):
        reading_plans.delete_run_progress(self)
