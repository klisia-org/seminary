# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""ADR 079 -- competency work lives in the course outline.

Integration tests, because what is under test is a composition of records: a
scale, a course with competencies, a framework, a programme binding them, and a
section whose outline the framework shapes. Each test builds its own world and
rolls it back.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from seminary.seminary import api, cbe, cbe_reflection

PREFIX = "ZZ079"

INTERVALS = [
    {"grade_code": "4", "threshold": 4.0, "grade_pass": "Pass"},  # nosec B105
    {"grade_code": "3", "threshold": 3.0, "grade_pass": "Pass"},  # nosec B105
    {"grade_code": "2", "threshold": 2.0, "grade_pass": "Fail"},  # nosec B105
    {"grade_code": "1", "threshold": 1.0, "grade_pass": "Fail"},  # nosec B105
]


def _insert(doc):
    doc = frappe.get_doc(doc)
    doc.flags.ignore_permissions = True
    doc.insert(ignore_mandatory=True)
    return doc


class World:
    """A competency section and everything it needs, built fresh per test."""

    def __init__(self, **framework):
        term = frappe.db.get_value("Academic Term", {})
        if not term:
            import unittest

            raise unittest.SkipTest("No Academic Term on this site.")
        self.term = term

        self.scale = _insert(
            {
                "doctype": "Grading Scale",
                "grading_scale_name": f"{PREFIX} CBE",
                "grscale_type": "Competency-based education",
                "maxnumgrade": 4.0,
                "intervals": [dict(i) for i in INTERVALS],
                "gradingscaledimensions": [
                    {
                        "dimension": "Knowledge",
                        "dimension_code": "knowledge",
                        "sequence": 1,
                    },
                    {
                        "dimension": "Character",
                        "dimension_code": "character",
                        "sequence": 2,
                    },
                ],
            }
        ).name
        self.course = _insert(
            {
                "doctype": "Course",
                "course_name": f"{PREFIX} Formation",
                "coursecode": "ZZ079",
                "default_grading_scale": self.scale,
            }
        ).name
        self.competencies = [
            _insert(
                {
                    "doctype": "Course Competency",
                    "course": self.course,
                    "competency_code": code,
                    "competency_name": name,
                    "sequence": seq,
                    "is_active": 1,
                    "dimensions": [
                        {"dimension_code": "knowledge", "demonstrated_by": "<p>k</p>"},
                        {"dimension_code": "character", "demonstrated_by": "<p>c</p>"},
                    ],
                }
            ).name
            for seq, (code, name) in enumerate(
                (("LIC", "Life in Christ"), ("INT", "Integrity")), start=1
            )
        ]
        settings = {
            "doctype": "Competency Framework",
            "framework_name": f"{PREFIX} Framework",
            "status": "Active",
            "grading_scale": self.scale,
            "activity_grading_mode": "One grade per activity",
            "verdict_source": "Final assessments only",
            "aggregation_method": "Average",
            "rounding": "Nearest",
            "report_basis": "Framework scale",
            "content_release_mode": "Ungated",
            "default_pacing_mode": "Self-paced",
            "course_self_eval": 1,
            "course_self_eval_points": "Start of course and end of each competency",
            "require_pdp": 1,
            "evaluators": [
                {
                    "instructor_category": frappe.db.get_value(
                        "Instructor Category", {}
                    ),
                    "assignment_source": "Course Schedule Instructors",
                    "grades_activities": 1,
                    "gives_competency_verdict": 1,
                }
            ],
        }
        settings.update(framework)
        self.framework = _insert(settings).name
        _insert(
            {
                "doctype": "Program",
                "program_name": f"{PREFIX} Programme",
                "program_abbreviation": "ZZ079",
                "enrollment_mode": "Timed",
                "competency_framework": self.framework,
                "courses": [{"course": self.course}],
            }
        )
        self.cs = self.section()

    def section(self, **flags):
        dates = frappe.db.get_value(
            "Academic Term",
            self.term,
            ["term_start_date", "term_end_date"],
            as_dict=True,
        )
        cs = frappe.get_doc(
            {
                "doctype": "Course Schedule",
                "course": self.course,
                "academic_term": self.term,
                "section": f"S{frappe.generate_hash(length=4)}",
                "gradesc_cs": self.scale,
                "modality": "Virtual",
                "c_datestart": (dates and dates.term_start_date) or nowdate(),
                "c_dateend": (dates and dates.term_end_date) or nowdate(),
            }
        )
        cs.flags.ignore_permissions = True
        for k, v in flags.items():
            setattr(cs.flags, k, v)
        cs.insert(ignore_mandatory=True)
        return cs.name

    def chapters(self, cs=None):
        return cbe._mapped_chapters(cs or self.cs)

    def lessons(self, chapter):
        return cbe_reflection._chapter_lessons(chapter)

    def reflections(self, chapter):
        return [
            cbe_reflection.reflection_of(
                frappe.db.get_value("Course Lesson", lesson, "content")
            )
            for lesson in self.lessons(chapter)
        ]

    def add_lesson(self, chapter, title="Plain lesson"):
        lesson = _insert(
            {
                "doctype": "Course Lesson",
                "chapter": chapter,
                "course_sc": self.cs,
                "lesson_title": title,
                "content": json.dumps(
                    {"blocks": [{"type": "paragraph", "data": {"text": "x"}}]}
                ),
            }
        )
        # As the lesson form does: a child row with the next index, which
        # lands after the closing reflection unless something re-pins it.
        _insert(
            {
                "doctype": "Course Schedule Lesson Reference",
                "parent": chapter,
                "parenttype": "Course Schedule Chapter",
                "parentfield": "lessons",
                "idx": len(self.lessons(chapter)) + 1,
                "lesson": lesson.name,
            }
        )
        return lesson.name


