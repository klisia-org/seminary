# Copyright (c) 2015, Frappe and Contributors
# See license.txt

import unittest

import frappe

from seminary.seminary.doctype.program.test_program import (
    make_program_and_linked_courses,
)
from seminary.seminary.doctype.student.test_student import create_student, get_student


class TestProgramEnrollment(unittest.TestCase):
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
