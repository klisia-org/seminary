# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Activity Topic (decisions/120 §3): one section's topic on one activity."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class ActivityTopic(Document):
	def validate(self):
		from seminary.seminary import group_work

		group_work._check_doctype(self.activity_doctype)
		self.capacity = max(1, cint(self.capacity))

	def on_trash(self):
		if frappe.db.exists("Topic Choice", {"topic": self.name}) or frappe.db.exists(
			"Activity Group", {"topic": self.name}
		):
			frappe.throw(_("This topic is held, so it cannot be deleted."))
