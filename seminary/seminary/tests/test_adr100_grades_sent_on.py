# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""ADR 100 §8 groundwork: the day a student's grades are sent is recorded on
their roster row, because oral audio is kept for a period counted from it."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import api
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr081_attendance import _roster, _section


class TestGradesSentOn(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.program = fx.make_program()
		self.student = fx.make_student()
		self.cs = _section()
		self.pe = fx.make_enrollment(self.student, self.program, submit=False)
		frappe.get_doc(
			{
				"doctype": "Program Enrollment Course",
				"name": frappe.generate_hash(length=10),
				"parent": self.pe.name,
				"parenttype": "Program Enrollment",
				"parentfield": "courses",
				"course": self.cs,
				"credits": 3,
			}
		).db_insert()
		self.roster = _roster(
			self.cs,
			self.student.name,
			self.program.name,
			fscore=90,
			fgrade="A",
			fgradepass="Pass",
		)

	def _finalize(self):
		with (
			patch.object(api, "_grade_thisstudent"),
			patch.object(api, "_fgrade_this_std"),
			patch.object(api, "_assert_grade_computed"),
			patch.object(api, "_cbe_count_in_gpa", return_value=None),
		):
			return api.finalize_roster(self.roster)

	def test_finalizing_records_when_grades_were_sent(self):
		self.assertEqual(self._finalize(), self.pe.name)
		sent = frappe.db.get_value("Scheduled Course Roster", self.roster, "grades_sent_on")
		self.assertIsNotNone(sent)

	def test_the_first_send_wins(self):
		self._finalize()
		first = frappe.db.get_value("Scheduled Course Roster", self.roster, "grades_sent_on")
		self.assertIsNone(self._finalize())
		self.assertEqual(
			frappe.db.get_value("Scheduled Course Roster", self.roster, "grades_sent_on"),
			first,
		)

	def test_an_audit_roster_gets_no_date(self):
		frappe.db.set_value("Scheduled Course Roster", self.roster, "audit_bool", 1)
		self.assertIsNone(self._finalize())
		self.assertIsNone(frappe.db.get_value("Scheduled Course Roster", self.roster, "grades_sent_on"))
