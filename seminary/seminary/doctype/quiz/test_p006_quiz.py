# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""p006 Phase 0, F7 + F13 on quiz_summary (privatedocs p006-OWASP-ADR-Phase0.md
§2.7, §2.13): User Input questions are graded on the server, ignoring the
client-sent ``is_correct``; the stored answer is sanitised."""

import json

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.doctype.quiz.quiz import quiz_summary

BYPASS = "<!--><img src=x onerror=alert(1)>-->"


def _make_input_question(possibility):
    doc = frappe.new_doc("Question")
    doc.question = f"QI-{frappe.generate_hash(length=8)}"
    doc.type = "User Input"
    doc.possibility_1 = possibility
    doc.insert(ignore_permissions=True)
    return doc.name


def _make_quiz(question, points=2):
    """A fresh standalone quiz per call: quiz_summary dedupes submissions of
    the same quiz by the same user within five seconds."""
    quiz = frappe.new_doc("Quiz")
    quiz.title = f"TQI-{frappe.generate_hash(length=8)}"
    quiz.standalone = 1
    quiz.passing_percentage = 50
    quiz.append(
        "questions", {"question": question, "points": points, "type": "User Input"}
    )
    quiz.insert(ignore_permissions=True)
    return quiz.name


def _summary(quiz, question, answer, is_correct):
    results = [{"question_name": question, "answer": answer, "is_correct": is_correct}]
    return quiz_summary(quiz, results=json.dumps(results))


class TestP006QuizUserInput(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.question = _make_input_question("Jerusalem")

    def test_wrong_answer_with_client_is_correct_scores_zero(self):
        quiz = _make_quiz(self.question)
        res = _summary(quiz, self.question, "Babylon", [1])
        self.assertEqual(res["score"], 0)
        self.assertFalse(res["pass"])
        row = frappe.get_all(
            "Quiz Result",
            filters={"parent": res["submission"]},
            fields=["is_correct", "points"],
        )[0]
        self.assertEqual(row.is_correct, 0)
        self.assertEqual(row.points, 0)

    def test_right_answer_with_client_is_incorrect_scores_full(self):
        quiz = _make_quiz(self.question)
        res = _summary(quiz, self.question, "jerusalem", [0])
        self.assertEqual(res["score"], 2)
        self.assertTrue(res["pass"])

    def test_stored_answer_is_sanitised(self):
        quiz = _make_quiz(self.question)
        res = _summary(quiz, self.question, BYPASS, [1])
        stored = frappe.get_all(
            "Quiz Result", filters={"parent": res["submission"]}, pluck="answer"
        )[0]
        self.assertNotIn("onerror", stored)
