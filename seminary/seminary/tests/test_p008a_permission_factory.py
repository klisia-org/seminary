# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p008a G7 (p005a A06-4): the row-permission factory scopes Instructor and
Student and leaves every other role to the DocPerm.

It used to end in a flat refusal for anyone else, and a has_permission hook runs
before the role permissions, so it silently voided DocPerm rows it had never
heard of -- Accounts User / Accounts Manager on Withdrawal Request."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import student_permissions as sp
from seminary.seminary.tests.test_p006_api import _make_user


class TestP008aPermissionFactory(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.accounts = _make_user("Accounts User", "g7-accounts")
        cls.student = _make_user("Student", "g7-student")
        cls.outsider = _make_user("Cohort Participant", "g7-cohort")

    def setUp(self):
        frappe.local.p007_cache = {}

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_a_role_the_docperm_grants_is_not_refused(self):
        self.assertTrue(
            sp._granted_by_another_role("Withdrawal Request", "read", self.accounts)
        )
        self.assertTrue(
            sp._granted_by_another_role("Withdrawal Request", "write", self.accounts)
        )
        self.assertEqual(sp.query_withdrawal_request(self.accounts), "")
        doc = frappe.new_doc("Withdrawal Request")
        self.assertTrue(
            sp.has_permission_withdrawal_request(doc, "read", self.accounts)
        )
        self.assertTrue(
            frappe.has_permission("Withdrawal Request", "read", user=self.accounts)
        )

    def test_the_grant_is_per_doctype(self):
        # Accounts User has no row on Student: the hook has no opinion, and the
        # DocPerm -- which the hook can only narrow -- still refuses.
        self.assertFalse(sp._granted_by_another_role("Student", "read", self.accounts))
        self.assertEqual(sp.query_student(self.accounts), "1=0")
        self.assertFalse(frappe.has_permission("Student", "read", user=self.accounts))

    def test_students_stay_scoped(self):
        self.assertFalse(
            sp._granted_by_another_role("Withdrawal Request", "read", self.student)
        )
        self.assertFalse(sp._granted_by_another_role("Student", "read", self.student))
        # no Student record behind this user: nothing is readable
        self.assertEqual(sp.query_student(self.student), "1=0")

    def test_an_outsider_gains_nothing(self):
        for doctype in ("Student", "Exam Submission", "Withdrawal Request"):
            with self.subTest(doctype=doctype):
                self.assertFalse(
                    sp._granted_by_another_role(doctype, "read", self.outsider)
                )
                self.assertFalse(
                    frappe.has_permission(doctype, "read", user=self.outsider)
                )

    def test_scoped_permlevel_ifowner_and_automatic_rows_do_not_count(self):
        """An "All" row must never switch row scoping off for every student."""
        rows = [
            frappe._dict(role="All", permlevel=0, if_owner=0, read=1),
            frappe._dict(role="Desk User", permlevel=0, if_owner=0, read=1),
            frappe._dict(role="Student", permlevel=0, if_owner=0, read=1),
            frappe._dict(role="Instructor", permlevel=0, if_owner=0, read=1),
            frappe._dict(role="Accounts User", permlevel=1, if_owner=0, read=1),
            frappe._dict(role="Accounts User", permlevel=0, if_owner=1, read=1),
            frappe._dict(
                role="Accounts User", permlevel=0, if_owner=0, read=0, write=1
            ),
        ]
        with patch("frappe.permissions.get_valid_perms", return_value=rows):
            self.assertFalse(sp._granted_by_another_role("Student", "read", "x@y.z"))
            frappe.local.p007_cache = {}
            self.assertTrue(sp._granted_by_another_role("Student", "write", "x@y.z"))