class ADR079Case(IntegrationTestCase):
    def tearDown(self):
        frappe.db.rollback()
        super().tearDown()


class TestScaffold(ADR079Case):
    def test_section_is_born_with_a_chapter_per_competency_and_its_reflections(self):
        w = World()
        chapters = w.chapters()
        self.assertEqual([c.course_competency for c in chapters], w.competencies)

        first, last = chapters[0].name, chapters[-1].name
        self.assertEqual(
            w.reflections(first),
            [
                ("selfAssessment", "course", "Baseline"),
                ("selfAssessment", "chapter", "Final"),
            ],
        )
        self.assertEqual(
            w.reflections(last),
            [
                ("selfAssessment", "chapter", "Final"),
                ("developmentPlan", "course", None),
            ],
        )
        for chapter in chapters:
            for lesson in w.lessons(chapter.name):
                self.assertEqual(
                    frappe.db.get_value("Course Lesson", lesson, "autocreated"), 1
                )

    def test_scaffold_is_idempotent(self):
        w = World()
        before = frappe.db.count("Course Lesson", {"course_sc": w.cs})
        self.assertEqual(cbe_reflection.scaffold(w.cs), 0)
        self.assertEqual(frappe.db.count("Course Lesson", {"course_sc": w.cs}), before)
        self.assertEqual(cbe_reflection.missing_reflections(w.cs), [])

    def test_a_cleared_self_eval_asks_for_no_self_assessment(self):
        """The dependent Select keeps its value; the parent Check decides."""
        w = World(course_self_eval=0)
        for chapter in w.chapters():
            self.assertNotIn(
                "selfAssessment", [r[0] for r in w.reflections(chapter.name) if r]
            )

    def test_an_import_skips_the_creation_scaffold(self):
        w = World()
        cs = w.section(skip_reflection_scaffold=True)
        self.assertEqual(w.chapters(cs), [])
        self.assertTrue(cbe_reflection.missing_reflections(cs))
        cbe_reflection.scaffold(cs)
        self.assertEqual(cbe_reflection.missing_reflections(cs), [])

    def test_untouched_scaffold_gives_way_but_one_with_content_does_not(self):
        w = World()
        self.assertTrue(cbe_reflection.untouched_scaffold(w.cs))
        w.add_lesson(w.chapters()[0].name)
        self.assertFalse(cbe_reflection.untouched_scaffold(w.cs))


class TestGovernedLessons(ADR079Case):
    def setUp(self):
        self.w = World()
        self.chapter = self.w.chapters()[0].name
        self.reflection = self.w.lessons(self.chapter)[-1]

    def test_a_new_lesson_lands_before_the_closing_reflection(self):
        added = self.w.add_lesson(self.chapter)
        lessons = self.w.lessons(self.chapter)
        self.assertEqual(lessons[-1], self.reflection)
        self.assertIn(added, lessons[1:-1])

    def test_deleting_a_reflection_lesson_is_refused_with_the_reason(self):
        with self.assertRaises(frappe.ValidationError) as caught:
            api.delete_lesson(self.reflection, self.chapter)
        self.assertIn("Competency Framework", str(caught.exception))
        with self.assertRaises(frappe.ValidationError):
            frappe.delete_doc("Course Lesson", self.reflection, ignore_permissions=True)

    def test_moving_a_reflection_lesson_is_refused(self):
        other = self.w.chapters()[1].name
        with self.assertRaises(frappe.ValidationError):
            api.update_lesson_index(self.reflection, self.chapter, other, 1)

    def test_deleting_its_chapter_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            api.delete_chapter(self.chapter)

    def test_the_title_may_change_but_the_block_may_not(self):
        doc = frappe.get_doc("Course Lesson", self.reflection)
        doc.lesson_title = "Looking back"
        doc.save(ignore_permissions=True)

        doc.content = json.dumps(
            {"blocks": [{"type": "paragraph", "data": {"text": "gone"}}]}
        )
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_the_flag_cannot_be_cleared(self):
        doc = frappe.get_doc("Course Lesson", self.reflection)
        doc.autocreated = 0
        doc.save(ignore_permissions=True)
        self.assertEqual(
            frappe.db.get_value("Course Lesson", self.reflection, "autocreated"), 1
        )


