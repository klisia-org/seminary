# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/107: chapter release dates, prerequisites and per-student exceptions."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_to_date, get_datetime, getdate, now_datetime, today

from seminary.seminary import content_release as cr
from seminary.seminary.tests import cohort_fixtures as fx


def _section(**values):
	cs = frappe.get_doc(
		{
			"doctype": "Course Schedule",
			"name": fx.uid("CS"),
			"title": fx.uid("Section"),
			"workflow_state": "Open for Enrollment",
			"published": 1,
			"notify_on_release": 1,
			"c_datestart": add_days(today(), -3),
			"open_ended": 0,
			**values,
		}
	)
	cs.db_insert()
	return cs.name


def _chapter(cs, idx, **values):
	ch = frappe.get_doc(
		{
			"doctype": "Course Schedule Chapter",
			"name": fx.uid("CH"),
			"coursesc": cs,
			"chapter_title": fx.uid(f"Chapter {idx}"),
			"release_type": cr.ALWAYS_OPEN,
			**values,
		}
	)
	ch.db_insert()
	frappe.get_doc(
		{
			"doctype": "Course Schedule Chapter Reference",
			"name": fx.uid("CHR"),
			"parent": cs,
			"parenttype": "Course Schedule",
			"parentfield": "chapters",
			"idx": idx,
			"chapter": ch.name,
		}
	).db_insert()
	return ch.name


def _lesson(cs, chapter, idx=1):
	lesson = frappe.get_doc(
		{
			"doctype": "Course Lesson",
			"name": fx.uid("L"),
			"chapter": chapter,
			"course_sc": cs,
			"lesson_title": fx.uid("Lesson"),
			"body": "secret body",
		}
	)
	lesson.db_insert()
	frappe.get_doc(
		{
			"doctype": "Course Schedule Lesson Reference",
			"name": fx.uid("LR"),
			"parent": chapter,
			"parenttype": "Course Schedule Chapter",
			"parentfield": "lessons",
			"idx": idx,
			"lesson": lesson.name,
		}
	).db_insert()
	return lesson.name


def _prereq(parent, idx=1, **values):
	frappe.get_doc(
		{
			"doctype": "Chapter Prerequisite",
			"name": fx.uid("CP"),
			"parent": parent,
			"parenttype": "Course Schedule Chapter",
			"parentfield": "prerequisites",
			"idx": idx,
			**values,
		}
	).db_insert()


def _roster(cs, student, **values):
	doc = frappe.get_doc(
		{
			"doctype": "Scheduled Course Roster",
			"name": f"{cs}-{student.name}",
			"course_sc": cs,
			"student": student.name,
			"stuname_roster": student.name,
			"stuemail_rc": student.user,
			"active": 1,
			"audit_bool": 0,
			**values,
		}
	)
	doc.db_insert()
	return doc.name


def _quiz(passing=70):
	quiz = frappe.get_doc(
		{"doctype": "Quiz", "name": fx.uid("QZ"), "title": fx.uid("Quiz"), "passing_percentage": passing}
	)
	quiz.db_insert()
	return quiz.name


def _quiz_row(cs, quiz):
	row = frappe.get_doc(
		{
			"doctype": "Scheduled Course Assess Criteria",
			"name": fx.uid("SCAC"),
			"parent": cs,
			"parenttype": "Course Schedule",
			"parentfield": "courseassescrit_sc",
			"title": fx.uid("Quiz row"),
			"type": "Quiz",
			"quiz": quiz,
			"weight_scac": 100,
		}
	)
	row.db_insert()
	return row.name


def _quiz_submission(cs, quiz, member, percentage):
	frappe.get_doc(
		{
			"doctype": "Quiz Submission",
			"name": fx.uid("QS"),
			"course": cs,
			"quiz": quiz,
			"member": member,
			"percentage": percentage,
		}
	).db_insert()


