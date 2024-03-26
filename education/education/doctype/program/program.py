# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document


class Program(Document):
	def validate(self):
		self.validate_courses_pgmtrack()
		
	def get_course_list(self):
		program_course_list = self.courses
		course_list = [
			frappe.get_doc("Course", program_course.course)
			for program_course in program_course_list
		]
		return course_list

	def validate_courses_pgmtrack(self):
		program_course_list = self.courses
		for program_course in program_course_list:
			if self.pgm_courses_track not in program_course.course:
				frappe.throw(
					"Course {0} is in the Program Track but not in Courses for this Program".format(program_course.course)
				)