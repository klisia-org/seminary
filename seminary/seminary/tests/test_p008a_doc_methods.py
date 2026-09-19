# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p008a G10: whitelisted DOCUMENT methods gate themselves.

``run_doc_method`` admits a caller on READ of the document alone. The G10
inventory (scripts/p008a_validation/inventory.md) found four writers that relied
on that: three Desk-button document methods, and one registrar action whose
``db_set`` ran before its permission-checked save."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.tests.test_p006_api import _make_user


class TestP008aDocMethods(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _make_user("Student", "g10-student")
        cls.instructor = _make_user("Instructor", "g10-instr")
        cls.chair = _make_user("Program Chair", "g10-chair")
        cls.registrar = _make_user("Registrar", "g10-reg")

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_schedule_dates_needs_write_on_the_section(self):
        for user in (self.student, self.instructor):  # instructor: on no section
            frappe.set_user(user)
            with self.subTest(user=user), self.assertRaises(frappe.PermissionError):
                frappe.new_doc("Course Schedule").schedule_dates(days=[])

    def test_raising_an_invoice_needs_write_on_the_enrollment(self):
        for user in (self.student, self.instructor, self.chair):
            frappe.set_user(user)
            with self.subTest(user=user), self.assertRaises(frappe.PermissionError):
                frappe.new_doc("Course Enrollment Individual").get_inv_data_ce()

    def test_create_supplier_is_not_self_service(self):
        for user in (self.student, self.instructor):
            frappe.set_user(user)
            with self.subTest(user=user), self.assertRaises(frappe.PermissionError):
                frappe.new_doc("Instructor").create_supplier()

    def test_create_supplier_admits_the_chair_past_the_gate(self):
        frappe.set_user(self.chair)
        doc = frappe.new_doc("Instructor")
        doc.supplier = "ZZT-already-linked"  # returns before touching Supplier
        self.assertEqual(doc.create_supplier(), "ZZT-already-linked")

    def test_withdraw_orphan_requirement_is_registrar_only(self):
        from seminary.seminary.graduation import withdraw_orphan_requirement

        for user in (self.student, self.instructor):
            frappe.set_user(user)
            with self.subTest(user=user), self.assertRaises(frappe.PermissionError):
                withdraw_orphan_requirement("ZZT-no-such-pe", "ZZT-no-such-row")
        frappe.set_user(self.registrar)
        with self.assertRaises(frappe.DoesNotExistError):  # past the gate
            withdraw_orphan_requirement("ZZT-no-such-pe", "ZZT-no-such-row")
