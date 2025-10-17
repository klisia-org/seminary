# Copyright (c) 2025, Klisia, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document



class DiscussionSubmission(Document):
	def validate(self):
		self.populate()


	def populate(self):
		if self.student is None and self.member:
			self.student = frappe.db.get_value("Student", {"user": self.member})
		if self.student_name is None and self.student:
			self.student_name = frappe.db.get_value("Student", self.student, "student_name")
		self.course_assess = frappe.db.get_value("Scheduled Course Assess Criteria", {'discussion' : self.disc_activity, 'parent' : self.course}, "name")
		self.extra_credit = frappe.db.get_value("Scheduled Course Assess Criteria", {'discussion' : self.disc_activity, 'parent' : self.course}, "extracredit_scac")

