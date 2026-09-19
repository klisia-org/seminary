# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p008a G8 (p005a A01-15): answer material does not reach a student before the
answer, and not at all where the instructor did not ask for feedback.

* model answers (``Assignment Activity.answer`` / ``show_answer``,
  ``Exam Question.standard_comments`` -- which is ``fetch_from`` the Open
  Question's ``explanation`` and so rides inside the exam a student must read)
  are permlevel 1; ``Open Question`` has no Student row at all;
* the quiz detail endpoints are membership-gated on the QUIZ's course and send
  ``explanation_*`` before the answer only to graders, or with a quiz context
  whose ``show_answers`` is on;
* ``check_answer`` is not an oracle: no verdict without that same context;
* the three caller-less ``get_question_details`` endpoints are gone.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.doctype.quiz.quiz import check_answer, quiz_summary
from seminary.seminary.tests.test_p006_api import _make_user
from seminary.seminary.utils import (
    get_all_questions_details,
    get_question_details,
)


def _choice_question():
    q = frappe.new_doc("Question")
    q.question = f"QC-{frappe.generate_hash(length=8)}"
    q.type = "Choices"
    q.option_1, q.is_correct_1, q.explanation_1 = "right", 1, "because it is right"
    q.option_2, q.is_correct_2 = "wrong", 0
    q.insert(ignore_permissions=True)
    return q.name


def _input_question(possibility="Jerusalem"):
    q = frappe.new_doc("Question")
    q.question = f"QI-{frappe.generate_hash(length=8)}"
    q.type = "User Input"
    q.possibility_1 = possibility
    q.insert(ignore_permissions=True)
    return q.name


def _quiz(question, qtype, show_answers, course=None):
    quiz = frappe.new_doc("Quiz")
    quiz.title = f"TQ8-{frappe.generate_hash(length=8)}"
    quiz.passing_percentage = 50
    quiz.show_answers = show_answers
    if course:
        quiz.course = course
    else:
        quiz.standalone = 1
    quiz.append("questions", {"question": question, "points": 2, "type": qtype})
    quiz.flags.ignore_links = True
    quiz.insert(ignore_permissions=True, ignore_mandatory=True)
    return quiz.name, quiz.questions[0].name


def _expl(d):
    return [k for k in (d or {}) if k.startswith("explanation_")]


class TestP008aAnswerKeys(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _make_user("Student", "g8-student")
        cls.instructor = _make_user("Instructor", "g8-instr")
        cls.question = _choice_question()
        cls.quiz_open, cls.row_open = _quiz(cls.question, "Choices", 1)
        cls.quiz_closed, cls.row_closed = _quiz(cls.question, "Choices", 0)
        # A quiz tied to a Course nobody here is enrolled in. The name need not
        # resolve to a real Course: user_is_enrolled_in_course finds no section.
        cls.quiz_foreign, cls.row_foreign = _quiz(
            _choice_question(), "Choices", 1, course="ZZT-p008a-no-such-course"
        )
        cls.foreign_question = frappe.db.get_value(
            "Quiz Question", cls.row_foreign, "question"
        )

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")

    # ---------------------------------------------------------- field level
    def test_model_answer_fields_are_permlevel_1(self):
        for doctype, field in (
            ("Assignment Activity", "answer"),
            ("Assignment Activity", "show_answer"),
            ("Exam Question", "standard_comments"),
        ):
            with self.subTest(field=f"{doctype}.{field}"):
                self.assertEqual(frappe.get_meta(doctype).get_field(field).permlevel, 1)

    def test_student_has_no_permlevel_1_read_and_instructor_does(self):
        for doctype in ("Assignment Activity", "Exam Activity"):
            doc = frappe.new_doc(doctype)
            with self.subTest(doctype=doctype):
                frappe.set_user(self.student)
                self.assertNotIn(1, doc.get_permlevel_access("read"))
                frappe.set_user(self.instructor)
                self.assertIn(1, doc.get_permlevel_access("read"))
                self.assertIn(1, doc.get_permlevel_access("write"))
                frappe.set_user("Administrator")

    def test_assignment_answer_is_blanked_for_a_student(self):
        doc = frappe.new_doc("Assignment Activity")
        doc.title = f"TA8-{frappe.generate_hash(length=6)}"
        doc.answer, doc.show_answer = "THE-KEY", 1
        doc.flags.ignore_links = True
        doc.insert(ignore_permissions=True, ignore_mandatory=True)
        frappe.set_user(self.student)
        seen = frappe.get_doc("Assignment Activity", doc.name)
        seen.apply_fieldlevel_read_permissions()
        self.assertFalse(seen.get("answer"))
        frappe.set_user(self.instructor)
        seen = frappe.get_doc("Assignment Activity", doc.name)
        seen.apply_fieldlevel_read_permissions()
        self.assertEqual(seen.get("answer"), "THE-KEY")

    def test_open_question_has_no_student_row(self):
        self.assertFalse(
            frappe.has_permission("Open Question", "read", user=self.student)
        )
        self.assertTrue(
            frappe.has_permission("Open Question", "read", user=self.instructor)
        )

    # ---------------------------------------------------------- endpoints
    def test_explanations_stay_home_without_show_answers(self):
        frappe.set_user(self.student)
        self.assertEqual(_expl(get_question_details(self.question)), [])
        self.assertEqual(
            _expl(get_question_details(self.question, quiz=self.quiz_closed)), []
        )
        rows = get_all_questions_details(json.dumps([self.row_closed]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(_expl(rows[0]), [])

    def test_explanations_travel_when_the_instructor_opted_in(self):
        frappe.set_user(self.student)
        self.assertTrue(_expl(get_question_details(self.question, quiz=self.quiz_open)))
        rows = get_all_questions_details(json.dumps([self.row_open]))
        self.assertTrue(_expl(rows[0]))

    def test_a_grader_sees_explanations_without_a_quiz(self):
        frappe.set_user(self.instructor)
        self.assertTrue(_expl(get_question_details(self.question)))

    def test_not_enrolled_is_refused(self):
        frappe.set_user(self.student)
        with self.assertRaises(frappe.PermissionError):
            get_question_details(self.foreign_question)
        with self.assertRaises(frappe.PermissionError):
            get_question_details(self.foreign_question, quiz=self.quiz_foreign)
        with self.assertRaises(frappe.PermissionError):
            get_all_questions_details(json.dumps([self.row_foreign]))
        with self.assertRaises(frappe.PermissionError):
            check_answer(
                self.foreign_question,
                "Choices",
                json.dumps(["right"]),
                quiz=self.quiz_foreign,
            )

    def test_a_quiz_that_does_not_contain_the_question_is_refused(self):
        frappe.set_user(self.student)
        with self.assertRaises(frappe.PermissionError):
            get_question_details(self.foreign_question, quiz=self.quiz_open)

    def test_rows_that_are_not_quiz_questions_are_not_served(self):
        frappe.set_user(self.student)
        self.assertEqual(get_all_questions_details(json.dumps(["ZZT-no-such-row"])), [])

    def test_check_answer_is_not_an_oracle(self):
        frappe.set_user(self.student)
        answers = json.dumps(["right"])
        # no quiz context, and a quiz whose instructor did not ask for feedback
        self.assertIsNone(check_answer(self.question, "Choices", answers))
        self.assertIsNone(
            check_answer(self.question, "Choices", answers, quiz=self.quiz_closed)
        )
        # the feature itself survives
        self.assertIsNotNone(
            check_answer(self.question, "Choices", answers, quiz=self.quiz_open)
        )

    def test_quiz_summary_grades_without_a_client_verdict(self):
        """The SPA now submits is_correct = [null] for a show_answers=0 quiz."""
        question = _input_question("Jerusalem")
        quiz, _row = _quiz(question, "User Input", 0)
        frappe.set_user(self.student)
        results = [
            {"question_name": question, "answer": "jerusalem", "is_correct": [None]}
        ]
        res = quiz_summary(quiz, results=json.dumps(results))
        self.assertEqual(res["score"], 2)

    def test_dead_endpoints_are_not_whitelisted(self):
        import importlib

        for mod, gone in (
            ("seminary.seminary.doctype.quiz.quiz", True),
            ("seminary.seminary.doctype.exam_activity.exam_activity", False),
            ("seminary.seminary.doctype.question.question", False),
        ):
            m = importlib.import_module(mod)
            fn = getattr(m, "get_question_details", None)
            with self.subTest(module=mod):
                if gone:
                    self.assertIsNone(fn)
                else:
                    self.assertNotIn(fn, frappe.whitelisted)


class TestP008aCourseFolderList(IntegrationTestCase):
    """The Course Folder list shows exactly what a per-document read allows.

    The per-document rule (``course_folder.user_may_read``) predates this; the
    list used to apply the DocPerm alone. The richer personas -- enrolled
    student, grader, of-record instructor -- are checked the same way against
    real folders by scripts/p008a_validation on potestas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _make_user("Student", "g8-cf-student")
        cls.chair = _make_user("Program Chair", "g8-cf-chair")

    def tearDown(self):
        frappe.set_user("Administrator")

    def _listed_vs_readable(self, user):
        from seminary.seminary.doctype.course_folder.course_folder import user_may_read

        everything = frappe.get_all("Course Folder", pluck="name")
        frappe.set_user(user)
        listed = set(frappe.get_list("Course Folder", pluck="name", limit=0))
        frappe.set_user("Administrator")
        readable = {n for n in everything if user_may_read(n, user)}
        return listed, readable

    def test_list_equals_per_document_read(self):
        for user in (self.student, self.chair):
            with self.subTest(user=user):
                listed, readable = self._listed_vs_readable(user)
                self.assertEqual(listed, readable)

    def test_condition_shapes(self):
        from seminary.seminary.doctype.course_folder.course_folder import (
            get_permission_query_conditions as cond,
        )

        self.assertEqual(cond("Guest"), "1=0")
        self.assertEqual(cond("Administrator"), "")
        self.assertEqual(cond(self.chair), "")
        # a student on no roster reaches School folders and nothing else
        student_cond = cond(self.student)
        self.assertIn("scope = 'School'", student_cond)
        self.assertNotIn("'Section'", student_cond)
        self.assertNotIn("'Instructor'", student_cond)
