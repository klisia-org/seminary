# Copyright (c) 2026, Murilo R. Melo and contributors
# See license.txt
"""decisions/122: the lesson library, shared questions and quizzes, required lessons."""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import library
from seminary.seminary.report.library_lesson_use import library_lesson_use as report
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_decisions107_content_release import _chapter, _lesson, _section


def _blocks(*types):
	return json.dumps(
		{
			"blocks": [
				{"type": t, "data": {"text": t, "quiz": "QZ-1"} if t == "quiz" else {"text": t}}
				for t in types
			]
		}
	)


def _course():
	doc = frappe.get_doc({"doctype": "Course", "name": fx.uid("C"), "course_name": fx.uid("Course")})
	doc.db_insert()
	return doc.name


def _program_with(course):
	program = frappe.get_doc({"doctype": "Program", "name": fx.uid("P"), "program_name": fx.uid("Program")})
	program.db_insert()
	frappe.get_doc(
		{
			"doctype": "Program Course",
			"name": fx.uid("PC"),
			"parent": program.name,
			"parenttype": "Program",
			"parentfield": "courses",
			"idx": 1,
			"course": course,
		}
	).db_insert()
	return program.name


def _term():
	doc = frappe.get_doc({"doctype": "Academic Term", "name": fx.uid("T"), "term_name": fx.uid("Term")})
	doc.db_insert()
	return doc.name


