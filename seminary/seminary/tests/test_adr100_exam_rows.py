# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""ADR 100a §3 groundwork: an exam draft keeps its answer rows across saves,
so a recording can point at one answer while the exam is open."""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.doctype.exam_submission.exam_submission import save_exam_draft
from seminary.seminary.doctype.exam_submission.test_p006_exam_submission import (
    _ensure_user,
    _without_dangling_fetch,
)

STUDENT = "adr100-rows-stu@example.com"
TITLE = "ADR100 Row Stability Exam"


def _ensure_exam():
    name = frappe.db.get_value("Exam Activity", {"title": TITLE}, "name")
    if not name:
        doc = frappe.get_doc(
            {
                "doctype": "Exam Activity",
                "title": TITLE,
                "questions": [
                    {"question": "ADR100-PLACEHOLDER-OQ1", "points": 1},
                    {"question": "ADR100-PLACEHOLDER-OQ2", "points": 1},
                    {"question": "ADR100-PLACEHOLDER-OQ3", "points": 1},
                ],
            }
        )
        doc.flags.ignore_links = True
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        name = doc.name
    rows = frappe.get_all(
        "Exam Question", {"parent": name}, pluck="name", order_by="idx"
    )
    return name, rows


class TestExamDraftRowsAreStable(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _ensure_user(STUDENT, ["Student"])
        cls.exam, cls.questions = _ensure_exam()

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def _save(self, answers, submission=None):
        frappe.set_user(self.student)
        payload = json.dumps([{"question": q, "answer": a} for q, a in answers])
        with (
            patch(
                "seminary.seminary.utils.user_is_enrolled_in_course",
                return_value=True,
            ),
            _without_dangling_fetch(),
        ):
            return save_exam_draft(self.exam, None, None, payload, 0, submission)

    @staticmethod
    def _rows(submission):
        return {
            r.question: (r.name, r.answer)
            for r in frappe.get_all(
                "Exam Question Result",
                {"parent": submission, "parenttype": "Exam Submission"},
                ["name", "question", "answer"],
            )
        }

    def test_rows_keep_their_names_across_saves(self):
        q1, q2, _q3 = self.questions
        doc = self._save([(q1, "first"), (q2, "")])
        before = self._rows(doc.name)

        for text in ("second", "third"):
            self._save([(q1, text), (q2, "later")], doc.name)

        after = self._rows(doc.name)
        self.assertEqual(before[q1][0], after[q1][0])
        self.assertEqual(before[q2][0], after[q2][0])
        self.assertIn("third", after[q1][1])

    def test_new_question_is_added_and_dropped_one_removed(self):
        q1, q2, q3 = self.questions
        doc = self._save([(q1, "a"), (q2, "b")])
        kept = self._rows(doc.name)[q1][0]

        self._save([(q1, "a2"), (q3, "c")], doc.name)

        rows = self._rows(doc.name)
        self.assertEqual(set(rows), {q1, q3})
        self.assertEqual(rows[q1][0], kept)
        idx = frappe.get_all(
            "Exam Question Result", {"parent": doc.name}, pluck="idx", order_by="idx"
        )
        self.assertEqual(idx, [1, 2])

    def test_answer_log_still_records_each_save(self):
        q1 = self.questions[0]
        doc = self._save([(q1, "one")])
        self._save([(q1, "two")], doc.name)
        self._save([(q1, "three")], doc.name)
        log = frappe.db.get_value("Exam Submission", doc.name, "answer_log") or ""
        self.assertIn("two", log)
        self.assertIn("three", log)

    def test_answers_are_still_sanitised(self):
        q1 = self.questions[0]
        doc = self._save([(q1, "ok")])
        self._save([(q1, "<img src=x onerror=alert(1)>")], doc.name)
        self.assertNotIn("onerror", self._rows(doc.name)[q1][1])
