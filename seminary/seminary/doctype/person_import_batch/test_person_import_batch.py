# Copyright (c) 2026, Seminary and contributors
# See license.txt

import unittest

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.doctype.person_import_batch import person_import_batch as pib


class TestPersonImportHelpers(unittest.TestCase):
    """Pure helpers — no DB."""

    def test_truthy(self):
        for v in ("1", "true", "YES", "x", "Checked", "t"):
            self.assertEqual(pib._truthy(v), 1)
        for v in ("0", "", "no", None, "false", "maybe"):
            self.assertEqual(pib._truthy(v), 0)

    def test_full_name_joins_parts(self):
        row = frappe._dict(first_name="Ada", middle_name=None, last_name="Lovelace")
        self.assertEqual(pib._full_name(row), "Ada Lovelace")

    def test_full_name_blank_returns_none(self):
        row = frappe._dict(first_name=None, middle_name=None, last_name=None)
        self.assertIsNone(pib._full_name(row))

    def test_needs_desk_and_user(self):
        student = frappe._dict(
            is_student=1,
            is_instructor=0,
            is_alumni=0,
            is_donor=0,
            is_registrar=0,
            is_programchair=0,
            is_seminarymanager=0,
        )
        self.assertFalse(pib._needs_desk(student))
        self.assertTrue(pib._needs_user(student))

        donor = frappe._dict(
            is_student=0,
            is_instructor=0,
            is_alumni=0,
            is_donor=1,
            is_registrar=0,
            is_programchair=0,
            is_seminarymanager=0,
        )
        self.assertFalse(pib._needs_desk(donor))
        self.assertFalse(pib._needs_user(donor))  # pure donor needs no login

        registrar = frappe._dict(
            is_student=0,
            is_instructor=0,
            is_alumni=0,
            is_donor=0,
            is_registrar=1,
            is_programchair=0,
            is_seminarymanager=0,
        )
        self.assertTrue(pib._needs_desk(registrar))
        self.assertTrue(pib._needs_user(registrar))


class IntegrationTestPersonImportBatch(IntegrationTestCase):
    """Changes are rolled back after each test by IntegrationTestCase."""

    def _new_batch(self, rows):
        batch = frappe.new_doc("Person Import Batch")
        for r in rows:
            batch.append("rows", r)
        batch.insert(ignore_permissions=True)
        return batch

    def test_dry_run_flags_bad_email_and_no_role(self):
        batch = self._new_batch(
            [
                {"primary_email": "not-an-email", "first_name": "Bad"},
                {"primary_email": "norole@example.com", "first_name": "NoRole"},
            ]
        )
        result = batch.dry_run()
        self.assertFalse(result["clean"])
        self.assertEqual(batch.rows[0].row_status, "Error")
        self.assertIn("bad_email", batch.rows[0].messages)
        # second row is only a warning (no role selected), not an error
        self.assertEqual(batch.rows[1].row_status, "Warning")
        self.assertIn("no_role_selected", batch.rows[1].messages)

    def test_dry_run_clean_after_override(self):
        batch = self._new_batch(
            [
                {
                    "primary_email": "override@example.com",
                    "first_name": "Over",
                    "override_note": "bare person on purpose",
                }
            ]
        )
        result = batch.dry_run()
        # only warning was no_role_selected, and it's overridden -> clean
        self.assertTrue(result["clean"])
        self.assertEqual(batch.batch_status, "Dry-Run Clean")

    def test_commit_bare_person_is_idempotent(self):
        email = "bare.person@example.com"
        batch = self._new_batch(
            [{"primary_email": email, "first_name": "Bare", "last_name": "Person"}]
        )
        batch._commit_rows()

        person = frappe.db.get_value("Person", {"primary_email": email})
        self.assertTrue(person)
        self.assertEqual(batch.rows[0].created_person, person)
        self.assertEqual(batch.rows[0].row_status, "Committed")
        # no roles -> no User created
        self.assertFalse(batch.rows[0].created_user)

        # Re-running resolves to the same Person (no duplicate).
        batch2 = self._new_batch(
            [{"primary_email": email, "first_name": "Bare", "last_name": "Person"}]
        )
        batch2._commit_rows()
        self.assertEqual(batch2.rows[0].created_person, person)
        self.assertEqual(frappe.db.count("Person", {"primary_email": email}), 1)

    def test_commit_student_creates_user_and_person(self):
        email = "student.import@example.com"
        batch = self._new_batch(
            [
                {
                    "primary_email": email,
                    "first_name": "Stu",
                    "last_name": "Dent",
                    "is_student": 1,
                }
            ]
        )
        batch._commit_rows()

        student = batch.rows[0].created_student
        self.assertTrue(student)
        self.assertTrue(batch.rows[0].created_user)
        self.assertEqual(batch.rows[0].created_user, email)

        person = batch.rows[0].created_person
        self.assertTrue(person)
        # Student, User and Person are all linked to the same identity.
        self.assertEqual(frappe.db.get_value("Student", student, "person"), person)
        self.assertEqual(frappe.db.get_value("Person", person, "user"), email)
        # Welcome email suppressed by default.
        self.assertEqual(
            frappe.db.get_value("User", email, "send_welcome_email") or 0, 0
        )

    def test_permission_role_assignment(self):
        if not frappe.db.exists("Role", "Registrar"):
            self.skipTest("Registrar role not installed")
        email = "registrar.import@example.com"
        batch = self._new_batch(
            [
                {
                    "primary_email": email,
                    "first_name": "Reg",
                    "last_name": "Istrar",
                    "is_registrar": 1,
                }
            ]
        )
        batch._commit_rows()

        self.assertEqual(batch.rows[0].created_user, email)
        roles = {r.role for r in frappe.get_doc("User", email).roles}
        self.assertIn("Registrar", roles)
        self.assertEqual(frappe.db.get_value("User", email, "user_type"), "System User")
        self.assertIn("Registrar", batch.rows[0].assigned_roles)
