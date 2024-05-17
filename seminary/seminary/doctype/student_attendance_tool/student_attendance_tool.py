# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document


class StudentAttendanceTool(Document):
	pass


@frappe.whitelist()
def get_student_attendance_records(
	date=None, course_schedule=None
):
	student_list = []
	student_attendance_list = []
	student_list = frappe.get_all(
		"Scheduled Course Roster",
		fields=["stuname_roster", "stuemail_rc", "program_std_scr", "audit_bool", "active"],
		filters={"parent": course_schedule},
		order_by="stuname_roster",
	)

	

	StudentAttendance = frappe.qb.DocType("Student Attendance")

	student_attendance_list = (
		frappe.qb.from_(StudentAttendance)
		.select(StudentAttendance.student, StudentAttendance.status)
		.where((StudentAttendance.course_schedule == course_schedule))
	).run(as_dict=True)
	

	for attendance in student_attendance_list:
		for student in student_list:
			if student.stuname_roster == attendance.student:
				student.active = attendance.status

	return student_list