class TestReleaseModes(ADR079Case):
    def test_gated_mode_needs_an_end_of_competency_self_assessment(self):
        w = World()
        fw = frappe.get_doc("Competency Framework", w.framework)
        fw.content_release_mode = cbe.CHAPTER_GATED
        fw.save(ignore_permissions=True)  # timing includes end of each competency

        fw.course_self_eval = 0
        with self.assertRaises(frappe.ValidationError) as caught:
            fw.save(ignore_permissions=True)
        self.assertIn("Ungated", str(caught.exception))

    def test_a_stale_gated_mode_resolves_to_ungated(self):
        w = World()
        frappe.db.set_value(
            "Competency Framework",
            w.framework,
            {"content_release_mode": cbe.CHAPTER_GATED, "course_self_eval": 0},
        )
        frappe.clear_document_cache("Competency Framework", w.framework)
        self.assertEqual(cbe.content_release_mode(w.cs), cbe.UNGATED)

    def test_options_follow_the_timing(self):
        w = World(course_self_eval_points="Start and end of course")
        self.assertEqual(
            cbe.release_mode_options(
                frappe.get_doc("Competency Framework", w.framework)
            ),
            [cbe.UNGATED],
        )


class TestChapterChain(ADR079Case):
    def test_a_move_refiles_the_assessment_on_the_new_chapter(self):
        w = World()
        first, second = (c.name for c in w.chapters())
        lesson = w.add_lesson(first, "Exam lesson")
        exam = frappe.get_doc(
            {"doctype": "Exam Activity", "title": f"{PREFIX} Exam", "course": w.course}
        )
        exam.flags.ignore_permissions = True
        exam.insert(ignore_mandatory=True)
        frappe.db.set_value(
            "Course Lesson",
            lesson,
            "content",
            json.dumps({"blocks": [{"type": "exam", "data": {"exam": exam.name}}]}),
        )
        criteria = frappe.get_doc(
            {
                "doctype": "Scheduled Course Assess Criteria",
                "parent": w.cs,
                "parenttype": "Course Schedule",
                "parentfield": "courseassescrit_sc",
                "title": "Exam",
                "type": "Exam",
                "exam": exam.name,
                "course_competency": w.competencies[0],
            }
        )
        criteria.insert(ignore_permissions=True, ignore_mandatory=True)

        lesson_doc = frappe.get_doc("Course Lesson", lesson)
        api._move_lesson_between_chapters(
            lesson_doc,
            frappe.get_doc("Course Schedule Chapter", first),
            frappe.get_doc("Course Schedule Chapter", second),
            1,
        )
        refiled = api._refile_competencies(w.cs)
        self.assertEqual([r["to"] for r in refiled], ["Integrity"])
        self.assertEqual(
            frappe.db.get_value(
                "Scheduled Course Assess Criteria", criteria.name, "course_competency"
            ),
            w.competencies[1],
        )


class TestMentors(ADR079Case):
    def test_visibility_follows_the_framework(self):
        w = World(student_sees_mentor_eval="On submit")
        fw = frappe.get_doc("Competency Framework", w.framework)
        self.assertTrue(
            cbe.mentor_assessments_visible("nobody", w.cs, w.competencies[0], fw)
        )
        fw.student_sees_mentor_eval = "After all mentors submit"
        # No roster for this student: nothing is shown before it exists.
        self.assertFalse(
            cbe.mentor_assessments_visible("nobody", w.cs, w.competencies[0], fw)
        )

    def test_blank_visibility_takes_the_narrow_default(self):
        w = World()
        fw = frappe.get_doc("Competency Framework", w.framework)
        fw.student_sees_mentor_eval = None
        self.assertFalse(
            cbe.mentor_assessments_visible("nobody", w.cs, w.competencies[0], fw)
        )
