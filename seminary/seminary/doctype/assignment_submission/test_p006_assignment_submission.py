# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""p006 Phase 0, F7 + F13 on Assignment Submission (privatedocs
p006-OWASP-ADR-Phase0.md §2.7, §2.13): grading requires a grader, rewriting a
submission requires its owner, students cannot set their own status, and the
validate hook sanitises student-authored HTML (the SPA inserts through
``frappe.client.insert``, so the hook is the only gate)."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.doctype.assignment_submission.assignment_submission import (
    grade_assignment,
    upload_assignment,
)

STUDENT_A = "p006-asg-stu-a@example.com"
STUDENT_B = "p006-asg-stu-b@example.com"
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


def _make_assignment():
    """A Text assignment; the Course link is skipped so no catalogue fixture
    is needed. One per submission: validate_duplicates allows a single
    submission per (assignment, member) and tests are not rolled back
    individually."""
    doc = frappe.get_doc(
        {
            "doctype": "Assignment Activity",
            "title": f"P006-{frappe.generate_hash(length=8)}",
            "type": "Text",
            "grade_assignment": 1,
        }
    )
    doc.flags.ignore_links = True
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    return doc.name


def _make_submission(member, answer="original"):
    doc = frappe.get_doc(
        {
            "doctype": "Assignment Submission",
            "assignment": _make_assignment(),
            "member": member,
            "type": "Text",
            "answer": answer,
            "status": "Not Graded",
        }
    )
    doc.flags.ignore_links = True
    doc.insert(ignore_permissions=True)
    return doc


class TestP006AssignmentSubmissionGates(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student_a = _ensure_user(STUDENT_A, ["Student"])
        cls.student_b = _ensure_user(STUDENT_B, ["Student"])

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    # --- F7 ----------------------------------------------------------------
    def test_student_cannot_grade(self):
        sub = _make_submission(self.student_a)
        frappe.set_user(self.student_a)
        self.assertRaises(
            frappe.PermissionError, grade_assignment, sub.name, "Graded", "x"
        )

    def test_student_cannot_rewrite_another_members_submission(self):
        sub = _make_submission(self.student_b)
        frappe.set_user(self.student_a)
        self.assertRaises(
            frappe.PermissionError,
            upload_assignment,
            answer="hijacked",
            assignment=sub.assignment,
            submission=sub.name,
        )
        self.assertEqual(
            frappe.db.get_value("Assignment Submission", sub.name, "answer"),
            "original",
        )

    def test_student_status_is_always_not_graded(self):
        sub = _make_submission(self.student_a)
        frappe.set_user(self.student_a)
        upload_assignment(
            answer="updated",
            assignment=sub.assignment,
            status="Graded",
            submission=sub.name,
        )
        self.assertEqual(
            frappe.db.get_value("Assignment Submission", sub.name, "status"),
            "Not Graded",
        )

    # --- F13 ---------------------------------------------------------------
    def test_validate_sanitises_answer_and_comments(self):
        sub = _make_submission(self.student_a, answer=BYPASS)
        self.assertNotIn("onerror", sub.answer)
        sub.comments = BYPASS
        sub.save(ignore_permissions=True)
        self.assertNotIn("onerror", sub.comments)

    def test_grade_assignment_sanitises_comments(self):
        sub = _make_submission(self.student_a)
        # Administrator holds System Manager, a grader role.
        grade_assignment(sub.name, "Graded", BYPASS)
        stored = frappe.db.get_value("Assignment Submission", sub.name, "comments")
        self.assertNotIn("onerror", stored)
