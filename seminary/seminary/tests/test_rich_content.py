# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Rich content and media (decision 109): what the sanitiser keeps, and lesson history."""

import json
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from seminary.seminary import lesson_history
from seminary.seminary.content_safety import clean_rich

EMBED = "https://www.youtube.com/embed/abc123"


def figure(url, title="Lecture 3"):
	return f'<figure data-embed="{url}" data-align="center"><a href="{url}">{title}</a></figure>'


class TestRichTextSanitiser(IntegrationTestCase):
	def test_an_embed_on_another_site_keeps_its_address(self):
		out = clean_rich(figure(EMBED))
		self.assertIn(f'data-embed="{EMBED}"', out)
		self.assertIn(">Lecture 3</a>", out)

	def test_an_embed_of_a_script_or_this_site_loses_its_address(self):
		for url in ("javascript:alert(1)", frappe.utils.get_url("/files/x.pdf"), "/files/x.pdf"):
			with self.subTest(url=url):
				out = clean_rich(figure(url))
				self.assertNotIn("data-embed", out)
				self.assertIn("<figure", out)

	def test_an_iframe_is_still_removed(self):
		self.assertNotIn("<iframe", clean_rich(f'<p>x</p><iframe src="{EMBED}"></iframe>'))

	def test_a_video_keeps_its_captions_list_and_text_keeps_its_direction(self):
		captions = json.dumps([{"src": "/files/a.vtt", "srclang": "pt-BR", "label": "Português"}])
		html = f'<video src="/files/a.mp4" data-captions=\'{captions}\'></video><p dir="auto">שלום</p>'
		out = clean_rich(html)
		self.assertIn("data-captions=", out)
		self.assertIn("/files/a.vtt", out)
		self.assertIn('<p dir="auto">', out)


class TestLessonHistory(IntegrationTestCase):
	"""Version rows for a lesson name no real lesson has, a new one per test: nothing on
	the site is read or changed, and the rows are rolled back with the test class."""

	def setUp(self):
		self.lesson = f"TEST-109-{frappe.generate_hash(length=8)}"
		patcher = patch.object(lesson_history, "_require_edit", lambda lesson: None)
		patcher.start()
		self.addCleanup(patcher.stop)
		self.start = now_datetime() - timedelta(days=1)

	def _save(self, minutes, owner, **changed):
		data = {
			"added": [],
			"changed": [[field, old, new] for field, (old, new) in changed.items()],
			"removed": [],
			"row_changed": [],
		}
		doc = frappe.get_doc(
			{
				"doctype": "Version",
				"ref_doctype": "Course Lesson",
				"docname": self.lesson,
				"data": json.dumps(data),
			}
		).insert(ignore_permissions=True)
		at = self.start + timedelta(minutes=minutes)
		frappe.db.set_value("Version", doc.name, {"creation": at, "owner": owner}, update_modified=False)
		return doc.name

	def test_saves_close_together_by_one_person_are_one_session(self):
		self._save(0, "a@example.com", content=("", "c1"))
		self._save(5, "a@example.com", content=("c1", "c2"))
		third = self._save(10, "a@example.com", content=("c2", "c3"))
		fourth = self._save(60, "a@example.com", content=("c3", "c4"))
		fifth = self._save(61, "b@example.com", content=("c4", "c5"))
		sessions = lesson_history.get_lesson_history(self.lesson)
		self.assertEqual([s["version"] for s in sessions], [fifth, fourth, third])
		self.assertEqual(sessions[-1]["saves"], 3)
		self.assertTrue(sessions[0]["current"])
		self.assertFalse(sessions[1]["current"])

	def test_a_long_sitting_is_split_into_half_hours(self):
		for minute in range(0, 70, 10):
			self._save(minute, "a@example.com", content=(f"c{minute}", f"c{minute + 10}"))
		sessions = lesson_history.get_lesson_history(self.lesson)
		# 0-30, 40-60: a new entry once a session would pass half an hour.
		self.assertEqual([s["saves"] for s in sessions], [3, 4])

	def test_a_version_holds_each_field_as_it_was_then(self):
		first = self._save(0, "a@example.com", content=("", "c1"), instructor_content=("", "n1"))
		second = self._save(30, "a@example.com", content=("c1", "c2"))
		self._save(60, "a@example.com", instructor_content=("n1", "n2"))
		v = lesson_history.get_lesson_version(self.lesson, second)
		# content changed at this version; the notes last changed before it.
		self.assertEqual((v["content"], v["instructor_content"]), ("c2", "n1"))
		v = lesson_history.get_lesson_version(self.lesson, first)
		self.assertEqual((v["content"], v["instructor_content"]), ("c1", "n1"))

	def test_a_version_from_another_lesson_is_refused(self):
		self._save(0, "a@example.com", content=("", "c1"))
		with self.assertRaises(frappe.DoesNotExistError):
			lesson_history.get_lesson_version(self.lesson, "not-a-version")

	def test_other_saves_of_the_lesson_are_not_listed(self):
		self._save(0, "a@example.com", content=("", "c1"))
		# A change to another field only (the title) is no version of the content.
		doc = frappe.get_doc(
			{
				"doctype": "Version",
				"ref_doctype": "Course Lesson",
				"docname": self.lesson,
				"data": json.dumps({"changed": [["title", "a", "b"]]}),
			}
		).insert(ignore_permissions=True)
		listed = [s["version"] for s in lesson_history.get_lesson_history(self.lesson)]
		self.assertNotIn(doc.name, listed)


class TestLessonHistoryPermission(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_someone_who_cant_edit_the_lesson_is_refused(self):
		lesson = frappe.get_all("Course Lesson", pluck="name", limit=1)
		if not lesson:
			self.skipTest("no lesson on this site")
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			lesson_history.get_lesson_history(lesson[0])
