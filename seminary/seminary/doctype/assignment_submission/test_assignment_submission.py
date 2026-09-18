# Copyright (c) 2025, Klisia / SeminaryERP and Contributors
# See license.txt

# import frappe
from frappe.tests.utils import FrappeTestCase

# p006: the p006 tests in this folder build their own minimal fixtures. The
# automatic link-dependency preload is switched off because the app's Student and
# Instructor test records predate the Person-first mandatory fields (ADR 068) and
# abort every IntegrationTestCase in this folder before a test runs.
IGNORE_TEST_RECORD_DEPENDENCIES = [
    "Assignment Activity",
    "Course",
    "Course Lesson",
    "Course Schedule",
    "Scheduled Course Assess Criteria",
    "Student",
    "User",
]


class TestAssignmentSubmission(FrappeTestCase):
    pass
