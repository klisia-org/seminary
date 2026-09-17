# Copyright (c) 2025, Klisia / SeminaryERP and Contributors
# See license.txt

# import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
# p006: the p006 tests in this folder build their own minimal fixtures. The
# automatic link-dependency preload is switched off because the app's Student and
# Instructor test records predate the Person-first mandatory fields (ADR 068) and
# abort every IntegrationTestCase in this folder before a test runs.
IGNORE_TEST_RECORD_DEPENDENCIES = [
    "Course",
    "Course Lesson",
    "Course Schedule",
    "Exam Activity",
    "Exam Question",
    "Exam Submission",
    "Scheduled Course Assess Criteria",
    "Student",
    "User",
]


class UnitTestExamSubmission(UnitTestCase):
    """
    Unit tests for ExamSubmission.
    Use this class for testing individual functions and methods.
    """

    pass


class IntegrationTestExamSubmission(IntegrationTestCase):
    """
    Integration tests for ExamSubmission.
    Use this class for testing interactions between multiple components.
    """

    pass
