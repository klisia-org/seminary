# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p008 browser pass: the two errors a Student met on a lesson page.

Both are pre-existing and unrelated to content safety, but they are what the
p008 browser pass surfaced, so they are pinned here.

* ``render_html`` concatenated ``Course Lesson.body``, which is empty on every
  lesson written in the block editor -- ``get_lesson`` answered 500 and the page
  never opened.
* ``save_progress`` recorded progress with a full ``Scheduled Course Roster``
  save. p007 F1 took Student write off that doctype (a student must not edit
  their own grade, active flag or program), so every lesson view raised
  PermissionError. The fix writes the one derived field; the rest of the row
  stays closed, which is the half this module guards against a re-grant.
"""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.doctype.course_lesson.course_lesson import save_progress
from seminary.seminary.tests.test_p007_docperms import (
    _any_course_schedule,
    _roster,
    _student_for,
)
from seminary.seminary.tests.test_p006_api import _make_user
from seminary.seminary.utils import render_html

PREFIX = "ZZT-p008-lesson"


class TestP008RenderHtml(IntegrationTestCase):
    """Nothing on a lesson is required to be set."""

    def test_a_lesson_with_no_legacy_body_renders(self):
        lesson = frappe._dict(youtube=None, quiz_id=None, body=None, question=None)
        self.assertEqual(render_html(lesson), "")

    def test_the_legacy_macros_still_wrap_the_body(self):
        lesson = frappe._dict(
            youtube="https://youtu.be/abc123",
            quiz_id="ZZT-quiz",
            body="<p>text</p>",
            question=None,
        )
        self.assertEqual(
            render_html(lesson),
            "{{ YouTubeVideo('abc123') }}<p>text</p>{{ Quiz('ZZT-quiz') }}",
        )

    def test_an_assignment_with_no_file_type_renders(self):
        lesson = frappe._dict(
            youtube=None, quiz_id=None, body=None, question="Q1", file_type=None
        )
        self.assertEqual(render_html(lesson), "{{ Assignment('Q1-') }}")


class TestP008SaveProgress(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = _make_user("Student", "p008-progress")
        cls.student = _student_for(cls.user, "progress")
        cs, _other = _any_course_schedule()
        cls.course = cs.name
        cls.roster = _roster(cls.course, cls.student, cls.user)

        cls.chapter = frappe.get_doc(
            {
                "doctype": "Course Schedule Chapter",
                "chapter_title": PREFIX,
                "course_sc": cls.course,
            }
        )
        cls.chapter.flags.ignore_permissions = True
        cls.chapter.insert(ignore_mandatory=True)

        cls.lesson = frappe.get_doc(
            {
                "doctype": "Course Lesson",
                "lesson_title": PREFIX,
                "chapter": cls.chapter.name,
                "course_sc": cls.course,
                # no body and no content: the block-editor shape that broke
                # render_html
            }
        )
        cls.lesson.flags.ignore_permissions = True
        cls.lesson.insert(ignore_mandatory=True)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_a_student_records_progress_on_their_own_roster_row(self):
        frappe.db.set_value("Scheduled Course Roster", self.roster, "progress", 0)
        frappe.set_user(self.user)
        # no exception: this raised PermissionError for every student
        save_progress(self.lesson.name, self.chapter.name, self.course)
        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value(
                "Scheduled Course Roster", self.roster, "current_lesson"
            ),
            self.lesson.name,
        )

    def test_the_rest_of_the_roster_row_stays_closed_to_the_student(self):
        """The reason save_progress may not simply pass ignore_permissions."""
        frappe.set_user(self.user)
        self.assertFalse(
            frappe.has_permission(
                "Scheduled Course Roster", "write", doc=self.roster, user=self.user
            )
        )
        doc = frappe.get_doc("Scheduled Course Roster", self.roster)
        doc.active = 0
        with self.assertRaises(frappe.PermissionError):
            doc.save()
