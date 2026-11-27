# Copyright (c) 2026, Murilo R. Melo and contributors
# See license.txt
"""privatedocs p028: slots another installed app fills, and course-pack extras."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import extensions
from seminary.seminary.course_pack.export import build_pack_bytes
from seminary.seminary.course_pack.import_ import import_pack_from_bytes
from seminary.seminary.course_pack.test_course_pack import TestCoursePackRoundTrip
from seminary.seminary.tests.test_decisions107_content_release import _chapter, _lesson, _section

HERE = "seminary.seminary.tests.test_p028_extensions"
SEEN = {}


def _tabs(course_schedule, access):
	return [
		{"key": "syllabus", "label": "Syllabus", "order": 20},
		{"key": "readings", "label": "Readings", "order": 10},
	]


def _lesson_panels(lesson):
	return [{"title": "Read first", "html": "<p>Romans 1</p>"}, {"title": "", "html": ""}]


def _notice(course_schedule):
	return {"title": "Syllabus", "html": "<p>For reference only</p>"}


def _export(course_schedule):
	return {"readings.json": '{"rows": 1}', "../escape": "x"}


def _import(course_schedule, files, name_map):
	SEEN["files"] = files
	SEEN["lessons"] = name_map["lessons"]


def _hooks(mapping):
	real = frappe.get_hooks

	def fake(hook=None, *args, **kwargs):
		if hook in mapping:
			return mapping[hook]
		return real(hook, *args, **kwargs)

	return patch.object(frappe, "get_hooks", side_effect=fake)


class TestSlots(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.cs = _section()
		self.chapter = _chapter(self.cs, 1)
		self.lesson = _lesson(self.cs, self.chapter)

	def test_nothing_registered_is_empty(self):
		with _hooks(
			{"seminary_course_tabs": [], "seminary_lesson_panels": [], "seminary_enrollment_notice": []}
		):
			self.assertEqual(extensions.course_tabs(self.cs), [])
			self.assertEqual(extensions.lesson_panels(self.lesson), [])
			self.assertIsNone(extensions.enrollment_notice(self.cs))

	def test_tabs_sorted_by_order(self):
		with _hooks({"seminary_course_tabs": [f"{HERE}._tabs"]}):
			self.assertEqual([t["key"] for t in extensions.course_tabs(self.cs)], ["readings", "syllabus"])

	def test_lesson_panels_drop_empty_rows(self):
		with _hooks({"seminary_lesson_panels": [f"{HERE}._lesson_panels"]}):
			self.assertEqual(
				extensions.lesson_panels(self.lesson), [{"title": "Read first", "html": "<p>Romans 1</p>"}]
			)

	def test_enrollment_notice(self):
		with _hooks({"seminary_enrollment_notice": [f"{HERE}._notice"]}):
			self.assertEqual(extensions.enrollment_notice(self.cs)["title"], "Syllabus")


class TestPackExtras(TestCoursePackRoundTrip):
	test_round_trip = None

	def test_extras_travel_and_stay_inside_their_folder(self):
		with _hooks(
			{"course_pack_exported": [f"{HERE}._export"], "course_pack_imported": [f"{HERE}._import"]}
		):
			_filename, content = build_pack_bytes(self.cs)
			SEEN.clear()
			import_pack_from_bytes(
				content,
				target_mode="new",
				course_name="CP Extras Course",
				academic_term=self.term,
				section="X",
			)
		self.assertEqual(SEEN["files"], {"readings.json": b'{"rows": 1}'})
		self.assertIn(self.lesson, SEEN["lessons"])
