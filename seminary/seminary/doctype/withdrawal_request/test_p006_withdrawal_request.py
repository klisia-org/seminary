# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""p006 Phase 0, F6 (privatedocs p006-OWASP-ADR-Phase0.md §2.6): the whitelisted
``initiate_program_separation`` is registrar-only; the body lives in
``_initiate_program_separation`` for server-side callers."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.doctype.withdrawal_request import withdrawal_request

STUDENT = "p006-wr-stu@example.com"


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


class TestP006ProgramSeparationGate(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _ensure_user(STUDENT, ["Student"])

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def test_student_cannot_initiate_program_separation(self):
        frappe.set_user(self.student)
        self.assertRaises(
            frappe.PermissionError,
            withdrawal_request.initiate_program_separation,
            "P006-NONEXISTENT-PE",
            "P006-NONEXISTENT-REASON",
        )

    def test_internal_body_is_ungated(self):
        # The disciplinary path calls the body directly; it must not carry the
        # registrar gate (its own flow authorises the instructor).
        self.assertNotIn(
            withdrawal_request._initiate_program_separation, frappe.whitelisted
        )
        self.assertIn(
            withdrawal_request.initiate_program_separation, frappe.whitelisted
        )