def _library_lesson(courses=(), **values):
	doc = frappe.get_doc(
		{
			"doctype": "Library Lesson",
			"title": fx.uid("AI policy"),
			"content": _blocks("paragraph", "header"),
			"courses": [{"course": c} for c in courses],
			**values,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def _lesson_refs(chapter):
	return library._chapter_lessons(chapter)


class LibraryCase(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.course = _course()
		self.term = _term()
		self.cs = _section(course=self.course, academic_term=self.term)
		self.ch1 = _chapter(self.cs, 1)
		self.l1 = _lesson(self.cs, self.ch1)
		self.ch2 = _chapter(self.cs, 2)
		self.lib = _library_lesson()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.library_lessons = {}
		super().tearDown()


class TestBlocks(IntegrationTestCase):
	def test_merged_content_is_library_then_activities(self):
		merged = json.loads(library.merged_content(_blocks("paragraph"), _blocks("quiz", "paragraph")))
		self.assertEqual([b["type"] for b in merged["blocks"]], ["paragraph", "quiz"])

	def test_nothing_to_merge_is_none(self):
		self.assertIsNone(library.merged_content(None, _blocks("paragraph")))


class TestLibraryLesson(LibraryCase):
	def test_refuses_activity_blocks(self):
		with self.assertRaises(frappe.ValidationError):
			_library_lesson(content=_blocks("paragraph", "quiz"))

	def test_title_change_reaches_placed_lessons(self):
		placed = library.place(self.lib.name, self.ch1)["lesson"]
		self.lib.title = "Renamed policy"
		self.lib.save()
		self.assertEqual(frappe.db.get_value("Course Lesson", placed, "lesson_title"), "Renamed policy")


class TestPlacing(LibraryCase):
	def test_place_at_end_and_start(self):
		end = library.place(self.lib.name, self.ch1)["lesson"]
		self.assertEqual(_lesson_refs(self.ch1), [self.l1, end])
		other = _library_lesson()
		start = library.place(other.name, self.ch1, at_start=1)["lesson"]
		self.assertEqual(_lesson_refs(self.ch1), [start, self.l1, end])

	def test_outline_reads_library_content(self):
		placed = library.place(self.lib.name, self.ch1)["lesson"]
		frappe.db.set_value("Course Lesson", placed, "content", _blocks("quiz"), update_modified=False)
		details = frappe.db.get_value(
			"Course Lesson",
			placed,
			["name", "content", "body", "library_lesson", "required_by"],
			as_dict=True,
		)
		library.overlay(details)
		types = [b["type"] for b in json.loads(details.content)["blocks"]]
		self.assertEqual(types, ["paragraph", "header", "quiz"])
		self.assertEqual(details.library["name"], self.lib.name)

	def test_library_edit_shows_everywhere(self):
		placed = library.place(self.lib.name, self.ch1)["lesson"]
		self.lib.content = _blocks("paragraph")
		self.lib.save()
		frappe.local.library_lessons = {}
		details = frappe.db.get_value(
			"Course Lesson", placed, ["name", "content", "library_lesson"], as_dict=True
		)
		library.overlay(details)
		self.assertEqual(len(json.loads(details.content)["blocks"]), 1)

	def test_placed_lesson_holds_only_activities(self):
		placed = frappe.get_doc("Course Lesson", library.place(self.lib.name, self.ch1)["lesson"])
		placed.content = _blocks("paragraph")
		with self.assertRaises(frappe.ValidationError):
			placed.save()

	def test_course_list_limits_placement(self):
		restricted = _library_lesson(courses=[_course()])
		with self.assertRaises(frappe.ValidationError):
			library.place(restricted.name, self.ch1)
		allowed = _library_lesson(courses=[self.course])
		self.assertTrue(library.place(allowed.name, self.ch1)["lesson"])


class TestDetachAndFreeze(LibraryCase):
	def test_detach_copies_content(self):
		placed = library.place(self.lib.name, self.ch1)["lesson"]
		library.detach(placed)
		doc = frappe.get_doc("Course Lesson", placed)
		self.assertIsNone(doc.library_lesson)
		self.assertEqual(doc.detached_from, self.lib.name)
		self.assertEqual(len(json.loads(doc.content)["blocks"]), 2)
		self.assertFalse(doc.frozen_at_close)

	def test_close_freezes_placed_lessons(self):
		placed = library.place(self.lib.name, self.ch1)["lesson"]
		section = frappe.get_doc("Course Schedule", self.cs)
		section.workflow_state = "Closed"
		with patch.object(type(section), "has_value_changed", return_value=True):
			library.freeze_on_close(section)
		doc = frappe.get_doc("Course Lesson", placed)
		self.assertIsNone(doc.library_lesson)
		self.assertTrue(doc.frozen_at_close)


class TestRequirements(LibraryCase):
	def requirement(self, **values):
		req = frappe.get_doc(
			{
				"doctype": "Library Lesson Requirement",
				"library_lesson": self.lib.name,
				"reason": "The school's new AI policy.",
				"programs": [{"program": _program_with(self.course)}],
				"academic_terms": [{"academic_term": self.term}],
				**values,
			}
		)
		req.insert(ignore_permissions=True)
		return req

	def required_lessons(self, req):
		return frappe.get_all("Course Lesson", {"required_by": req.name, "course_sc": self.cs}, pluck="name")

	def test_places_once_at_start(self):
		req = self.requirement()
		placed = self.required_lessons(req)
		self.assertEqual(len(placed), 1)
		self.assertEqual(_lesson_refs(self.ch1)[0], placed[0])
		req.reason = "Updated wording."
		req.save()
		self.assertEqual(len(self.required_lessons(req)), 1)

	def test_end_of_last_chapter(self):
		req = self.requirement(position="End of the last chapter")
		self.assertEqual(_lesson_refs(self.ch2), self.required_lessons(req))

	def test_other_term_is_left_alone(self):
		req = self.requirement(academic_terms=[{"academic_term": _term()}])
		self.assertEqual(self.required_lessons(req), [])

	def test_instructor_cant_detach_or_delete(self):
		req = self.requirement()
		lesson = self.required_lessons(req)[0]
		with patch.object(library, "_is_manager", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				library.detach(lesson)
			with self.assertRaises(frappe.ValidationError):
				frappe.get_doc("Course Lesson", lesson).delete(ignore_permissions=True)

	def test_deactivating_removes_unless_completed(self):
		req = self.requirement()
		lesson = self.required_lessons(req)[0]
		req.active = 0
		req.save()
		self.assertFalse(frappe.db.exists("Course Lesson", lesson))
		self.assertNotIn(lesson, _lesson_refs(self.ch1))

		req.active = 1
		req.save()
		lesson = self.required_lessons(req)[0]
		frappe.get_doc(
			{
				"doctype": "Course Schedule Progress",
				"course": self.cs,
				"chapter": self.ch1,
				"lesson": lesson,
				"member": "Administrator",
				"status": "Complete",
			}
		).insert(ignore_permissions=True, ignore_links=True, ignore_mandatory=True)
		req.active = 0
		req.save()
		self.assertTrue(frappe.db.exists("Course Lesson", lesson))
		self.assertFalse(frappe.db.get_value("Course Lesson", lesson, "required_by"))

	def test_new_chapter_receives_pending_requirement(self):
		empty = _section(course=self.course, academic_term=self.term)
		self.requirement()
		self.assertFalse(frappe.db.exists("Course Lesson", {"course_sc": empty}))
		chapter = frappe.get_doc(
			{"doctype": "Course Schedule Chapter", "coursesc": empty, "chapter_title": fx.uid("Week 1")}
		)
		chapter.insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Course Schedule Chapter Reference",
				"parent": empty,
				"parenttype": "Course Schedule",
				"parentfield": "chapters",
				"idx": 1,
				"chapter": chapter.name,
			}
		).insert(ignore_permissions=True)
		self.assertTrue(
			frappe.db.exists("Course Lesson", {"course_sc": empty, "library_lesson": self.lib.name})
		)

	def test_report_rows_and_missing(self):
		req = self.requirement()
		rows = report.data(frappe._dict(library_lesson=self.lib.name))
		self.assertEqual([r["kind"] for r in rows], ["Required"])
		self.assertEqual(rows[0]["state"], "Placed")
		empty = _section(course=self.course, academic_term=self.term)
		pairs = report.missing({"library_lesson": self.lib.name})
		self.assertIn((req.name, empty), [(r.name, cs) for r, cs in pairs])


class TestSharedQuizzes(LibraryCase):
	def test_shared_with_course_is_offered(self):
		other = _course()
		quiz = frappe.get_doc(
			{
				"doctype": "Quiz",
				"title": fx.uid("Shared quiz"),
				"course": other,
				"shared_with": [{"course": self.course}],
			}
		)
		quiz.insert(ignore_permissions=True, ignore_mandatory=True)
		own = frappe.get_doc({"doctype": "Quiz", "title": fx.uid("Other quiz"), "course": other})
		own.insert(ignore_permissions=True, ignore_mandatory=True)
		found = [r[0] for r in library.shared_query("Quiz", "", "name", 0, 50, {"course": self.course})]
		self.assertIn(quiz.name, found)
		self.assertNotIn(own.name, found)
