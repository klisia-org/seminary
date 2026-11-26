# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/119: Incompletes, the server-side freeze, grade changes, repeats and transcripts."""

import hashlib
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from seminary.seminary import api, grade_changes, incompletes, repeats, transcripts
from seminary.seminary.financial.backend import NullFinancialBackend, PaymentAggregate
from seminary.seminary.tests import cohort_fixtures as fx

INTERVALS = [
	{"grade_code": "A", "threshold": 90, "grade_pass": "Pass"},
	{"grade_code": "B", "threshold": 80, "grade_pass": "Pass"},
	{"grade_code": "C", "threshold": 70, "grade_pass": "Pass"},
	{"grade_code": "F", "threshold": 0, "grade_pass": "Fail"},
]


def _scale(inc_code="I", lapse_code=""):
	name = fx.uid("GS")
	frappe.get_doc(
		{
			"doctype": "Grading Scale",
			"name": name,
			"grading_scale_name": name,
			"grscale_type": "Points",
			"maxnumgrade": 100,
			"inc_code": inc_code,
			"lapse_code": lapse_code,
		}
	).db_insert()
	for idx, row in enumerate(INTERVALS, 1):
		frappe.get_doc(
			{
				"doctype": "Grading Scale Interval",
				"name": frappe.generate_hash(length=10),
				"parent": name,
				"parenttype": "Grading Scale",
				"parentfield": "intervals",
				"idx": idx,
				**row,
			}
		).db_insert()
	frappe.local.grading_scale_intervals = {}
	return name


def _backend(**methods):
	"""A null backend with some methods replaced: the test site may have a real one active."""
	backend = NullFinancialBackend()
	for name, value in methods.items():
		setattr(backend, name, value)
	return patch("seminary.seminary.financial.backend.get_financial_backend", return_value=backend)


def _pdf_bytes():
	import io

	from pypdf import PdfWriter

	writer = PdfWriter()
	writer.add_blank_page(width=200, height=200)
	out = io.BytesIO()
	writer.write(out)
	return out.getvalue()


def _settings(**values):
	for k, v in values.items():
		frappe.db.set_single_value("Seminary Settings", k, v)
	frappe.clear_document_cache("Seminary Settings", "Seminary Settings")


