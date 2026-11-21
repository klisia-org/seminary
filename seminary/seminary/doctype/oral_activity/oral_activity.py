# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document


class OralActivity(Document):
    def validate(self):
        from seminary.seminary import oral

        try:
            steps = json.loads(self.oral_steps or "[]")
        except ValueError:
            frappe.throw(_("Processing Steps must be a list."))
        self.oral_steps = json.dumps([s for s in oral.PIPELINE if s in steps])
        if self.mode != "Conversation":
            self.group_size = 0
