# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""p006 Phase 0, F7 + F13 on Exam Submission (privatedocs/p006-OWASP-ADR-Phase0.md
§2.7, §2.13): grade writers require a grader, student-owned writers require the
owner, and grader comments are sanitised on the way in."""

import json
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.doctype.exam_submission.exam_submission import (
    save_exam_comment,
    save_exam_draft,
    save_exam_grade,
    submit_exam,
)

STUDENT_A = "p006-exam-stu-a@example.com"
STUDENT_B = "p006-exam-stu-b@example.com"
BYPASS = "<!--><img src=x onerror=alert(1)>-->"


def _ensure_user(email, roles):
    if not frappe.db.exists("User", email):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": email.split("@")[0],
                "send_welcome_email": 0,
            }
        )
        user.flags.no_welcome_mail = True
        user.insert(ignore_permissions=True)
    frappe.get_doc("User", email).add_roles(*roles)
    return email


def _ensure_exam():
    """An Exam Activity with one question row. The row's Open Question link
    is a placeholder (links/mandatory ignored) so no question bank fixture is
    needed; the row itself must exist because Exam Question Result links it
    and a real save validates that link. Returns (exam, question_row)."""
    title = "P006 Gate Exam"
    name = frappe.db.get_value("Exam Activity", {"title": title}, "name")
    if not name:
        doc = frappe.get_doc(
            {
                "doctype": "Exam Activity",
                "title": title,
                "questions": [{"question": "P006-PLACEHOLDER-OQ", "points": 1}],
            }
        )
        doc.flags.ignore_links = True
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        name = doc.name
    return name, frappe.db.get_value("Exam Question", {"parent": name}, "name")


@contextmanager
def _without_dangling_fetch():
    """exam_submission.json fetches ``passing_percentage`` from Exam Activity,
    which has no such field, so any save that validates the ``exam`` link
    fails with an unknown-column error. That is pre-existing and outside p006
    Phase 0; drop the fetch on the cached meta for the duration of a save so
    the save paths can be exercised here."""
    df = frappe.get_meta("Exam Submission").get_field("passing_percentage")
    if not df or not df.fetch_from:
        yield
        return
    with patch.object(df, "fetch_from", None):
        yield


def _make_draft(exam, member, question=None):
    """A draft, optionally with one result row for ``question``; links and
    mandatory fields are ignored so no Course Schedule is needed."""
    doc = frappe.get_doc(
        {
            "doctype": "Exam Submission",
            "exam": exam,
            "member": member,
            "status": "Not Submitted",
            "result": [{"question": question, "answer": "x"}] if question else [],
        }
    )
    doc.flags.ignore_links = True
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc


class TestP006ExamSubmissionGates(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student_a = _ensure_user(STUDENT_A, ["Student"])
        cls.student_b = _ensure_user(STUDENT_B, ["Student"])
        cls.exam, cls.question = _ensure_exam()

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    # --- F7: grade writers require a grader ------------------------------
    def test_student_cannot_save_exam_grade(self):
        draft = _make_draft(self.exam, self.student_a)
        frappe.set_user(self.student_a)
        self.assertRaises(
            frappe.PermissionError,
            save_exam_grade,
            draft.name,
            "Graded",
            10,
            100,
            0,
            json.dumps([]),
        )

    def test_student_cannot_save_exam_comment(self):
        draft = _make_draft(self.exam, self.student_a, self.question)
        frappe.set_user(self.student_a)
        self.assertRaises(
            frappe.PermissionError,
            save_exam_comment,
            draft.name,
            draft.result[0].name,
            "nice try",
        )

    # --- F7: student-owned writers require the owner ----------------------
    def test_student_cannot_submit_another_members_draft(self):
        draft = _make_draft(self.exam, self.student_b)
        frappe.set_user(self.student_a)
        self.assertRaises(frappe.PermissionError, submit_exam, draft.name)
        self.assertEqual(
            frappe.db.get_value("Exam Submission", draft.name, "status"),
            "Not Submitted",
        )

    def test_student_can_submit_own_draft(self):
        draft = _make_draft(self.exam, self.student_a)
        frappe.set_user(self.student_a)
        with _without_dangling_fetch():
            doc = submit_exam(draft.name)
        self.assertEqual(doc.status, "Not Graded")

    def test_save_exam_draft_ignores_member_argument(self):
        frappe.set_user(self.student_a)
        with (
            patch(
                "seminary.seminary.utils.user_is_enrolled_in_course",
                return_value=True,
            ),
            _without_dangling_fetch(),
        ):
            doc = save_exam_draft(self.exam, None, self.student_b, json.dumps([]), 0)
        self.assertEqual(doc.member, self.student_a)
        self.assertEqual(
            frappe.db.get_value("Exam Submission", doc.name, "member"), self.student_a
        )

    def test_save_exam_draft_requires_enrollment(self):
        frappe.set_user(self.student_a)
        with patch(
            "seminary.seminary.utils.user_is_enrolled_in_course", return_value=False
        ):
            self.assertRaises(
                frappe.PermissionError,
                save_exam_draft,
                self.exam,
                None,
                self.student_a,
                json.dumps([]),
                0,
            )

    def test_save_exam_draft_cannot_update_another_members_draft(self):
        draft = _make_draft(self.exam, self.student_b)
        frappe.set_user(self.student_a)
        with patch(
            "seminary.seminary.utils.user_is_enrolled_in_course", return_value=True
        ):
            self.assertRaises(
                frappe.PermissionError,
                save_exam_draft,
                self.exam,
                None,
                self.student_a,
                json.dumps([]),
                0,
                draft.name,
            )

    # --- F13: grader comments are sanitised -------------------------------
    def test_grader_comments_are_sanitised(self):
        draft = _make_draft(self.exam, self.student_a, self.question)
        row = draft.result[0].name
        # Administrator holds System Manager, a grader role.
        save_exam_comment(draft.name, row, BYPASS)
        stored = frappe.db.get_value("Exam Question Result", row, "comments")
        self.assertNotIn("onerror", stored)

        with _without_dangling_fetch():
            save_exam_grade(
                draft.name,
                "Graded",
                1,
                100,
                0,
                json.dumps(
                    [{"name": row, "points": 1, "graded": 1, "comments": BYPASS}]
                ),
            )
        stored = frappe.db.get_value("Exam Question Result", row, "comments")
        self.assertNotIn("onerror", stored)