class ADR119Case(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.savepoint("adr119")
		_settings(
			incomplete_default_days=30,
			incomplete_instructor_max_days=60,
			incomplete_reminder_days=2,
			grade_change_second_approver_role=None,
			grade_change_second_approval_days=0,
		)
		self.program = fx.make_program()
		self.end = getdate(add_days(today(), -1))
		self.cs = self.section()
		self.a = self.enrol(fx.make_student())
		self.b = self.enrol(fx.make_student())

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="adr119")
		frappe.clear_document_cache("Seminary Settings", "Seminary Settings")
		frappe.local.grading_scale_intervals = {}
		super().tearDown()

	def section(self, scale=None):
		cs = frappe.get_doc(
			{
				"doctype": "Course Schedule",
				"name": fx.uid("CS"),
				"workflow_state": "Grading",
				"open_ended": 0,
				"gradesc_cs": scale or _scale(),
				"maxnumgrade": 100,
				"c_dateend": self.end,
				"title": "Test Course",
			}
		)
		cs.db_insert()
		self.rows = []
		for idx, title in enumerate(("Paper", "Exam"), 1):
			row = frappe.get_doc(
				{
					"doctype": "Scheduled Course Assess Criteria",
					"name": fx.uid("SCAC"),
					"parent": cs.name,
					"parenttype": "Course Schedule",
					"parentfield": "courseassescrit_sc",
					"idx": idx,
					"title": title,
					"type": "Offline",
					"weight_scac": 50,
				}
			)
			row.db_insert()
			self.rows.append(row.name)
		return cs.name

	def enrol(self, student, cs=None, course_name="ZZT-COURSE"):
		cs = cs or self.cs
		pe = frappe.db.get_value(
			"Program Enrollment", {"student": student.name, "program": self.program.name}
		)
		if not pe:
			pe = fx.make_enrollment(student, self.program, submit=False).name
		frappe.get_doc(
			{
				"doctype": "Program Enrollment Course",
				"name": frappe.generate_hash(length=10),
				"parent": pe,
				"parenttype": "Program Enrollment",
				"parentfield": "courses",
				"course": cs,
				"course_name": course_name,
				"credits": 3,
				"count_in_gpa": 1,
				"status": "Enrolled",
			}
		).db_insert()
		roster = frappe.get_doc(
			{
				"doctype": "Scheduled Course Roster",
				"name": f"{cs}-{student.name}",
				"course_sc": cs,
				"student": student.name,
				"stuname_roster": student.name,
				"program_std_scr": self.program.name,
				"active": 1,
				"audit_bool": 0,
			}
		)
		roster.db_insert()
		for row in frappe.get_all("Scheduled Course Assess Criteria", filters={"parent": cs}, pluck="name"):
			frappe.get_doc(
				{
					"doctype": "Course Assess Results Detail",
					"name": frappe.generate_hash(length=10),
					"parent": roster.name,
					"parenttype": "Scheduled Course Roster",
					"parentfield": "stdroster_grade",
					"assessment_criteria": row,
					"student_card": student.name,
					"maximum_score": 50,
				}
			).db_insert()
		return frappe._dict(student=student.name, pe=pe, roster=roster.name)

	def grade(self, who, *scores):
		cards = frappe.get_all(
			"Course Assess Results Detail",
			filters={"parent": who.roster},
			fields=["name", "assessment_criteria"],
			order_by="idx asc, creation asc",
		)
		by_row = {c.assessment_criteria: c.name for c in cards}
		for row, score in zip(self.rows, scores, strict=False):
			frappe.db.set_value(
				"Course Assess Results Detail", by_row[row], {"rawscore_card": score, "graded_card": 1}
			)

	def pec(self, who, cs=None):
		return frappe.db.get_value(
			"Program Enrollment Course",
			{"parent": who.pe, "course": cs or self.cs},
			[
				"name",
				"status",
				"pec_finalgradecode",
				"pec_finalgradenum",
				"credits",
				"count_in_gpa",
				"repeated",
				"attempt",
			],
			as_dict=True,
		)

	def roster(self, who):
		return frappe.db.get_value(
			"Scheduled Course Roster",
			who.roster,
			[
				"active",
				"incomplete",
				"incomplete_until",
				"incomplete_resolution",
				"fgrade",
				"incomplete_reminder_sent",
			],
			as_dict=True,
		)

	def send(self):
		return api.send_grades(doc={"name": self.cs})


