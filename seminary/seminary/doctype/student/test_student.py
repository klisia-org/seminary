# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt

import unittest

import frappe

from seminary.seminary.doctype.program.test_program import (
    make_program_and_linked_courses,
)

test_records = frappe.get_test_records("Student")


class TestStudent(unittest.TestCase):
    def setUp(self):
        create_student(
            {
                "first_name": "_Test Name",
                "last_name": "_Test Last Name",
                "email": "_test_student@example.com",
            }
        )
        make_program_and_linked_courses(
            "_Test Program 1", ["_Test Course 1", "_Test Course 2"]
        )

    def test_create_student_user(self):
        self.assertTrue(bool(frappe.db.exists("User", "_test_student@example.com")))
        frappe.db.rollback()

    def test_enroll_in_program(self):
        student = get_student("_test_student@example.com")
        enrollment = student.enroll_in_program("_Test Program 1")
        test_enrollment = frappe.get_all(
            "Program Enrollment",
            filters={"student": student.name, "program": "_Test Program 1"},
        )
        self.assertTrue(len(test_enrollment))
        self.assertEqual(test_enrollment[0]["name"], enrollment.name)
        frappe.db.rollback()

    def test_get_pgmenrollments(self):
        # Renamed from get_program_enrollments, and it now returns a list of
        # dicts rather than a program-keyed mapping.
        student = get_student("_test_student@example.com")
        student.enroll_in_program("_Test Program 1")
        rows = student.get_pgmenrollments()
        self.assertIn("_Test Program 1", [r["program"] for r in rows])
        frappe.db.rollback()

    def tearDown(self):
        # Scoped to this test's own student. The original swept *every* Program
        # Enrollment on the site, which would have destroyed a school's records
        # the first time anyone ran the suite outside a throwaway database.
        student = get_student("_test_student@example.com")
        if student:
            for entry in frappe.db.get_all(
                "Program Enrollment", filters={"student": student.name}
            ):
                doc = frappe.get_doc("Program Enrollment", entry.name)
                if doc.docstatus == 1:
                    doc.cancel()
                doc.delete()
        frappe.db.rollback()


def create_student(student_dict):
    student = get_student(student_dict["email"])
    if not student:
        student = frappe.get_doc(
            {
                "doctype": "Student",
                "first_name": student_dict["first_name"],
                "last_name": student_dict["last_name"],
                "student_email_id": student_dict["email"],
            }
        ).insert()
    return student


def get_student(email):
    try:
        student_id = frappe.get_all("Student", {"student_email_id": email}, ["name"])[
            0
        ].name
        return frappe.get_doc("Student", student_id)
    except IndexError:
        return None
