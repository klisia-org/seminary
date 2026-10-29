# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/094: a school's history imported from another system."""

from contextlib import contextmanager

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_months, getdate, today

from seminary.seminary import comms
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr091_requirements import _doc_type, _program, _rule


@contextmanager
def importing():
    frappe.flags.in_import = True
    try:
        yield
    finally:
        frappe.flags.in_import = False


def _past_enrollment(student, program, **values):
    """Built with new_doc, as Data Import does, so defaults are in place."""
    pe = frappe.new_doc("Program Enrollment")
    pe.update(
        {
            "student": student.name,
            "program": program.name,
            "academic_term": fx.current_term(),
            "enrollment_date": add_days(today(), -900),
            **values,
        }
    )
    pe.insert(ignore_permissions=True)
    pe.submit()
    return pe


def _partner(internal_legacy):
    scale = frappe.get_all(
        "Grading Scale", filters={"docstatus": 1}, limit=1, pluck="name"
    )[0]
    policy = frappe.get_doc(
        {
            "doctype": "Grade Conversion Policy",
            "policy_name": fx.uid("Identity"),
            "conversion_method": "identity",
            "source_grading_scale": scale,
            "target_grading_scale": scale,
        }
    ).insert(ignore_permissions=True)
    policy.submit()
    return frappe.get_doc(
        {
            "doctype": "Partner Seminary",
            "partner_seminary_name": fx.uid("Partner"),
            "default_grading_scale": scale,
            "default_conversion_policy": policy.name,
            "is_internal_legacy": internal_legacy,
        }
    ).insert(ignore_permissions=True)


def _commit_transcript(partner, student, program, **row):
    """The commit step alone: rows arrive as a clean dry-run leaves them."""
    batch = frappe.new_doc("Partner Transcript Import Batch")
    batch.update(
        {
            "partner_seminary": partner.name,
            "target_program": program.name,
            "target_academic_term": fx.current_term(),
        }
    )
    batch.append(
        "rows",
        {
            "student": student.name,
            "source_course_code": "HIST-101",
            "source_grade": "A",
            "resolved_internal_course": "History",
            "resolved_credit": 3,
            "resolved_grade_code": "A",
            **row,
        },
    )
    batch._commit_rows()
    return frappe.get_doc(
        "Program Enrollment",
        {"student": student.name, "program": program.name, "docstatus": 1},
    )


class IntegrationTestHistory(IntegrationTestCase):
    def setUp(self):
        self.document_type = _doc_type(needs_review=0, valid_months=12)
        self.program = _program([_rule("Document", self.document_type.name)])
        self.student = fx.make_student()

    # §2 past enrolments arrive finished

    def test_a_graduated_enrollment_arrives_finished(self):
        ended = add_days(today(), -30)
        with importing():
            pe = _past_enrollment(
                self.student, self.program, status="Graduated", date_of_conclusion=ended
            )
        pe.reload()
        self.assertEqual((pe.status, pe.pgmenrol_active), ("Graduated", 0))
        [history] = pe.status_history
        self.assertEqual(
            (history.from_status, history.to_status, getdate(history.effective_date)),
            ("Active", "Graduated", getdate(ended)),
        )
        leaving = frappe.get_all(
            "Student Leaving Record",
            filters={"parent": self.student.name, "program_enrollment": pe.name},
            fields=["reason_for_leaving", "date_of_leaving"],
        )
        self.assertEqual(len(leaving), 1)
        self.assertEqual(getdate(leaving[0].date_of_leaving), getdate(ended))
        self.assertEqual(pe.grad_candidate or 0, 0)

    def test_a_past_date_is_still_refused_outside_an_import(self):
        with self.assertRaises(frappe.ValidationError):
            _past_enrollment(self.student, self.program)

    def test_a_finished_enrollment_needs_its_end_date(self):
        with importing(), self.assertRaises(frappe.ValidationError):
            _past_enrollment(self.student, self.program, status="Withdrawn")

    def test_leave_is_not_imported(self):
        with importing(), self.assertRaises(frappe.ValidationError):
            _past_enrollment(self.student, self.program, status="Leave of Absence")

    # §1 imported history does not act

    def test_an_imported_enrollment_opens_no_requirements_and_sends_nothing(self):
        logs = frappe.db.count("Communication Log")
        with importing():
            pe = _past_enrollment(self.student, self.program)
        self.assertEqual(pe.status, "Active")
        self.assertFalse(
            frappe.db.exists("Person Requirement", {"reference_name": pe.name})
        )
        self.assertEqual(frappe.db.count("Communication Log"), logs)

        # The same enrollment made today opens its requirement.
        other = fx.make_enrollment(fx.make_student(), self.program)
        self.assertTrue(
            frappe.db.exists("Person Requirement", {"reference_name": other.name})
        )

    def test_nothing_is_queued_while_importing(self):
        with importing():
            self.assertIsNone(
                comms.send_message(
                    channel="Email",
                    message="Hello",
                    subject="Hello",
                    to_address="someone@example.test",
                )
            )

    def test_an_imported_student_gets_no_welcome_email(self):
        person = fx.make_person(
            "Imported", email="past.%s@example.test" % frappe.generate_hash(length=8)
        )
        with importing():
            student = fx.make_student(person)
        user = frappe.db.get_value("Student", student.name, "user")
        self.assertTrue(user)
        self.assertEqual(frappe.db.get_value("User", user, "send_welcome_email"), 0)

    # §3 attendance as a summary

    def test_attendance_cannot_exceed_sessions_held(self):
        pe = fx.make_enrollment(self.student, fx.make_program(), submit=False)
        pe.reload()
        pe.append(
            "courses",
            {"course_name": "History", "sessions_attended": 12, "sessions_held": 10},
        )
        with self.assertRaises(frappe.ValidationError):
            pe.save()
        pe.reload()
        pe.append(
            "courses",
            {"course_name": "History", "sessions_attended": 9, "sessions_held": 10},
        )
        pe.save()

    def test_our_past_students_coursework_is_history_but_a_transfer_is_not(self):
        pe = _commit_transcript(
            _partner(internal_legacy=1),
            self.student,
            self.program,
            sessions_attended=11,
            sessions_held=12,
        )
        self.assertFalse(
            frappe.db.exists("Person Requirement", {"reference_name": pe.name})
        )
        self.assertEqual(
            (pe.courses[0].sessions_attended, pe.courses[0].sessions_held), (11, 12)
        )
        self.assertFalse(frappe.flags.in_import)

        transfer = _commit_transcript(
            _partner(internal_legacy=0), fx.make_student(), self.program
        )
        self.assertTrue(
            frappe.db.exists("Person Requirement", {"reference_name": transfer.name})
        )

    # §4 documents

    def test_an_imported_document_is_valid_from_when_it_was_submitted(self):
        submitted = add_days(today(), -200)
        with importing():
            doc = frappe.get_doc(
                {
                    "doctype": "Person Document",
                    "person": self.student.person,
                    "document_type": self.document_type.name,
                    "file": "/private/files/diploma.pdf",
                    "status": "Accepted",
                    "submitted_on": submitted,
                }
            ).insert(ignore_permissions=True)
        self.assertEqual(doc.status, "Accepted")
        self.assertEqual(getdate(doc.valid_until), getdate(add_months(submitted, 12)))

    def tearDown(self):
        frappe.flags.in_import = False
