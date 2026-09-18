# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""p006 Phase 0, F5 (privatedocs p006-OWASP-ADR-Phase0.md §2.5): ``lift_hold``
requires a registrar role."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.student_standing import lift_hold

STUDENT = "p006-hold-stu@example.com"
REGISTRAR = "p006-hold-reg@example.com"


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


class TestP006LiftHoldGate(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _ensure_user(STUDENT, ["Student"])
        cls.registrar = _ensure_user(REGISTRAR, ["Registrar"])

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def test_student_cannot_lift_hold(self):
        frappe.set_user(self.student)
        self.assertRaises(
            frappe.PermissionError,
            lift_hold,
            "P006-NONEXISTENT",
            "P006-NONEXISTENT-ROW",
        )

    def test_registrar_passes_gate(self):
        # No real hold is needed: the gate is the first line, and the writes
        # below it are no-ops on a missing row / student.
        frappe.set_user(self.registrar)
        self.assertEqual(
            lift_hold("P006-NONEXISTENT", "P006-NONEXISTENT-ROW"), "P006-NONEXISTENT"
        )
