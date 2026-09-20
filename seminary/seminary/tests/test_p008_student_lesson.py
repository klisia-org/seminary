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
from seminary.seminary.tests.student_write_sweep import sweep
from seminary.seminary.utils import render_html

PREFIX = "ZZT-p008-lesson"

# Every (endpoint, doctype) pair the sweep reports today, each read and judged.
# The list is the ratchet: a new pair is a student path that p007's DocPerms may
# have closed, and has to be looked at before the branch is green. Shrinking it
# is always allowed.
KNOWN_SWEEP_PAIRS = {
    # The write is behind `doc.flags.ignore_permissions = True` set on another
    # line or in a branch, which the sweep's coarse scan does not follow.
    ("seminary.seminary.api.course_enroll", "Program Enrollment"),
    ("seminary.seminary.api.save_instructor_profile", "Instructor"),
    # Staff work whose refusal IS the DocPerm on the save -- the endpoint is in
    # OWN_RULE for exactly that reason, and a student failing here is correct.
    ("seminary.seminary.doctype.course.course.add_course_to_programs", "Program"),
    ("seminary.seminary.doctype.course.course.bulk_add_courses_to_program", "Program"),
    ("seminary.seminary.doctype.question.question.refresh_scripture_text", "Question"),
    ("seminary.seminary.doctype.question.question.replace_matching_items", "Question"),
    (
        "seminary.seminary.doctype.term_admission.term_admission.refresh_programs",
        "Term Admission",
    ),
    ("seminary.seminary.graduation.waive_sgr", "Program Enrollment"),
    ("seminary.seminary.leveling.apply_leveling_profile", "Leveling Profile"),
    ("seminary.seminary.leveling.apply_leveling_profile", "Program Enrollment"),
    ("seminary.seminary.leveling.resolve_leveling_plan", "Program Enrollment"),
}


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
        cs, other = _any_course_schedule()
        cls.course = cs.name
        cls.other_course = other.name
        cls.roster = _roster(cls.course, cls.student, cls.user)
        # p007 §8.1: a roster row alone opens nothing -- the section has to be
        # published. That is the rule get_lesson applies, and now the rule the
        # lesson discussion applies, so the fixture has to satisfy it.
        frappe.db.set_value("Course Schedule", cls.course, "published", 1)
        frappe.db.set_value("Course Schedule", cls.other_course, "published", 1)

        cls.chapter = frappe.get_doc(
            {
                "doctype": "Course Schedule Chapter",
                "chapter_title": PREFIX,
                # the field is `coursesc` here; Course Lesson.course_sc is
                # fetch_from chapter.coursesc, so getting this wrong leaves
                # every lesson of the chapter with no section at all
                "coursesc": cls.course,
            }
        )
        cls.chapter.flags.ignore_permissions = True
        cls.chapter.insert(ignore_mandatory=True)

        cls.lesson = frappe.get_doc(
            {
                "doctype": "Course Lesson",
                "lesson_title": PREFIX,
                "chapter": cls.chapter.name,
                # no body and no content: the block-editor shape that broke
                # render_html
            }
        )
        cls.lesson.flags.ignore_permissions = True
        cls.lesson.insert(ignore_mandatory=True)
        if cls.lesson.course_sc != cls.course:
            # course_sc is fetch_from chapter.coursesc, so a chapter built with
            # the wrong field name leaves every lesson sectionless and the
            # enrolment tests below would pass for the wrong reason
            raise AssertionError(
                "fixture lesson is on %r, not %r" % (cls.lesson.course_sc, cls.course)
            )

    def setUp(self):
        # guards memoises the caller's sections per request; these fixtures are
        # built after the first lookup would have run.
        frappe.local.p007_cache = {}

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.local.p007_cache = {}

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

    def test_a_student_opens_and_posts_in_the_lesson_discussion(self):
        """The same shape as save_progress: `_require_reference_read` asked
        `has_permission("Course Lesson", "read")`, which p007 F1 took away from
        the Student role on purpose -- so lesson discussions refused every
        student. The rule is the section's, not the doctype's."""
        from seminary.seminary.utils import add_discussion_reply, get_discussion_topics

        frappe.set_user(self.user)
        # the first caller creates the thread, so this returns a Document here
        # and a dict once one exists -- .get() reads both
        topic = get_discussion_topics("Course Lesson", self.lesson.name, 1)
        self.assertTrue(topic and topic.get("name"))
        reply = add_discussion_reply(topic.get("name"), "<p>p008</p>")
        self.assertTrue(reply)
        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Discussion Reply", reply, "owner"), self.user
        )

    def test_a_student_is_refused_a_lesson_they_are_not_enrolled_in(self):
        chapter = frappe.get_doc(
            {
                "doctype": "Course Schedule Chapter",
                "chapter_title": PREFIX + " elsewhere",
                "coursesc": self.other_course,
            }
        )
        chapter.flags.ignore_permissions = True
        chapter.insert(ignore_mandatory=True)
        other = frappe.get_doc(
            {
                "doctype": "Course Lesson",
                "lesson_title": PREFIX + " elsewhere",
                "chapter": chapter.name,
            }
        )
        other.flags.ignore_permissions = True
        other.insert(ignore_mandatory=True)
        self.assertEqual(other.course_sc, self.other_course)
        from seminary.seminary.utils import get_discussion_topics

        frappe.set_user(self.user)
        with self.assertRaises(frappe.PermissionError):
            get_discussion_topics("Course Lesson", other.name, 1)

    def test_a_student_submits_their_own_recommendation_letter(self):
        """`start_recommendation_letter` inserted the letter with
        ignore_permissions and then submitted it without. Student holds no
        submit on Recommendation Letter -- p007 F1 put the letter's body and
        token at permlevel 1 precisely because it is about them -- so the
        portal button raised PermissionError for every student who pressed it.
        This pins both halves: the permission really is absent, and the shape
        the endpoint now uses gets through."""
        letter = frappe.get_doc(
            {
                "doctype": "Recommendation Letter",
                "program_enrollment": None,
                "recommender_name": PREFIX,
                "recommender_email": "zzt-rec@example.com",
            }
        )
        letter.flags.ignore_permissions = True
        letter.insert(ignore_mandatory=True, ignore_permissions=True)

        frappe.set_user(self.user)
        self.assertFalse(frappe.has_permission("Recommendation Letter", "submit"))
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc("Recommendation Letter", letter.name).submit()

        doc = frappe.get_doc("Recommendation Letter", letter.name)
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.submit()
        self.assertEqual(doc.docstatus, 1)

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


class TestP008StudentWriteSweep(IntegrationTestCase):
    """The ratchet for the class of bug save_progress belonged to."""

    def test_no_new_student_path_is_closed_by_a_docperm(self):
        checked, hits = sweep()
        self.assertGreater(checked, 100, "the sweep found almost nothing to scan")
        found = {(dotted, dt) for dotted, dt, _missing, _w in hits}
        new = sorted(found - KNOWN_SWEEP_PAIRS)
        self.assertEqual(
            new,
            [],
            "a student-reachable endpoint writes a doctype the Student role "
            "cannot: read it, and either fix the endpoint (the p008 fixes to "
            "save_progress, get_discussion_topics and start_recommendation_letter "
            "are the worked examples) or add the pair to KNOWN_SWEEP_PAIRS with "
            "the reason. New pairs: %s" % (new,),
        )
        gone = sorted(KNOWN_SWEEP_PAIRS - found)
        self.assertEqual(
            gone,
            [],
            "KNOWN_SWEEP_PAIRS entries the sweep no longer reports -- drop "
            "them, the ratchet only tightens: %s" % (gone,),
        )
