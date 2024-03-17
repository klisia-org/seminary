# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from frappe.utils.csvutils import getlink


class CourseEnrollmentIndividual(Document):
	def validate(self):
		self.validate_duplicate()

	def validate_duplicate(self):
		CEI= frappe.get_list(
			"Course Enrollment Individual",
			filters={
				"program_ce": (self.program_ce),
				"coursesc_ce": self.coursesc_ce,
				"docstatus": ("=", 1),
			},
		)
		if CEI:
			frappe.throw(
				_("This Course Enrollment {0} already exists.").format(
					getlink("Course Enrollment Individual", CEI[0].name)
				)
			)

	def get_program_courses(self):
		program = frappe.get_doc("Program Enrollment", self.program_ce)
		courses = []

			# Get courses from program.courses child table
		for course in program.courses:
			courses.append(course.course)

			# Get courses from program_track_courses where emphasis_program_track matches
			if program.emphasis_program_track:
				track_courses = frappe.get_list(
					"Program Track Courses",
					filters={"program_track": program.emphasis_program_track},
					fields=["course"],
					)
				for track_course in track_courses:
					courses.append(track_course.course)

				if program.program_type != "Time-based":
					return courses

				if program.program_type == "Time-based":
					program_course = frappe.get_doc("Program Course", course)
					if program_course.course_term > program.current_std_term:
						courses.remove(course)
						return courses

				
				
				for course in courses:
					course_doc = frappe.get_doc("Course", course)
					if course_doc.prereq_mandatory == "Mandatory":
						courses.remove(course)
					elif course_doc.prereq_mandatory == "Recommended":
						confirm_enrollment = frappe.confirm(
							"Recommended pre-requisites for this course are not met. Are you sure you want to enroll?",
							title="Confirmation",
							primary_action="Save",
							secondary_action="Cancel"
						)
						if not confirm_enrollment:
							return

@frappe.whitelist()
def copy_data_to_program_enrollment_course(program_ce, coursesc_ce):
		program_enrollment = frappe.get_doc("Program Enrollment", program_ce)
		course_schedule = frappe.get_doc("Course Schedule", coursesc_ce)
		course = coursesc_ce

		if course:
			course_name = course_schedule.course
			academic_term = course_schedule.academic_term
			program_enrollment.append("Program Enrollment Course", {
				"course_schedule": course,
				"course_name": course_name,
				"academic_term": academic_term
			})

		program_enrollment.save()


@frappe.whitelist()
def copy_data_to_scheduled_course_roster(self):
		course_schedule = frappe.get_doc("Course Schedule", self.coursesc_ce)
		student = frappe.get_doc("Student", self.student_ce)

		if course_schedule and student:
			scheduled_course_roster = frappe.get_doc({
			"doctype": "Scheduled Course Roster",
			"parent": course_schedule.name,
			"parenttype": "Course Schedule",
			"parentfield": "cs_roster",
			"student_roster": self.student_ce,
			"stuname_roster": self.student_ce,
			"student_main_link": student.name,
			"stuemail_rc": student.student_email_id,
			"program_std_scr": course_schedule.program_data,
			"audit": self.audit_bool,
			
			})
		scheduled_course_roster.insert().submit()

@frappe.whitelist()
def on_submit(self):
		self.copy_data_to_scheduled_course_roster()
