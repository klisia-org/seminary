# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FeeCategory(Document):
	def validate(self):
		self.validate_tuition()
		self.validate_audit()

	def validate_tuition(self):
		if self.fc_event !="Course Enrollment":
			if self.is_credit == 1:
				frappe.throw("Credits are only allowed for events of type Course Enrollment")
	
	def validate_audit(self):
		if self.fc_event !="Course Enrollment":
			if self.is_audit == 1:
				frappe.throw("Audit is only allowed for events of type Course Enrollment")
		if self.is_credit == 1:
			if self.is_audit == 1:
				frappe.throw("Audit and Credits are mutually exclusive")