class TestIncompleteAtSendGrades(ADR119Case):
	def test_an_incomplete_lets_the_class_go_and_stays_open(self):
		self.grade(self.a, 95, 85)
		self.grade(self.b, 90)  # one assessment left
		with self.assertRaises(frappe.ValidationError):
			self.send()
		incompletes.mark_incomplete(self.b.roster, "Hospitalised in week 12")
		self.send()

		self.assertEqual(frappe.db.get_value("Course Schedule", self.cs, "workflow_state"), "Closed")
		self.assertEqual(self.pec(self.a).status, "Pass")
		b = self.pec(self.b)
		self.assertEqual((b.status, b.pec_finalgradecode), ("Incomplete", "I"))
		self.assertEqual(b.count_in_gpa, 0)
		self.assertEqual(self.roster(self.b).active, 1)
		self.assertEqual(getdate(self.roster(self.b).incomplete_until), getdate(add_days(self.end, 30)))
		# The unfinished assessment got an individual due date on the completion date.
		due = frappe.db.get_value(
			"Student Due Date Override",
			{"student": self.b.student, "course_assess": self.rows[1]},
			"due_date",
		)
		self.assertEqual(getdate(due), getdate(add_days(self.end, 30)))

	def test_send_one_grade_after_the_course_closed(self):
		self.grade(self.a, 95, 85)
		self.grade(self.b, 90)
		incompletes.mark_incomplete(self.b.roster, "Family emergency")
		self.send()
		with self.assertRaises(frappe.ValidationError):
			incompletes.send_incomplete_grade(self.b.roster)
		self.grade(self.b, 90, 70)
		incompletes.send_incomplete_grade(self.b.roster)
		b = self.pec(self.b)
		self.assertEqual((b.status, b.pec_finalgradecode), ("Pass", "B"))
		r = self.roster(self.b)
		self.assertEqual((r.active, r.incomplete_resolution), (0, incompletes.COMPLETED))

	def test_needs_an_incomplete_code_on_the_scale(self):
		frappe.db.set_value(
			"Grading Scale", frappe.db.get_value("Course Schedule", self.cs, "gradesc_cs"), "inc_code", ""
		)
		with self.assertRaises(frappe.ValidationError):
			incompletes.mark_incomplete(self.b.roster, "reason")

	def test_an_instructor_is_held_to_the_limit(self):
		late = add_days(self.end, 61)
		with patch.object(incompletes, "_is_school", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				incompletes.mark_incomplete(self.b.roster, "reason", late)
			incompletes.mark_incomplete(self.b.roster, "reason", add_days(self.end, 60))

	def test_nothing_unfinished_means_no_incomplete(self):
		self.grade(self.b, 80, 80)
		with self.assertRaises(frappe.ValidationError):
			incompletes.mark_incomplete(self.b.roster, "reason")

	def test_the_gradebook_hears_whether_the_scale_allows_it(self):
		from seminary.seminary import utils

		with patch.object(utils, "section_access", return_value="instructor"):
			self.assertEqual(utils.get_course_details(self.cs).incompletes_enabled, 1)
			frappe.db.set_value(
				"Grading Scale", frappe.db.get_value("Course Schedule", self.cs, "gradesc_cs"), "inc_code", ""
			)
			self.assertEqual(utils.get_course_details(self.cs).incompletes_enabled, 0)

	def test_the_scale_checks_its_codes(self):
		scale = frappe.get_doc("Grading Scale", frappe.db.get_value("Course Schedule", self.cs, "gradesc_cs"))
		scale.lapse_code = "Z"
		with self.assertRaises(frappe.ValidationError):
			scale.validate_incomplete_codes()
		scale.lapse_code, scale.inc_code = "F", "A"
		with self.assertRaises(frappe.ValidationError):
			scale.validate_incomplete_codes()
		scale.inc_code = "I"
		scale.validate_incomplete_codes()

	def test_clear_removes_the_mark_and_its_due_dates(self):
		incompletes.mark_incomplete(self.b.roster, "reason")
		incompletes.clear_incomplete(self.b.roster)
		self.assertEqual(self.roster(self.b).incomplete, 0)
		self.assertFalse(frappe.db.exists("Student Due Date Override", {"student": self.b.student}))


class TestDailyJob(ADR119Case):
	def setUp(self):
		super().setUp()
		self.grade(self.a, 95, 85)
		self.grade(self.b, 90)
		incompletes.mark_incomplete(self.b.roster, "reason", add_days(today(), 10))
		self.send()

	def test_reminder_two_days_before_when_work_is_unsubmitted(self):
		with patch("seminary.seminary.comms.send") as send:
			incompletes.daily(add_days(today(), 7))
			self.assertFalse(send.called)
			incompletes.daily(add_days(today(), 8))
			self.assertTrue(send.called)
			self.assertEqual(send.call_args.args[1], "incomplete-reminder")
		self.assertEqual(self.roster(self.b).incomplete_reminder_sent, 1)

	def test_lapse_grades_unfinished_work_as_zero(self):
		with patch("seminary.seminary.comms.send"), patch("seminary.seminary.comms.send_to_role"):
			incompletes.daily(add_days(today(), 11))
		b = self.pec(self.b)
		# 90 on half the weight, 0 on the other half.
		self.assertEqual((b.status, b.pec_finalgradecode), ("Fail", "F"))
		self.assertEqual(self.roster(self.b).incomplete_resolution, incompletes.LAPSED)

	def test_lapse_can_assign_the_scale_s_code(self):
		frappe.db.set_value(
			"Grading Scale", frappe.db.get_value("Course Schedule", self.cs, "gradesc_cs"), "lapse_code", "C"
		)
		with patch("seminary.seminary.comms.send"), patch("seminary.seminary.comms.send_to_role"):
			incompletes.lapse(self.b.roster)
		b = self.pec(self.b)
		self.assertEqual((b.pec_finalgradecode, b.status, b.pec_finalgradenum), ("C", "Pass", 70))


class TestExtensionRequest(ADR119Case):
	def setUp(self):
		super().setUp()
		self.grade(self.a, 95, 85)
		self.grade(self.b, 90)
		incompletes.mark_incomplete(self.b.roster, "reason")
		self.send()

	def request(self, until):
		return frappe.get_doc(
			{
				"doctype": "Incomplete Extension Request",
				"roster": self.b.roster,
				"requested_until": until,
				"reason": "Surgery",
			}
		).insert()

	def test_approval_moves_the_date_and_charges_the_fee(self):
		until = add_days(self.end, 90)
		with patch("seminary.seminary.comms.send"), patch("seminary.seminary.comms.send_to_role"):
			req = self.request(until)
			calls = []
			with _backend(charge_incomplete_extension=lambda name: calls.append(name) or ["CHG-1"]):
				incompletes.approve_extension(req.name, "OK")
		self.assertEqual(calls, [req.name])
		self.assertEqual(getdate(self.roster(self.b).incomplete_until), getdate(until))
		self.assertEqual(frappe.db.get_value("Incomplete Extension Request", req.name, "charges"), "CHG-1")

	def test_a_date_before_the_current_one_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.request(add_days(self.end, 5))

	def test_one_open_request_at_a_time(self):
		with patch("seminary.seminary.comms.send"), patch("seminary.seminary.comms.send_to_role"):
			self.request(add_days(self.end, 90))
			with self.assertRaises(frappe.ValidationError):
				self.request(add_days(self.end, 100))

	def test_a_decline_needs_a_reason_and_charges_nothing(self):
		with patch("seminary.seminary.comms.send"), patch("seminary.seminary.comms.send_to_role"):
			req = self.request(add_days(self.end, 90))
			with self.assertRaises(frappe.ValidationError):
				incompletes.decline_extension(req.name, "")
			calls = []
			with _backend(charge_incomplete_extension=lambda name: calls.append(name) or []):
				incompletes.decline_extension(req.name, "Not enough reason")
		self.assertEqual(calls, [])
		self.assertEqual(getdate(self.roster(self.b).incomplete_until), getdate(add_days(self.end, 30)))


class TestFreeze(ADR119Case):
	def setUp(self):
		super().setUp()
		self.grade(self.a, 95, 85)
		self.grade(self.b, 80, 80)
		self.send()

	def test_a_sent_roster_refuses_a_changed_score(self):
		doc = frappe.get_doc("Scheduled Course Roster", self.a.roster)
		doc.stdroster_grade[0].rawscore_card = 10
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_a_result_row_saved_on_its_own_is_refused(self):
		name = frappe.get_all(
			"Course Assess Results Detail", filters={"parent": self.a.roster}, pluck="name"
		)[0]
		card = frappe.get_doc("Course Assess Results Detail", name)
		card.rawscore_card = 10
		with self.assertRaises(frappe.ValidationError):
			card.save(ignore_permissions=True)

	def test_an_unchanged_save_still_works(self):
		frappe.get_doc("Scheduled Course Roster", self.a.roster).save(ignore_permissions=True)


class TestGradeChange(ADR119Case):
	def setUp(self):
		super().setUp()
		self.grade(self.a, 95, 85)
		self.grade(self.b, 80, 60)
		self.send()

	def request(self, value):
		return frappe.get_doc(
			{
				"doctype": "Grade Change Request",
				"roster": self.b.roster,
				"reason": "Exam was mis-keyed",
				"changes": [{"assessment": self.rows[1], "new_value": value}],
			}
		).insert()

	def test_approval_rewrites_the_transcript_row(self):
		self.assertEqual(self.pec(self.b).pec_finalgradecode, "C")
		req = self.request(100)
		self.assertEqual(req.changes[0].old_value, 60)
		self.assertEqual(req.old_grade, "C")
		self.assertEqual(grade_changes.approve(req.name), "Approved")
		b = self.pec(self.b)
		self.assertEqual((b.pec_finalgradecode, b.status), ("A", "Pass"))
		self.assertEqual(frappe.db.get_value("Grade Change Request", req.name, "new_grade"), "A")
		# Still frozen to everything else.
		doc = frappe.get_doc("Scheduled Course Roster", self.b.roster)
		doc.stdroster_grade[0].rawscore_card = 1
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_a_change_to_failing_takes_the_credits_back(self):
		before = frappe.db.get_value("Program Enrollment", self.b.pe, "totalcredits")
		grade_changes.approve(self.request(0).name)
		self.assertEqual(self.pec(self.b).status, "Fail")
		self.assertEqual(frappe.db.get_value("Program Enrollment", self.b.pe, "totalcredits"), before - 3)

	def test_an_unsent_grade_has_no_request(self):
		frappe.db.set_value("Scheduled Course Roster", self.b.roster, "active", 1)
		with self.assertRaises(frappe.ValidationError):
			self.request(100)

	def test_an_old_grade_needs_a_second_approver(self):
		_settings(grade_change_second_approver_role="System Manager", grade_change_second_approval_days=10)
		frappe.db.set_value(
			"Scheduled Course Roster", self.b.roster, "grades_sent_on", add_days(today(), -30)
		)
		req = self.request(100)
		self.assertEqual(req.needs_second_approval, 1)
		self.assertEqual(grade_changes.approve(req.name), "Open")
		# The same person can't give both approvals.
		with self.assertRaises(frappe.ValidationError):
			grade_changes.approve(req.name)
		frappe.db.set_value("Grade Change Request", req.name, "registrar_approved_by", "Guest")
		self.assertEqual(grade_changes.approve(req.name), "Approved")

	def test_a_rejection_changes_nothing(self):
		req = self.request(100)
		grade_changes.reject(req.name, "The key was right")
		self.assertEqual(self.pec(self.b).pec_finalgradecode, "C")


class TestRepeats(ADR119Case):
	def take_again(self, who, *scores):
		self.cs = self.section(frappe.db.get_value("Course Schedule", self.cs, "gradesc_cs"))
		retake = self.enrol(frappe._dict(name=who.student), self.cs)
		self.grade(retake, *scores)
		self.send()
		return retake

	def test_most_recent_attempt_counts(self):
		first_cs = self.cs
		self.grade(self.a, 95, 95)
		self.grade(self.b, 50, 50)
		self.send()
		self.take_again(self.b, 80, 80)
		first, second = self.pec(self.b, first_cs), self.pec(self.b)
		self.assertEqual((first.repeated, first.count_in_gpa, first.credits, first.attempt), (1, 0, 0, 1))
		self.assertEqual((second.repeated, second.attempt, second.status), (0, 2, "Pass"))
		self.assertEqual(frappe.db.get_value("Program Enrollment", self.b.pe, "totalcredits"), 3)

	def test_highest_attempt_counts_when_the_program_says_so(self):
		frappe.db.set_value("Program", self.program.name, "repeat_policy", repeats.HIGHEST)
		first_cs = self.cs
		self.grade(self.a, 95, 95)
		self.grade(self.b, 85, 85)
		self.send()
		self.take_again(self.b, 75, 75)
		self.assertEqual(self.pec(self.b, first_cs).repeated, 0)
		latest = self.pec(self.b)
		self.assertEqual((latest.repeated, latest.credits), (1, 0))
		self.assertEqual(frappe.db.get_value("Program Enrollment", self.b.pe, "totalcredits"), 3)

	def test_attempt_limit(self):
		frappe.db.set_value("Program", self.program.name, "max_attempts", 1)
		self.grade(self.a, 95, 95)
		self.grade(self.b, 50, 50)
		self.send()
		with patch("frappe.get_roles", return_value=["Student"]):
			with self.assertRaises(frappe.ValidationError):
				repeats.assert_attempts_left(self.b.pe, "ZZT-COURSE")
		repeats.assert_attempts_left(self.b.pe, "ZZT-COURSE")  # the registrar may


class TestTranscripts(ADR119Case):
	def setUp(self):
		super().setUp()
		self.grade(self.a, 95, 85)
		self.grade(self.b, 90)
		incompletes.mark_incomplete(self.b.roster, "reason")
		self.send()
		frappe.db.set_value("Program Enrollment", self.b.pe, "docstatus", 1)

	def test_data_marks_the_incomplete(self):
		rows = transcripts.data(self.b.student).enrollments[0].terms[0]["rows"]
		self.assertEqual((rows[0].grade, rows[0].marks), ("I", "I"))

	def test_a_hold_blocks_the_official_copy(self):
		frappe.get_doc(
			{
				"doctype": "Student Hold",
				"name": frappe.generate_hash(length=10),
				"parent": self.b.student,
				"parenttype": "Student",
				"parentfield": "student_holds",
				"hold_type": "Financial",
				"is_active": 1,
				"reason": "Fees owed",
			}
		).db_insert()
		with patch("seminary.seminary.comms.send"), _backend():
			req = frappe.get_doc(
				{"doctype": "Transcript Request", "student": self.b.student, "delivery": "Student"}
			).insert()
		self.assertEqual(frappe.db.get_value("Transcript Request", req.name, "status"), "On Hold")

	def test_issue_stores_the_hash_and_verifies(self):
		with patch("frappe.enqueue") as enqueue, patch("seminary.seminary.comms.send"), _backend():
			req = frappe.get_doc(
				{
					"doctype": "Transcript Request",
					"student": self.b.student,
					"delivery": "Email",
					"recipient_email": "admissions@example.com",
				}
			).insert()
		self.assertEqual(frappe.db.get_value("Transcript Request", req.name, "status"), "Ready")
		self.assertTrue(enqueue.called)
		content = _pdf_bytes()
		with patch.object(transcripts, "pdf", return_value=content), patch("seminary.seminary.comms.send"):
			transcripts.issue_job(req.name)
		doc = frappe.get_doc("Transcript Request", req.name)
		self.assertEqual(doc.status, "Issued")
		self.assertEqual(doc.pdf_sha256, hashlib.sha256(content).hexdigest())
		found = transcripts.verify(doc.verification_code.lower())
		self.assertEqual((found.student_name, found.sha256), (doc.student_name, doc.pdf_sha256))
		self.assertEqual(set(found), {"student_name", "issued_on", "sha256", "request"})
		self.assertIsNone(transcripts.verify("NOPE-NOPE-NOPE"))
		with self.assertRaises(frappe.PermissionError):
			transcripts.download(doc.verification_code, "wrong")
		transcripts.download(doc.verification_code, doc.download_key)
		self.assertEqual(frappe.local.response.filecontent, content)

	def test_an_unpaid_fee_waits_and_a_waiver_lets_it_go(self):
		with (
			_backend(
				charge_transcript_request=lambda name: ["CHG-9"],
				payment_status_for_transcript_request=lambda name: PaymentAggregate(paid_percent=0),
				waive_request_charges=lambda *a: [],
			),
			patch("frappe.enqueue"),
		):
			req = frappe.get_doc(
				{"doctype": "Transcript Request", "student": self.b.student, "delivery": "Student"}
			).insert()
			self.assertEqual(
				frappe.db.get_value("Transcript Request", req.name, "status"), "Awaiting Payment"
			)
			self.assertEqual(transcripts.waive_fee(req.name, "Alumni courtesy"), "Ready")

	def test_the_template_renders_both_uses(self):
		unofficial = transcripts.html(self.a.student)
		self.assertIn("UNOFFICIAL", unofficial)
		self.assertIn("ZZT", unofficial)
		req = frappe._dict(verification_code="ABCD-EFGH-JKLM")
		official = transcripts.html(self.a.student, official=True, request=req)
		self.assertNotIn("UNOFFICIAL", official)
		self.assertIn("ABCD-EFGH-JKLM", official)
		self.assertIn("/transcript-verify", official)


class TestLetterhead(IntegrationTestCase):
	def test_jinja_is_rendered_and_an_empty_size_dropped(self):
		from seminary.seminary.doctype.seminary_announcement.seminary_announcement import _render_letterhead

		html = _render_letterhead(
			'{% set c = doc.company %}<b>{{ c or "" }}</b><img src="/x.png" style="height: px;">'
		)
		self.assertNotIn("{%", html)
		self.assertNotIn("{{", html)
		self.assertNotIn("px;", html)
		self.assertNotIn("None", html)
		self.assertIn('<img src="/x.png"', html)

	def test_a_broken_template_still_prints_without_its_source(self):
		from seminary.seminary.doctype.seminary_announcement.seminary_announcement import _render_letterhead

		html = _render_letterhead("<p>Head</p>{% if %}{{ doc.nope( }}")
		self.assertEqual(html, "<p>Head</p>")
