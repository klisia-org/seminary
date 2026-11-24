# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""privatedocs p027: what the meeting provider reports after a school meeting."""

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import ClassVar
from unittest.mock import patch

import frappe

from seminary.seminary import oral_meetings, school_meetings
from seminary.seminary.tests import test_adr051a_school_meetings as t051a
from seminary.seminary.tests.test_adr051a_school_meetings import (
	CALLS,
	MeetingCase,
	_account,
	_save,
	_school_section,
)
from seminary.seminary.tests.test_adr100_meeting_rows import MON
from seminary.seminary.tests.test_adr100d_meeting_capture import _on_roster, _student

THIS = "seminary.seminary.tests.test_p027_class_meeting_reports"
REPORT = "Class Meeting Report"
END = datetime.combine(MON, datetime.strptime("10:00", "%H:%M").time())


class ReportingProvider(t051a.FakeProvider):
	default = False
	answer = None
	asked: ClassVar[list] = []

	def records_by_default(self):
		return ReportingProvider.default

	def after_meeting(self, account, meeting_id, meeting):
		ReportingProvider.asked.append((meeting_id, meeting["record"]))
		return ReportingProvider.answer


@contextmanager
def _provider():
	with patch.object(school_meetings, "providers", return_value={"Fake": f"{THIS}.ReportingProvider"}):
		yield


class ReportCase(MeetingCase):
	def setUp(self):
		super().setUp()
		ReportingProvider.default = False
		ReportingProvider.answer = None
		ReportingProvider.asked = []
		self._patch = patch.object(t051a, "_provider", _provider)
		self._patch.start()
		self.account = _account()
		self.cs = _school_section()
		self.row = self.cs.cs_meetinfo[0]

	def tearDown(self):
		self._patch.stop()
		super().tearDown()

	def collect(self, after=timedelta(minutes=10)):
		with _provider():
			return school_meetings.collect_row(self.row.name, now=END + after)


class TestRecording(ReportCase):
	def test_the_school_default_decides_until_the_section_says(self):
		with _provider():
			self.assertFalse(school_meetings.row_recorded(self.cs, self.row))
			ReportingProvider.default = True
			self.assertTrue(school_meetings.row_recorded(self.cs, self.row))
			self.cs.record_meetings = "Do not record"
			self.assertFalse(school_meetings.row_recorded(self.cs, self.row))

	def test_changing_the_choice_updates_the_provider_meeting(self):
		CALLS.clear()
		_save(self.cs, record_meetings="Record")
		self.assertEqual([c[0] for c in CALLS], ["update"])
		cs = frappe.get_doc("Course Schedule", self.cs.name)
		with _provider():
			self.assertTrue(school_meetings._meeting(cs, cs.cs_meetinfo[0], [])["record"])
			self.assertEqual(school_meetings.recorded_rows(cs.name), {self.row.name})

	def test_resync_upcoming_leaves_past_meetings_alone(self):
		# MON is in the past: nothing to resync for it.
		with patch.object(school_meetings, "_enqueue") as enqueue:
			school_meetings.resync_upcoming()
		self.assertNotIn(self.cs.name, [c.args[0] for c in enqueue.call_args_list])


