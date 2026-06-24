# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.doctype.quiz.quiz import (
    check_choice_answers,
    choice_is_correct,
    quiz_summary,
)


def _make_choice_question(options, correct_idx):
    """Create a Choices Question. `options` is a list of option texts (2-4);
    `correct_idx` is a set of 1-based indices that are correct."""
    doc = frappe.new_doc("Question")
    doc.question = f"Q-{frappe.generate_hash(length=8)}"
    doc.type = "Choices"
    for i, text in enumerate(options, start=1):
        doc.set(f"option_{i}", text)
        doc.set(f"is_correct_{i}", 1 if i in correct_idx else 0)
    doc.insert(ignore_permissions=True)
    return doc.name


def _make_quiz(questions, passing_percentage=50):
    """questions: list of (question_name, points). Returns a standalone Quiz name
    (standalone avoids the Course Schedule wiring so we can score in isolation)."""
    quiz = frappe.new_doc("Quiz")
    quiz.title = f"TQ-{frappe.generate_hash(length=8)}"
    quiz.standalone = 1
    quiz.passing_percentage = passing_percentage
    for qname, points in questions:
        quiz.append(
            "questions", {"question": qname, "points": points, "type": "Choices"}
        )
    quiz.insert(ignore_permissions=True)
    return quiz.name


def _summary(quiz, answers):
    """answers: list of (question_name, selected_list)."""
    results = [
        {
            "question_name": qname,
            "selected": selected,
            "answer": ", ".join(selected),
            "is_correct": [],
        }
        for qname, selected in answers
    ]
    return quiz_summary(quiz, results=json.dumps(results))


class TestQuiz(IntegrationTestCase):
    # --- choice_is_correct: authoritative set-equality verdict (#182 + latent multi-correct) ---

    def test_single_correct_pass_and_fail(self):
        q = _make_choice_question(["A", "B", "C", "D"], {1})
        self.assertEqual(choice_is_correct(q, ["A"]), 1)
        self.assertEqual(choice_is_correct(q, ["B"]), 0)
        self.assertEqual(choice_is_correct(q, []), 0)
        self.assertEqual(choice_is_correct(q, ["A", "B"]), 0)

    def test_two_option_question_grades_correctly(self):
        # Issue #182: a question with only options 1-2 filled (slots 3-4 empty)
        # must still be gradable instead of always scoring 0.
        q = _make_choice_question(["A", "B"], {1})
        self.assertEqual(choice_is_correct(q, ["A"]), 1)
        self.assertEqual(choice_is_correct(q, ["B"]), 0)

    def test_multi_correct_set_equality(self):
        q = _make_choice_question(["A", "B", "C", "D"], {1, 2})
        self.assertEqual(choice_is_correct(q, ["A", "B"]), 1)  # exact set
        self.assertEqual(choice_is_correct(q, ["A"]), 0)  # latent bug: missed one
        self.assertEqual(choice_is_correct(q, ["A", "B", "C"]), 0)  # extra wrong
        self.assertEqual(choice_is_correct(q, []), 0)

    # --- check_choice_answers: per-option list shape must remain for the review UI ---

    def test_check_choice_answers_returns_four_element_list(self):
        q = _make_choice_question(["A", "B"], {1})
        out = check_choice_answers(q, ["A"])
        self.assertIsInstance(out, list)
        self.assertEqual(len(out), 4)

    # --- quiz_summary: end-to-end scoring + pass threshold (#181, #182) ---

    def test_two_option_quiz_scores_and_passes(self):
        # #182 end-to-end: 2-option question, correct selection -> full score, pass.
        q = _make_choice_question(["A", "B"], {1})
        quiz = _make_quiz([(q, 1)], passing_percentage=50)
        res = _summary(quiz, [(q, ["A"])])
        self.assertEqual(res["score"], 1)
        self.assertEqual(res["percentage"], 100)
        self.assertTrue(res["pass"])

    def test_multi_correct_missing_one_scores_zero(self):
        # Latent bug: omitting a required correct option must score 0, not full marks.
        q = _make_choice_question(["A", "B", "C", "D"], {1, 2})
        quiz = _make_quiz([(q, 1)], passing_percentage=50)
        res = _summary(quiz, [(q, ["A"])])
        self.assertEqual(res["score"], 0)
        self.assertFalse(res["pass"])

    def test_pass_uses_greater_or_equal(self):
        # #181: pass must be percentage >= passing, not exact equality.
        q1 = _make_choice_question(["A", "B"], {1})
        q2 = _make_choice_question(["A", "B"], {1})

        # Score exactly at threshold (50% of two single-correct questions) -> pass.
        at_threshold = _make_quiz([(q1, 1), (q2, 1)], passing_percentage=50)
        res = _summary(at_threshold, [(q1, ["A"]), (q2, ["B"])])  # 1 of 2 correct
        self.assertEqual(res["percentage"], 50)
        self.assertTrue(res["pass"])  # == threshold

        # Score above threshold -> pass (the bug reported this as a fail).
        above = _make_quiz([(q1, 1), (q2, 1)], passing_percentage=50)
        res = _summary(above, [(q1, ["A"]), (q2, ["A"])])  # both correct
        self.assertEqual(res["percentage"], 100)
        self.assertTrue(res["pass"])

        # Score below threshold -> fail.
        below = _make_quiz([(q1, 1), (q2, 1)], passing_percentage=50)
        res = _summary(below, [(q1, ["B"]), (q2, ["B"])])  # both wrong
        self.assertEqual(res["percentage"], 0)
        self.assertFalse(res["pass"])
