# Copyright (c) 2026, Seminary and contributors
# For license information, please see license.txt
"""The Person importer and the school's billing app (aretenic decision 050).

Kept outside the doctype folder on purpose: a test module there makes Frappe
build test records for every linked doctype, and the Instructor record cannot
be built since the person-first spine."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.doctype.person_import_batch import person_import_batch as pib


class IntegrationTestPreviousStudentId(IntegrationTestCase):
    """The school's own student number is kept on the Student (aretenic
    decision 050 §2), and billing records are the billing app's business."""

    def _new_batch(self, rows):
        batch = frappe.new_doc("Person Import Batch")
        for r in rows:
            batch.append("rows", r)
        batch.insert(ignore_permissions=True)
        return batch

    def _row(self, email, **extra):
        return {
            "primary_email": email,
            "first_name": "Luke",
            "last_name": "Skywalker",
            "is_student": 1,
            **extra,
        }

    def test_the_previous_id_is_kept_and_never_replaced(self):
        email = "prev.id@example.com"
        batch = self._new_batch([self._row(email, previous_student_id=" 965458 ")])
        batch._commit_rows()
        student = batch.rows[0].created_student
        self.assertEqual(
            frappe.db.get_value("Student", student, "previous_student_id"), "965458"
        )

        again = self._new_batch([self._row(email, previous_student_id="111111")])
        again._commit_rows()
        self.assertEqual(again.rows[0].created_student, student)
        self.assertEqual(
            frappe.db.get_value("Student", student, "previous_student_id"), "965458"
        )

    def test_dry_run_checks_the_previous_id(self):
        taken = self._new_batch(
            [self._row("prev.taken@example.com", previous_student_id="777777")]
        )
        taken._commit_rows()
        batch = self._new_batch(
            [
                self._row("prev.a@example.com", previous_student_id="555555"),
                self._row("prev.b@example.com", previous_student_id="555555"),
                self._row("prev.c@example.com", previous_student_id="777777"),
                {
                    "primary_email": "prev.d@example.com",
                    "first_name": "D",
                    "is_alumni": 1,
                    "previous_student_id": "888888",
                },
            ]
        )
        batch.dry_run()
        messages = [r.messages or "" for r in batch.rows]
        self.assertNotIn("previous_student_id", messages[0])
        self.assertIn("duplicate_previous_student_id:555555", messages[1])
        self.assertIn("previous_student_id_taken:777777", messages[2])
        self.assertIn("previous_student_id_needs_student", messages[3])

    def test_academic_only_follows_the_billing_app(self):
        from unittest.mock import patch

        from seminary.seminary.financial import backend

        class Billing:
            def has_financials(self):
                return True

        batch = self._new_batch([self._row("billing.app@example.com")])
        with patch.object(pib, "get_financial_backend", return_value=Billing()):
            batch.dry_run()
            self.assertNotIn("student_academic_only", batch.rows[0].messages or "")
            self.assertFalse(
                pib._customer_billing(), "only oikonomos makes a Customer per student"
            )
        with patch.object(
            pib, "get_financial_backend", return_value=backend.NullFinancialBackend()
        ):
            batch.dry_run()
            self.assertIn("student_academic_only", batch.rows[0].messages or "")