class TestReport(ReportCase):
	def test_nothing_is_kept_until_the_meeting_has_ended(self):
		self.assertIsNone(self.collect())
		self.assertFalse(frappe.db.exists(REPORT, {"meeting": self.row.name}))

	def test_a_recording_still_coming_keeps_the_report_waiting(self):
		_save(self.cs, record_meetings="Record")
		ReportingProvider.answer = {"participants": [], "recording": None, "pending": True}
		self.assertEqual(self.collect().status, "Waiting")
		self.assertEqual(ReportingProvider.asked[-1][1], True)
		ReportingProvider.answer = {
			"participants": [],
			"recording": {"url": "https://zoom.example/rec/1", "passcode": "x1"},
			"pending": False,
		}
		doc = self.collect()
		self.assertEqual(
			(doc.status, doc.recording_url, doc.recording_passcode),
			("Done", "https://zoom.example/rec/1", "x1"),
		)
		self.assertEqual(frappe.db.count(REPORT, {"meeting": self.row.name}), 1, "one report per meeting")

	def test_after_48_hours_a_missing_recording_is_given_up(self):
		ReportingProvider.answer = {"participants": [], "recording": None, "pending": True}
		doc = self.collect(after=timedelta(hours=49))
		self.assertEqual(doc.status, "Done")
		self.assertTrue(doc.error)

	def test_a_provider_error_shows_on_the_report(self):
		with patch.object(
			ReportingProvider, "after_meeting", side_effect=frappe.ValidationError("No scope.")
		):
			doc = self.collect()
		self.assertEqual((doc.status, doc.error), ("Failed", "No scope."))

	def test_the_sweep_only_asks_inside_the_window(self):
		ReportingProvider.answer = {"participants": [], "recording": None, "pending": False}
		with _provider():
			school_meetings.sweep(now=END + timedelta(minutes=2))
			self.assertFalse(ReportingProvider.asked)
			school_meetings.sweep(now=END + timedelta(minutes=10))
			self.assertIn(self.row.cs_meeting_id, [a[0] for a in ReportingProvider.asked])
			ReportingProvider.asked.clear()
			school_meetings.sweep(now=END + timedelta(minutes=20))
			self.assertNotIn(self.row.cs_meeting_id, [a[0] for a in ReportingProvider.asked])

	def test_a_deleted_meeting_row_takes_its_report(self):
		ReportingProvider.answer = {"participants": [], "recording": None, "pending": False}
		self.collect()
		_save(self.cs, school_meeting=0)
		cs = frappe.get_doc("Course Schedule", self.cs.name)
		cs.cs_meetinfo = []
		_save(cs)
		self.assertFalse(frappe.db.exists(REPORT, {"meeting": self.row.name}))


class TestSuggestedAttendance(ReportCase):
	def setUp(self):
		super().setUp()
		self.ana = _student("Ana Lúcia Prado")
		self.ben = _student("Benjamin Okafor")
		_on_roster(self.cs.name, self.ana, "Ana Lúcia Prado")
		_on_roster(self.cs.name, self.ben, "Benjamin Okafor")
		email = frappe.db.get_value("User", self.ana.user, "email")
		ReportingProvider.answer = {
			"participants": [
				# Ana by email, all hour long; Ben by name, for 20 minutes.
				{"name": "Ana's laptop", "email": email.upper(), "attended_s": 3600},
				{"name": "benjamin okafor", "email": None, "attended_s": 1200},
				{"name": "Guest 1", "email": None, "attended_s": 3600},
			],
			"recording": None,
			"pending": False,
		}
		self.collect()

	def test_matches_by_email_then_by_name(self):
		doc = frappe.get_doc(REPORT, {"meeting": self.row.name})
		self.assertEqual(
			[(p.match or None, p.student) for p in doc.participants],
			[("Email", self.ana.name), ("Name", self.ben.name), (None, None)],
		)

	def test_only_students_in_for_the_least_share_are_enough(self):
		out = oral_meetings.attendance_suggestions(self.cs.name, self.row.name)
		self.assertEqual(set(out), {self.ana.name, self.ben.name})
		self.assertEqual((out[self.ana.name]["share"], out[self.ana.name]["enough"]), (100, True))
		self.assertEqual((out[self.ben.name]["share"], out[self.ben.name]["enough"]), (33, False))
		frappe.db.set_single_value("Seminary Settings", "meeting_attendance_min_share", 30)
		try:
			out = oral_meetings.attendance_suggestions(self.cs.name, self.row.name)
			self.assertTrue(out[self.ben.name]["enough"])
		finally:
			frappe.db.set_single_value("Seminary Settings", "meeting_attendance_min_share", 50)

	def test_no_attendance_row_exists_until_the_instructor_marks(self):
		self.assertFalse(frappe.db.exists("Student Attendance", {"meeting": self.row.name}))
