# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from seminary.seminary import group_work, peer_reviews, rubrics


class OralActivitySubmission(Document):
	def validate(self):
		from seminary.seminary.utils import stamp_first_grading

		stamp_first_grading(self)
		self.populate()
		group_work.stamp(self)
		rubrics.apply_grade(self)
		# The gradebook card reads `percentage`; the grade is entered as one.
		if self.grade is not None:
			self.percentage = self.grade
		# Review work is part of the grade (decisions/120 §7).
		peer_reviews.blend(self)

	def populate(self):
		if not self.student and self.member:
			self.student = frappe.db.get_value("Student", {"user": self.member})
		if self.student and not self.member_name:
			self.member_name = frappe.db.get_value("Student", self.student, "student_name")
		row = frappe.db.get_value(
			"Scheduled Course Assess Criteria",
			{"oral": self.oral_activity, "parent": self.course},
			["name", "extracredit_scac"],
			as_dict=True,
		)
		if row:
			self.course_assess = row.name
			self.extra_credit = row.extracredit_scac
