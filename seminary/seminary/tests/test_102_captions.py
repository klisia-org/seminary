# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""102 §6: lesson captions are WebVTT files, and they reach the lesson player."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.tests import cohort_fixtures as fx

VTT = "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nIn the beginning\n"


class TestLessonCaptions(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.files = []
		self.records = []

	def tearDown(self):
		frappe.set_user("Administrator")
		for doctype, name in reversed(self.records):
			frappe.db.delete(doctype, {"name": name})
		frappe.db.delete("Course Lesson Caption", {"parent": ["like", "ZZT%"]})
		for name in self.files:
			frappe.delete_doc("File", name, force=True, ignore_permissions=True)

	def _file(self, name, content):
		doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"zzt-{frappe.generate_hash(length=6)}-{name}",
				"content": content,
				"is_private": 1,
			}
		).insert(ignore_permissions=True)
		self.files.append(doc.name)
		return doc.file_url

	def _lesson_with(self, url):
		lesson = frappe.new_doc("Course Lesson")
		lesson.append("captions", {"language": "en", "caption_file": url})
		return lesson

	def test_a_webvtt_file_is_accepted(self):
		self._lesson_with(self._file("captions.vtt", VTT)).validate_captions()

	def test_a_byte_order_mark_is_allowed(self):
		self._lesson_with(self._file("bom.vtt", "﻿" + VTT)).validate_captions()

	def test_another_extension_is_refused(self):
		url = self._file("captions.srt", "1\n00:00:00,000 --> 00:00:02,000\nIn the beginning\n")
		with self.assertRaises(frappe.ValidationError) as caught:
			self._lesson_with(url).validate_captions()
		self.assertIn(".vtt", str(caught.exception))

	def test_a_vtt_name_without_the_signature_is_refused(self):
		url = self._file("fake.vtt", "00:00:00.000 --> 00:00:02.000\nno header\n")
		with self.assertRaises(frappe.ValidationError) as caught:
			self._lesson_with(url).validate_captions()
		self.assertIn("WEBVTT", str(caught.exception))

	def test_captions_reach_the_lesson_api(self):
		from seminary.seminary.utils import get_lesson, get_lesson_creation_details

		url = self._file("lesson.vtt", VTT)
		transcript = self._file("lesson-transcript.txt", "In the beginning")
		cs, chapter, lesson = fx.uid("CS"), fx.uid("CH"), fx.uid("LSN")
		frappe.get_doc({"doctype": "Course Schedule", "name": cs}).db_insert()
		self.records.append(("Course Schedule", cs))
		frappe.get_doc(
			{"doctype": "Course Schedule Chapter", "name": chapter, "chapter_title": "One", "course": cs}
		).db_insert()
		self.records.append(("Course Schedule Chapter", chapter))
		for doctype, parent, parenttype, field, values in (
			("Course Schedule Chapter Reference", cs, "Course Schedule", "chapters", {"chapter": chapter}),
			(
				"Course Schedule Lesson Reference",
				chapter,
				"Course Schedule Chapter",
				"lessons",
				{"lesson": lesson},
			),
		):
			row = frappe.get_doc(
				{
					"doctype": doctype,
					"name": fx.uid("REF"),
					"parent": parent,
					"parenttype": parenttype,
					"parentfield": field,
					"idx": 1,
					**values,
				}
			)
			row.db_insert()
			self.records.append((doctype, row.name))
		doc = frappe.get_doc(
			{
				"doctype": "Course Lesson",
				"name": lesson,
				"lesson_title": "Genesis 1",
				"course_sc": cs,
				"chapter": chapter,
				"transcript": transcript,
				"captions": [{"language": "en", "label": "English", "caption_file": url}],
			}
		)
		doc.db_insert()
		for row in doc.captions:
			row.db_insert()
		self.records.append(("Course Lesson", lesson))

		data = get_lesson(cs, 1, 1)
		self.assertEqual(data.transcript, transcript)
		self.assertEqual(data.captions, [{"language": "en", "label": "English", "file": url}])

		# The lesson form gets the rows to edit and save back.
		details = get_lesson_creation_details(cs, 1, 1)
		self.assertEqual(
			[(r.language, r.caption_file) for r in details["lesson"].captions],
			[("en", url)],
		)
		self.assertEqual(details["lesson"].transcript, transcript)

	def test_a_blank_label_takes_the_language_name(self):
		from seminary.seminary.doctype.course_lesson.course_lesson import lesson_captions

		url = self._file("label.vtt", VTT)
		lesson = fx.uid("LSN")
		doc = frappe.get_doc(
			{
				"doctype": "Course Lesson",
				"name": lesson,
				"lesson_title": "Genesis 2",
				"captions": [{"language": "en", "caption_file": url}],
			}
		)
		doc.db_insert()
		for row in doc.captions:
			row.db_insert()
		self.records.append(("Course Lesson", lesson))
		[track] = lesson_captions(lesson)
		self.assertTrue(track["label"])
