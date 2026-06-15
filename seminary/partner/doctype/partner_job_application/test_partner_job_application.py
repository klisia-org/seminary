# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

# These tests build their own Partner Organization / Person / Job Opening records
# in setUpClass, so the recursive auto-loader for link-field test records is not
# needed — and skipping it avoids dragging in ERPNext's Customer test record, whose
# bootstrap needs an active Fiscal Year for the current date.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Customer", "Person"]


class IntegrationTestPartnerJobApplication(IntegrationTestCase):
    """Integration tests for the Partner Job Application ATS pipeline (ADR 053)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = frappe.get_doc(
            {
                "doctype": "Partner Organization",
                "organization_name": "Test Grace Church (PJA)",
                "status": "Active",
            }
        ).insert(ignore_permissions=True)
        cls.person = frappe.get_doc(
            {
                "doctype": "Person",
                "first_name": "Pja",
                "last_name": "Applicant",
                "primary_email": "pja.applicant@example.com",
                "resume": "/private/files/pja-resume.pdf",
            }
        ).insert(ignore_permissions=True)

    def _make_opening(self, **kwargs):
        opening = frappe.get_doc(
            {
                "doctype": "Partner Job Opening",
                "partner_org": self.org.name,
                "job_title": "Associate Pastor",
                "planned_vacancies": 1,
                "status": "Open",
                **kwargs,
            }
        ).insert(ignore_permissions=True)
        return opening

    def test_resume_defaults_from_person(self):
        opening = self._make_opening()
        app = frappe.get_doc(
            {
                "doctype": "Partner Job Application",
                "job_opening": opening.name,
                "applicant": self.person.name,
            }
        ).insert(ignore_permissions=True)
        self.assertEqual(app.resume, "/private/files/pja-resume.pdf")
        self.assertEqual(app.full_name, self.person.full_name)

    def test_duplicate_application_rejected(self):
        opening = self._make_opening()
        frappe.get_doc(
            {
                "doctype": "Partner Job Application",
                "job_opening": opening.name,
                "applicant": self.person.name,
            }
        ).insert(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Partner Job Application",
                    "job_opening": opening.name,
                    "applicant": self.person.name,
                }
            ).insert(ignore_permissions=True)

    def test_average_rating_computed(self):
        opening = self._make_opening()
        app = frappe.get_doc(
            {
                "doctype": "Partner Job Application",
                "job_opening": opening.name,
                "applicant": self.person.name,
                "reviews": [
                    {"reviewer": self.person.name, "rating": 1.0},
                    {"reviewer": self.person.name, "rating": 0.6},
                ],
            }
        ).insert(ignore_permissions=True)
        self.assertAlmostEqual(app.average_rating, 0.8)

    def test_accept_decrements_vacancies_and_closes(self):
        opening = self._make_opening(planned_vacancies=1)
        app = frappe.get_doc(
            {
                "doctype": "Partner Job Application",
                "job_opening": opening.name,
                "applicant": self.person.name,
            }
        ).insert(ignore_permissions=True)
        app.status = "Accepted"
        app.save(ignore_permissions=True)
        opening.reload()
        self.assertEqual(opening.vacancies, 0)
        self.assertEqual(opening.status, "Closed")

    def test_students_only_opening_blocks_non_student(self):
        opening = self._make_opening(open_students=1)
        # self.person is not a Student, so the students-only opening rejects them.
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Partner Job Application",
                    "job_opening": opening.name,
                    "applicant": self.person.name,
                }
            ).insert(ignore_permissions=True)
