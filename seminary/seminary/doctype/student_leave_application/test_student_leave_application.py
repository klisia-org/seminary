# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest

import frappe
from frappe.utils import add_days, getdate

from seminary.seminary.doctype.student.test_student import create_student


class TestStudentLeaveApplication(unittest.TestCase):
    def setUp(self):
        frappe.db.sql("""delete from `tabStudent Leave Application`""")

    def test_attendance_record_creation(self):
        leave_application = create_leave_application()
        attendance_record = frappe.db.exists(
            "Student Attendance",
            {"leave_application": leave_application.name, "status": "Absent"},
        )
        self.assertTrue(attendance_record)

        # mark as present
        date = add_days(getdate(), -1)
        leave_application = create_leave_application(date, date, 1)
        attendance_record = frappe.db.exists(
            "Student Attendance",
            {"leave_application": leave_application.name, "status": "Present"},
        )
        self.assertTrue(attendance_record)

    def test_attendance_record_updated(self):
        attendance = create_student_attendance()
        create_leave_application()
        self.assertEqual(
            frappe.db.get_value("Student Attendance", attendance.name, "status"),
            "Absent",
        )

    def test_attendance_record_cancellation(self):
        leave_application = create_leave_application()
        leave_application.cancel()
        attendance_status = frappe.db.get_value(
            "Student Attendance",
            {"leave_application": leave_application.name},
            "docstatus",
        )
        self.assertTrue(attendance_status, 2)


def create_leave_application(from_date=None, to_date=None, mark_as_present=0, submit=1):
    student = get_student()

    leave_application = frappe.new_doc("Student Leave Application")
    leave_application.student = student.name
    leave_application.attendance_based_on = "Student Group"

    leave_application.from_date = from_date if from_date else getdate()
    leave_application.to_date = from_date if from_date else getdate()
    leave_application.mark_as_present = mark_as_present

    if submit:
        leave_application.insert()
        leave_application.submit()

    return leave_application


def create_student_attendance(date=None, status=None):
    student = get_student()
    attendance = frappe.get_doc(
        {
            "doctype": "Student Attendance",
            "student": student.name,
            "status": status if status else "Present",
            "date": date if date else getdate(),
        }
    ).insert()
    return attendance


def get_student():
    return create_student(
        dict(email="test_student@gmail.com", first_name="Test", last_name="Student")
    )
