# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from seminary.seminary.discipleship import reading_plans


class ReadingPlan(Document):
    def validate(self):
        reading_plans.validate_plan(self)

    def on_update(self):
        reading_plans.adopt_step_attachments(self)

    def on_trash(self):
        reading_plans.guard_plan_delete(self)
