# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Topic Choice (decisions/120 §3): the topic a student holds on individual work."""

import frappe
from frappe import _
from frappe.model.document import Document


class TopicChoice(Document):
	def validate(self):
		t = frappe.db.get_value(
			"Activity Topic", self.topic, ["course_schedule", "activity_doctype", "activity"], as_dict=True
		)
		if not t or (t.course_schedule, t.activity_doctype, t.activity) != (
			self.course_schedule,
			self.activity_doctype,
			self.activity,
		):
			frappe.throw(_("This topic belongs to another activity."))
		if frappe.db.exists(
			"Topic Choice",
			{
				"course_schedule": self.course_schedule,
				"activity": self.activity,
				"student": self.student,
				"name": ["!=", self.name],
			},
		):
			frappe.throw(_("This student already has a topic on this activity."))
