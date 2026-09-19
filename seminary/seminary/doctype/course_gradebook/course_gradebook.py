# Copyright (c) 2024, Klisia and Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CourseGradebook(Document):
    # Not whitelisted (p007 §2.7, applied by the p008a G10 inventory): there is no
    # caller in any .js or .vue, and it cannot have one -- the roster filter below
    # names a `parent` column Scheduled Course Roster does not have, so it has
    # raised OperationalError for every caller, Administrator included. Had it
    # worked, any Instructor (the role includes a one-section grader) could have
    # pulled any section's roster through frappe.get_all, which the row hook
    # never sees. If it is revived, gate it with require_course_staff.
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