def _complete(cs, chapter, lesson, member):
	frappe.get_doc(
		{
			"doctype": "Course Schedule Progress",
			"course": cs,
			"chapter": chapter,
			"lesson": lesson,
			"member": member,
			"status": "Complete",
		}
	).insert(ignore_permissions=True, ignore_links=True, ignore_mandatory=True)


def _override(cs, chapter, student, **values):
	frappe.get_doc(
		{
			"doctype": "Student Chapter Release Override",
			"name": fx.uid("SCRO"),
			"course_schedule": cs,
			"chapter": chapter,
			"student": student,
			"reason": "Accommodation",
			**values,
		}
	).db_insert()


class Decisions107Case(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.student = fx.make_student()
		self.cs = _section()
		self.ch1 = _chapter(self.cs, 1)
		self.l1 = _lesson(self.cs, self.ch1)
		self.ch2 = _chapter(self.cs, 2)
		self.l2 = _lesson(self.cs, self.ch2)
		self.roster = _roster(self.cs, self.student)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def state(self, chapter, at=None):
		return cr.visible_outline(self.roster, at=at)["chapters"][chapter]

	def set_chapter(self, chapter, **values):
		frappe.db.set_value("Course Schedule Chapter", chapter, values, update_modified=False)


class TestReleaseDates(Decisions107Case):
	def test_always_open_is_open(self):
		self.assertFalse(self.state(self.ch2)["locked"])

	def test_future_date_locks_with_its_date(self):
		self.set_chapter(self.ch2, release_type=cr.ON_A_DATE, release_on=add_days(now_datetime(), 2))
		state = self.state(self.ch2)
		self.assertTrue(state["locked"])
		self.assertTrue(state["activities_locked"])
		self.assertTrue(state["reasons"][0].startswith("Opens"))
		self.assertIsNotNone(state["opens_at"])

	def test_past_date_is_open(self):
		self.set_chapter(self.ch2, release_type=cr.ON_A_DATE, release_on=add_days(now_datetime(), -1))
		self.assertFalse(self.state(self.ch2)["locked"])

	def test_days_after_start_counts_from_section_start(self):
		# Started three days ago.
		self.set_chapter(self.ch2, release_type=cr.DAYS_AFTER_START, release_offset_days=5)
		self.assertTrue(self.state(self.ch2)["locked"])
		self.set_chapter(self.ch2, release_offset_days=2)
		self.assertFalse(self.state(self.ch2)["locked"])

	def test_open_ended_counts_from_enrolment(self):
		cs = _section(open_ended=1, c_datestart=add_days(today(), -100))
		ch = _chapter(cs, 1, release_type=cr.DAYS_AFTER_START, release_offset_days=5)
		roster = _roster(cs, self.student)
		# The roster row was created just now, so five days from enrolment
		# has not passed although the section began long ago.
		self.assertTrue(cr.visible_outline(roster)["chapters"][ch]["locked"])
		later = add_days(now_datetime(), 6)
		self.assertFalse(cr.visible_outline(roster, at=later)["chapters"][ch]["locked"])


class TestPrerequisites(Decisions107Case):
	def test_complete_chapter(self):
		_prereq(self.ch2, kind=cr.COMPLETE_CHAPTER, chapter=self.ch1)
		state = self.state(self.ch2)
		self.assertTrue(state["locked"])
		self.assertIn("first", state["reason"])
		_complete(self.cs, self.ch1, self.l1, self.student.user)
		self.assertFalse(self.state(self.ch2)["locked"])

	def test_pass_quiz_uses_the_quiz_pass_mark(self):
		quiz = _quiz(passing=70)
		_quiz_row(self.cs, quiz)
		_prereq(self.ch2, kind=cr.PASS_QUIZ, quiz=quiz)
		self.assertTrue(self.state(self.ch2)["locked"])
		_quiz_submission(self.cs, quiz, self.student.user, 60)
		self.assertTrue(self.state(self.ch2)["locked"])
		_quiz_submission(self.cs, quiz, self.student.user, 80)
		self.assertFalse(self.state(self.ch2)["locked"])

	def test_pass_quiz_row_minimum_wins(self):
		quiz = _quiz(passing=50)
		_quiz_row(self.cs, quiz)
		_prereq(self.ch2, kind=cr.PASS_QUIZ, quiz=quiz, min_percentage=90)
		_quiz_submission(self.cs, quiz, self.student.user, 80)
		state = self.state(self.ch2)
		self.assertTrue(state["locked"])
		self.assertIn("90%", state["reason"])

	def test_every_row_must_hold_and_every_reason_shows(self):
		quiz = _quiz()
		_quiz_row(self.cs, quiz)
		_prereq(self.ch2, 1, kind=cr.COMPLETE_CHAPTER, chapter=self.ch1)
		_prereq(self.ch2, 2, kind=cr.PASS_QUIZ, quiz=quiz)
		self.set_chapter(self.ch2, release_type=cr.ON_A_DATE, release_on=add_days(now_datetime(), 1))
		self.assertEqual(len(self.state(self.ch2)["reasons"]), 3)
		_complete(self.cs, self.ch1, self.l1, self.student.user)
		self.assertEqual(len(self.state(self.ch2)["reasons"]), 2)


class TestOverrides(Decisions107Case):
	def test_open_from_moves_the_date_either_way(self):
		self.set_chapter(self.ch2, release_type=cr.ON_A_DATE, release_on=add_days(now_datetime(), 5))
		_override(self.cs, self.ch2, self.student.name, open_from=add_days(now_datetime(), -1))
		self.assertFalse(self.state(self.ch2)["locked"])

	def test_later_open_from_locks_an_open_chapter(self):
		_override(self.cs, self.ch1, self.student.name, open_from=add_days(now_datetime(), 1))
		self.assertTrue(self.state(self.ch1)["locked"])

	def test_waive_lifts_prerequisites_not_the_date(self):
		_prereq(self.ch2, kind=cr.COMPLETE_CHAPTER, chapter=self.ch1)
		_override(self.cs, self.ch2, self.student.name, waive_prerequisites=1)
		self.assertFalse(self.state(self.ch2)["locked"])
		self.set_chapter(self.ch2, release_type=cr.ON_A_DATE, release_on=add_days(now_datetime(), 1))
		self.assertTrue(self.state(self.ch2)["locked"])

	def test_waive_lifts_the_cbe_lock(self):
		cbe_state = {
			"mode": "Chapter unlocks after previous competency self-assessed",
			"gated": True,
			"chapters": {
				self.ch2: {
					"locked": True,
					"activities_locked": True,
					"reason": "Opens once you have submitted your self-assessment for X.",
					"unlock_competency": "COMP",
				}
			},
		}
		with patch("seminary.seminary.cbe.competency_locks", return_value=cbe_state):
			self.assertTrue(self.state(self.ch2)["locked"])
			self.assertEqual(self.state(self.ch2)["unlock_competency"], "COMP")
			_override(self.cs, self.ch2, self.student.name, waive_prerequisites=1)
			self.assertFalse(self.state(self.ch2)["locked"])

	def test_override_needs_a_reason_and_a_change(self):
		doc = frappe.get_doc(
			{
				"doctype": "Student Chapter Release Override",
				"course_schedule": self.cs,
				"chapter": self.ch2,
				"student": self.student.name,
				"reason": "x",
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()


class TestEnforcement(Decisions107Case):
	def setUp(self):
		super().setUp()
		self.set_chapter(self.ch2, release_type=cr.ON_A_DATE, release_on=add_days(now_datetime(), 2))

	def test_staff_are_never_locked(self):
		self.assertIsNone(cr.outline_for_user(self.cs, "Administrator"))

	def test_student_outline_drops_locked_content(self):
		from seminary.seminary.utils import get_course_outline, get_lesson

		frappe.set_user(self.student.user)
		outline = {c.name: c for c in get_course_outline(self.cs)}
		self.assertTrue(outline[self.ch2].release["locked"])
		self.assertNotIn("body", outline[self.ch2].lessons[0])
		self.assertTrue(outline[self.ch2].lessons[0].lesson_title)
		self.assertEqual(outline[self.ch1].lessons[0].body, "secret body")

		lesson = get_lesson(self.cs, 2, 1)
		self.assertEqual(lesson.locked, 1)
		self.assertNotIn("body", lesson)
		self.assertEqual(get_lesson(self.cs, 1, 1).body, "secret body")

	def test_locked_lesson_cannot_be_completed(self):
		from seminary.seminary.doctype.course_lesson.course_lesson import save_progress

		frappe.set_user(self.student.user)
		# Naming an open chapter does not help: the lesson's own chapter counts.
		self.assertEqual(save_progress(self.l2, self.ch1, self.cs), 0)
		self.assertFalse(frappe.db.exists("Course Schedule Progress", {"lesson": self.l2}))

	def test_submission_in_a_locked_chapter_is_refused(self):
		quiz = _quiz()
		row = _quiz_row(self.cs, quiz)
		frappe.db.set_value("Course Lesson", self.l2, "assessment_criteria_quiz", row)
		doc = frappe._dict(course=self.cs, course_assess=row, student=self.student.name)
		with self.assertRaises(frappe.PermissionError):
			cr.assert_activity_unlocked(doc)
		self.set_chapter(self.ch2, release_on=add_days(now_datetime(), -1))
		cr.assert_activity_unlocked(doc)


class TestChapterValidation(Decisions107Case):
	def chapter_doc(self, name, rows, **values):
		doc = frappe.get_doc("Course Schedule Chapter", name)
		doc.update(values)
		doc.set("prerequisites", rows)
		return doc

	def test_loop_is_refused(self):
		_prereq(self.ch1, kind=cr.COMPLETE_CHAPTER, chapter=self.ch2)
		doc = self.chapter_doc(self.ch2, [{"kind": cr.COMPLETE_CHAPTER, "chapter": self.ch1}])
		with self.assertRaises(frappe.ValidationError):
			cr.validate_chapter(doc)

	def test_own_prerequisite_is_refused(self):
		doc = self.chapter_doc(self.ch2, [{"kind": cr.COMPLETE_CHAPTER, "chapter": self.ch2}])
		with self.assertRaises(frappe.ValidationError):
			cr.validate_chapter(doc)

	def test_other_section_chapter_is_refused(self):
		other = _chapter(_section(), 1)
		doc = self.chapter_doc(self.ch2, [{"kind": cr.COMPLETE_CHAPTER, "chapter": other}])
		with self.assertRaises(frappe.ValidationError):
			cr.validate_chapter(doc)

	def test_quiz_must_belong_to_the_section(self):
		doc = self.chapter_doc(self.ch2, [{"kind": cr.PASS_QUIZ, "quiz": _quiz()}])
		with self.assertRaises(frappe.ValidationError):
			cr.validate_chapter(doc)

	def test_date_required_for_on_a_date(self):
		doc = self.chapter_doc(self.ch2, [], release_type=cr.ON_A_DATE, release_on=None)
		with self.assertRaises(frappe.ValidationError):
			cr.validate_chapter(doc)

	def test_unused_release_fields_are_cleared(self):
		doc = self.chapter_doc(
			self.ch2, [], release_type=cr.DAYS_AFTER_START, release_offset_days=3, release_on=now_datetime()
		)
		cr.validate_chapter(doc)
		self.assertIsNone(doc.release_on)


class TestCopying(Decisions107Case):
	def test_fixed_date_moves_with_the_start(self):
		target = frappe._dict()
		src = frappe._dict(release_type=cr.ON_A_DATE, release_on="2026-02-10 09:00:00", release_offset_days=0)
		cr.copy_release(src, target, cr.start_shift("2026-02-02", "2026-08-03"))
		self.assertEqual(get_datetime(target.release_on), get_datetime("2026-08-11 09:00:00"))
		self.assertEqual(target.release_type, cr.ON_A_DATE)

	def test_prerequisites_follow_the_copies_and_drop_the_rest(self):
		cs = _section()
		new1 = _chapter(cs, 1)
		new2 = _chapter(cs, 2)
		quiz = _quiz()
		rows = [
			{"kind": cr.COMPLETE_CHAPTER, "chapter": self.ch1},
			{"kind": cr.COMPLETE_CHAPTER, "chapter": "not-copied"},
			{"kind": cr.PASS_QUIZ, "quiz": quiz, "min_percentage": 80},
			{"kind": cr.PASS_QUIZ, "quiz": "missing"},
		]
		dropped = cr.insert_prerequisites(new2, rows, {self.ch1: new1}, lambda q: q if q == quiz else None)
		self.assertEqual(len(dropped), 2)
		saved = frappe.get_all(
			"Chapter Prerequisite",
			filters={"parent": new2},
			fields=["kind", "chapter", "quiz", "min_percentage"],
			order_by="idx asc",
		)
		self.assertEqual(
			[(r.kind, r.chapter, r.quiz) for r in saved],
			[
				(cr.COMPLETE_CHAPTER, new1, None),
				(cr.PASS_QUIZ, None, quiz),
			],
		)
		self.assertEqual(saved[1].min_percentage, 80)


class TestNotices(Decisions107Case):
	def test_notice_once_released_and_open(self):
		self.set_chapter(
			self.ch2, release_type=cr.ON_A_DATE, release_on=add_to_date(now_datetime(), hours=-1)
		)
		person = frappe.db.get_value("Student", self.student.name, "person")
		with patch("seminary.seminary.comms.send_message") as send:
			cr.notify_opened_chapters()
		keys = [c.kwargs["dedupe_key"] for c in send.call_args_list if c.kwargs.get("person") == person]
		self.assertEqual(keys, [f"chapter-open-{self.roster}-{self.ch2}"])

	def test_no_notice_while_a_prerequisite_holds(self):
		self.set_chapter(
			self.ch2, release_type=cr.ON_A_DATE, release_on=add_to_date(now_datetime(), hours=-1)
		)
		_prereq(self.ch2, kind=cr.COMPLETE_CHAPTER, chapter=self.ch1)
		with patch("seminary.seminary.comms.send_message") as send:
			cr.notify_opened_chapters()
		self.assertFalse([c for c in send.call_args_list if self.ch2 in c.kwargs["dedupe_key"]])

	def test_old_releases_and_switched_off_sections_send_nothing(self):
		self.set_chapter(self.ch2, release_type=cr.ON_A_DATE, release_on=add_days(now_datetime(), -30))
		_chapter(self.cs, 3, release_type=cr.ON_A_DATE, release_on=add_to_date(now_datetime(), hours=-1))
		frappe.db.set_value("Course Schedule", self.cs, "notify_on_release", 0)
		with patch("seminary.seminary.comms.send_message") as send:
			cr.notify_opened_chapters()
		self.assertFalse([c for c in send.call_args_list if self.cs in c.kwargs["reference_name"]])
		frappe.db.set_value("Course Schedule", self.cs, "notify_on_release", 1)
		with patch("seminary.seminary.comms.send_message") as send:
			cr.notify_opened_chapters()
		keys = [c.kwargs["dedupe_key"] for c in send.call_args_list if c.kwargs["reference_name"] == self.cs]
		self.assertEqual(len(keys), 1)
		self.assertNotIn(self.ch2, keys[0])

	def test_getdate_anchor(self):
		# A section with no start date never date-locks a days-after-start chapter.
		cs = _section(c_datestart=None)
		ch = _chapter(cs, 1, release_type=cr.DAYS_AFTER_START, release_offset_days=3)
		roster = _roster(cs, self.student)
		self.assertFalse(cr.visible_outline(roster)["chapters"][ch]["locked"])
		self.assertTrue(getdate(today()))
