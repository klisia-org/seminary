"""Round-trip test for Course Pack export/import.

Builds a minimal Course Schedule with a chapter, a lesson whose EditorJS content
embeds a quiz, a quiz with one question, a graded SCAC row and a grading scale;
exports it to a pack; imports the pack as a NEW Course on the same test site; and
asserts the content was cloned and every reference remapped to the new local docs.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from .editorjs import rewrite_body_refs, scan_body_refs, scan_content_refs, scan_urls
from .export import build_pack_bytes
from .import_ import import_pack_from_bytes


class TestEditorJS(FrappeTestCase):
    def test_scan_and_rewrite(self):
        content = json.dumps(
            {
                "blocks": [
                    {"type": "quiz", "data": {"quiz": "Q-1"}},
                    {"type": "upload", "data": {"file_url": "/files/a.png"}},
                ]
            }
        )
        self.assertIn(("Quiz", "Q-1"), scan_content_refs(content))
        self.assertEqual(scan_urls(content), {"/files/a.png"})

        body = "{{ Quiz('Q-1') }} text"
        self.assertEqual(scan_body_refs(body), [("Quiz", "Q-1")])
        self.assertEqual(
            rewrite_body_refs(body, {"Q-1": "Q-NEW"}), "{{ Quiz('Q-NEW') }} text"
        )


class TestCoursePackRoundTrip(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Bind the Pass/Fail grade value to a non-password-like name so Bandit
        # B105 doesn't misread the "Pass" literal as a hardcoded password (the
        # field is grade_pass — a grade outcome, not a secret).
        grade_outcome = "Pass"
        cls.scale = _ensure(
            "Grading Scale",
            {
                "grading_scale_name": "CP Test Scale",
                "grscale_type": "Points",
                "maxnumgrade": 100,
            },
            child={
                "intervals": [
                    {"grade_code": "A", "threshold": 0, "grade_pass": grade_outcome}
                ],
            },
        )
        cls.term = _any_academic_term()
        cls.criteria = _ensure(
            "Assessment Criteria",
            {"assessment_criteria": "CP Test Quizzes", "type": "Quiz"},
        )
        cls.course = _ensure(
            "Course",
            {"course_name": "CP Source Course", "default_grading_scale": cls.scale},
        )
        cls.question = (
            frappe.get_doc(
                {
                    "doctype": "Question",
                    "question": "What is 2+2?",
                    "type": "Choices",
                    "course": cls.course,
                    "option_1": "4",
                    "is_correct_1": 1,
                    "option_2": "5",
                }
            )
            .insert(ignore_permissions=True, ignore_mandatory=True)
            .name
        )
        cls.quiz = (
            frappe.get_doc(
                {
                    "doctype": "Quiz",
                    "title": "CP Source Quiz",
                    "course": cls.course,
                    "questions": [{"question": cls.question, "points": 1}],
                }
            )
            .insert(ignore_permissions=True, ignore_mandatory=True)
            .name
        )

        cls.cs = _make_cs(cls.course, cls.term, cls.scale)
        # one graded SCAC row linking the quiz
        scac = frappe.get_doc(
            {
                "doctype": "Scheduled Course Assess Criteria",
                "parent": cls.cs,
                "parenttype": "Course Schedule",
                "parentfield": "courseassescrit_sc",
                "idx": 1,
                "assesscriteria_scac": cls.criteria,
                "title": "Quizzes",
                "weight_scac": 100,
                "quiz": cls.quiz,
            }
        ).insert(ignore_permissions=True, ignore_mandatory=True)
        cls.scac_name = scac.name
        # chapter + lesson whose content embeds the quiz
        cls.chapter = (
            frappe.get_doc(
                {
                    "doctype": "Course Schedule Chapter",
                    "coursesc": cls.cs,
                    "chapter_title": "Ch1",
                }
            )
            .insert(ignore_permissions=True, ignore_mandatory=True)
            .name
        )
        content = json.dumps({"blocks": [{"type": "quiz", "data": {"quiz": cls.quiz}}]})
        cls.lesson = (
            frappe.get_doc(
                {
                    "doctype": "Course Lesson",
                    "chapter": cls.chapter,
                    "lesson_title": "L1",
                    "content": content,
                    "assessment_criteria_quiz": cls.scac_name,
                }
            )
            .insert(ignore_permissions=True, ignore_mandatory=True)
            .name
        )
        _child(
            cls.chapter,
            "Course Schedule Chapter",
            "lessons",
            "Course Schedule Lesson Reference",
            {"lesson": cls.lesson},
            1,
        )
        _child(
            cls.cs,
            "Course Schedule",
            "chapters",
            "Course Schedule Chapter Reference",
            {"chapter": cls.chapter},
            1,
        )

    def test_round_trip(self):
        _filename, content = build_pack_bytes(self.cs)
        result = import_pack_from_bytes(
            content,
            target_mode="new",
            course_name="CP Imported Course",
            academic_term=self.term,
            section="A",
        )

        # New, distinct course + schedule
        self.assertNotEqual(result["course"], self.course)
        self.assertTrue(frappe.db.exists("Course", result["course"]))
        self.assertEqual(result["chapters"], 1)
        self.assertEqual(result["lessons"], 1)
        self.assertEqual(result["questions"], 1)

        # The imported lesson's quiz ref points at a NEW quiz, not the source one
        new_chapter = frappe.db.get_value(
            "Course Schedule Chapter Reference",
            {"parent": result["course_schedule"]},
            "chapter",
        )
        new_lesson = frappe.db.get_value(
            "Course Schedule Lesson Reference", {"parent": new_chapter}, "lesson"
        )
        new_content = frappe.db.get_value("Course Lesson", new_lesson, "content")
        refs = scan_content_refs(new_content)
        self.assertEqual(len(refs), 1)
        new_quiz = refs[0][1]
        self.assertNotEqual(new_quiz, self.quiz)
        self.assertTrue(frappe.db.exists("Quiz", new_quiz))

        # The new quiz carries its question (cloned)
        new_q_rows = frappe.get_all("Quiz Question", {"parent": new_quiz}, ["question"])
        self.assertEqual(len(new_q_rows), 1)
        self.assertNotEqual(new_q_rows[0].question, self.question)

        # SCAC row carried and pointed at the new quiz; lesson SCAC link remapped
        new_scac = frappe.db.get_value(
            "Scheduled Course Assess Criteria",
            {"parent": result["course_schedule"]},
            ["name", "quiz"],
            as_dict=True,
        )
        self.assertEqual(new_scac.quiz, new_quiz)
        self.assertEqual(
            frappe.db.get_value(
                "Course Lesson", new_lesson, "assessment_criteria_quiz"
            ),
            new_scac.name,
        )


# --- fixture helpers ---------------------------------------------------------


def _ensure(doctype, fields, child=None):
    key = next(iter(fields))
    existing = frappe.db.get_value(doctype, {key: fields[key]})
    if existing:
        return existing
    doc = frappe.get_doc({"doctype": doctype, **fields})
    for cf, rows in (child or {}).items():
        for r in rows:
            doc.append(cf, r)
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    return doc.name


def _any_academic_term():
    name = frappe.db.get_value("Academic Term", {})
    if not name:
        import unittest

        raise unittest.SkipTest(
            "No Academic Term on this site to anchor the test schedule."
        )
    return name


def _make_cs(course, term, scale):
    from frappe.utils import nowdate

    dates = frappe.db.get_value(
        "Academic Term", term, ["term_start_date", "term_end_date"], as_dict=True
    )
    start = (dates and dates.term_start_date) or nowdate()
    end = (dates and dates.term_end_date) or nowdate()
    cs = frappe.get_doc(
        {
            "doctype": "Course Schedule",
            "course": course,
            "academic_term": term,
            "section": "SRC",
            "gradesc_cs": scale,
            "modality": "Virtual",
            "c_datestart": start,
            "c_dateend": end,
        }
    )
    cs.insert(ignore_permissions=True, ignore_mandatory=True)
    frappe.db.delete(
        "Scheduled Course Assess Criteria",
        {"parent": cs.name, "parenttype": "Course Schedule"},
    )
    return cs.name


def _child(parent, parenttype, parentfield, child_doctype, fields, idx):
    frappe.get_doc(
        {
            "doctype": child_doctype,
            "parent": parent,
            "parenttype": parenttype,
            "parentfield": parentfield,
            "idx": idx,
            **fields,
        }
    ).insert(ignore_permissions=True)


def run_smoke():
    """Run these tests directly (bypassing app-wide test discovery), then roll
    back. Invoke with: bench --site <site> execute
    seminary.seminary.course_pack.test_course_pack.run_smoke
    """
    import unittest

    frappe.flags.in_test = True
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(
        [
            loader.loadTestsFromTestCase(TestEditorJS),
            loader.loadTestsFromTestCase(TestCoursePackRoundTrip),
        ]
    )
    result = unittest.TextTestRunner(verbosity=2, stream=None).run(suite)
    frappe.db.rollback()
    summary = {
        "ran": result.testsRun,
        "failures": [str(f[0]) + "\n" + f[1] for f in result.failures],
        "errors": [str(e[0]) + "\n" + e[1] for e in result.errors],
        "ok": result.wasSuccessful(),
    }
    print(frappe.as_json(summary))
    return summary
