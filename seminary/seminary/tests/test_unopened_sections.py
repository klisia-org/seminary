# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p007 §8.1: an enrolled student is told a section isn't published yet, and still can't open it."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import guards, utils
from seminary.seminary.tests import cohort_fixtures as fx


class TestUnopenedSections(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.savepoint("unopened")
		self.student = fx.make_student()
		self.sections = {}
		for key, published, state in (
			("draft", 0, "Open for Enrollment"),
			("open", 1, "Grading"),
			("cancelled", 0, "Cancelled"),
		):
			cs = frappe.get_doc(
				{
					"doctype": "Course Schedule",
					"name": fx.uid("CS"),
					"published": published,
					"workflow_state": state,
				}
			)
			cs.db_insert()
			frappe.get_doc(
				{
					"doctype": "Scheduled Course Roster",
					"name": f"{cs.name}-{self.student.name}",
					"course_sc": cs.name,
					"student": self.student.name,
					"active": 1,
					"audit_bool": 0,
				}
			).db_insert()
			self.sections[key] = cs.name
		self.as_student = patch.object(guards, "current_student", return_value=self.student.name)
		self.as_student.start()

	def tearDown(self):
		self.as_student.stop()
		frappe.db.rollback(save_point="unopened")
		super().tearDown()

	def test_only_the_unpublished_live_section_is_named(self):
		self.assertEqual(guards.unopened_sections(), [self.sections["draft"]])

	def test_it_stays_closed(self):
		self.assertFalse(guards.is_published(self.sections["draft"]))
		with (
			patch.object(guards, "is_course_staff", return_value=False),
			patch.object(guards, "instructor_tier", return_value=None),
		):
			self.assertFalse(guards.is_enrolled(self.sections["draft"], "student@example.com"))

	def test_course_details_says_not_open_yet(self):
		with patch.object(utils, "section_access", return_value=None):
			details = utils.get_course_details(self.sections["draft"])
		self.assertEqual(details.not_open_yet, 1)
