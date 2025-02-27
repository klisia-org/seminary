# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe.website.website_generator import WebsiteGenerator


class Program(WebsiteGenerator):
	#def validate(self):
		#self.validate_courses_pgmtrack()


		
		
	def get_course_list(self):
		program_course_list = self.courses
		course_list = [
			frappe.get_doc("Course", program_course.course)
			for program_course in program_course_list
		]
		return course_list

""" 	def validate_courses_pgmtrack(self):
		program_course_list = self.courses
		pgm_track_list = self.pgm_courses_track
		if pgm_track_list:
			for pgm_track in pgm_track_list:
				if pgm_track not in program_course_list:
					frappe.throw(
						"Course {0} is in the Program Track but not in Courses for this Program".format(pgm_track.program_track_course)
					)
		return """