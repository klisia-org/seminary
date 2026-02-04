# Copyright (c) 2024, Klisia and Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CourseGradebook(Document):
    @frappe.whitelist()
    def get_student_grades(self, course_schedule):
        student_list = []
        student_attendance_list = []
        student_list = frappe.get_all(
            "Scheduled Course Roster",
            fields=[
                "stuname_roster",
                "stuemail_rc",
                "program_std_scr",
                "audit_bool",
                "active",
            ],
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
