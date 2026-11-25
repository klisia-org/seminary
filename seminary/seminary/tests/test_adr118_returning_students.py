# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/118: returning and second-degree students keep one Student record."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import admissions, returning
from seminary.seminary.api import enroll_student
from seminary.seminary.doctype.student_applicant.test_student_applicant import make_applicant
from seminary.seminary.student_standing import add_hold
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.catalog_fixtures import ensure_catalog
from seminary.seminary.tests.identity_cleanup import module_hooks

setUpModule, tearDownModule = module_hooks()


def _program(mode="Reviewed"):
	program = fx.make_program()
	program.program_director = fx.make_user(roles=("Instructor",)).name
	program.admission_mode = mode
	program.save(ignore_permissions=True)
	ensure_catalog(program)
	return program


def _status(applicant):
	return frappe.db.get_value("Student Applicant", applicant.name, "application_status")


def _standing(student):
	return frappe.db.get_value("Student", student.name, "student_standing")


class ReturningCase(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.savepoint("adr118_test")
		self.student = fx.make_student()
		self.email = frappe.db.get_value("Person", self.student.person, "primary_email")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.flags.in_web_form = False
		frappe.db.rollback(save_point="adr118_test")
		super().tearDown()

	def _apply(self, mode="Reviewed", **kw):
		return make_applicant(program=_program(mode).name, student_email_id=self.email, **kw)

	def _decide(self, applicant, decision="Admit", **kw):
		doc = frappe.get_doc(
			{"doctype": "Admission Decision", "student_applicant": applicant.name, "decision": decision, **kw}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc

	def _dismiss(self):
		"""A dismissal as the record holds it: a Dismissed enrollment and a Disciplinary hold."""
		pe = fx.make_enrollment(self.student, _program())
		pe.db_set("status", "Dismissed")
		add_hold(self.student.name, "Disciplinary", reason="Plagiarism ruling")
		self.assertEqual(_standing(self.student), "Dismissed")


class TestOneRecord(ReturningCase):
	def test_a_returning_applicant_is_enrolled_on_their_student(self):
		applicant = self._apply()
		self.assertEqual(applicant.returning_student, self.student.name)
		self.assertEqual(applicant.prior_standing, "Good Standing")
		self.assertFalse(applicant.readmission_review)
		self._decide(applicant)

		pe = enroll_student(applicant.name)

		self.assertEqual(pe.student, self.student.name)
		self.assertEqual(pe.student_applicant, applicant.name)
		self.assertEqual(_status(applicant), "Admitted")
		self.assertEqual(frappe.db.count("Student", {"person": self.student.person}), 1)

	def test_a_disabled_student_is_enabled_again(self):
		self.student.db_set("enabled", 0)
		applicant = self._apply()
		self._decide(applicant)
		enroll_student(applicant.name)
		self.assertEqual(frappe.db.get_value("Student", self.student.name, "enabled"), 1)

	def test_a_new_applicant_still_gets_a_new_student(self):
		applicant = make_applicant(program=_program().name)
		self.assertFalse(applicant.returning_student)
		self._decide(applicant)
		pe = enroll_student(applicant.name)
		self.assertNotEqual(pe.student, self.student.name)
		self.assertEqual(pe.student_applicant, applicant.name)


class TestReadmission(ReturningCase):
	def test_a_dismissed_student_is_flagged_and_always_reviewed(self):
		self._dismiss()
		applicant = self._apply(mode="Automatic")
		self.assertTrue(applicant.readmission_review)
		self.assertEqual(applicant.prior_standing, "Dismissed")
		self.assertEqual(_status(applicant), "In Review")
		self.assertIsNone(admissions.latest_decision(applicant.name))
		todo = frappe.get_all(
			"ToDo",
			filters={"reference_type": "Application Review", "status": "Open"},
			fields=["description"],
			order_by="creation desc",
			limit=1,
		)
		self.assertIn("Plagiarism ruling", todo[0].description)

	def test_admitting_needs_a_rationale_and_lifts_the_hold(self):
		self._dismiss()
		applicant = self._apply()
		with self.assertRaises(frappe.ValidationError):
			self._decide(applicant)
		decision = self._decide(applicant, rationale="Completed the restoration plan with the dean.")

		hold = frappe.get_all(
			"Student Hold",
			filters={"parent": self.student.name},
			fields=["is_active", "lifted_through"],
		)[0]
		self.assertEqual((hold.is_active, hold.lifted_through), (0, decision.name))
		# Standing follows the enrollment, which doesn't exist yet.
		self.assertEqual(_standing(self.student), "Dismissed")

		pe = enroll_student(applicant.name)
		pe.submit()
		self.assertEqual(_standing(self.student), "Good Standing")

	def test_cancelling_the_decision_restores_the_hold(self):
		self._dismiss()
		applicant = self._apply()
		decision = self._decide(applicant, rationale="Restored")
		decision.cancel()
		self.assertEqual(frappe.db.get_value("Student Hold", {"parent": self.student.name}, "is_active"), 1)
		self.assertEqual(_standing(self.student), "Dismissed")

	def test_declining_changes_nothing(self):
		self._dismiss()
		applicant = self._apply()
		self._decide(applicant, "Decline")
		self.assertEqual(frappe.db.get_value("Student Hold", {"parent": self.student.name}, "is_active"), 1)

	def test_a_financial_hold_stays(self):
		add_hold(self.student.name, "Financial", reason="Unpaid balance")
		applicant = self._apply()
		self._decide(applicant)
		self.assertEqual(frappe.db.get_value("Student Hold", {"parent": self.student.name}, "is_active"), 1)

	def test_the_flag_is_frozen_once_admitted(self):
		self._dismiss()
		applicant = self._apply()
		self._decide(applicant, rationale="Restored")
		pe = enroll_student(applicant.name)
		pe.submit()
		applicant.reload()
		applicant.save(ignore_permissions=True)
		self.assertEqual(
			frappe.db.get_value("Student Applicant", applicant.name, "prior_standing"), "Dismissed"
		)


class TestSigningIn(ReturningCase):
	def test_a_signed_in_applicant_applies_as_themselves(self):
		user = frappe.db.get_value("Person", self.student.person, "user")
		program = _program()
		frappe.set_user(user)
		frappe.flags.in_web_form = True
		applicant = make_applicant(program=program.name, student_email_id="typed@example.test")
		frappe.flags.in_web_form = False
		frappe.set_user("Administrator")
		self.assertEqual(applicant.student_email_id, frappe.db.get_value("User", user, "email"))
		self.assertEqual(applicant.person, self.student.person)
		self.assertEqual(applicant.returning_student, self.student.name)

	def test_staff_in_desk_keep_the_email_they_type(self):
		frappe.flags.in_web_form = False
		applicant = make_applicant(program=_program().name, student_email_id="someone@example.test")
		self.assertEqual(applicant.student_email_id, "someone@example.test")

	def test_prefill_comes_from_the_person(self):
		user = frappe.db.get_value("Person", self.student.person, "user")
		frappe.set_user(user)
		values = returning.signed_in_prefill()
		self.assertEqual(values["student_email_id"], frappe.db.get_value("User", user, "email"))
		self.assertEqual(
			values.get("first_name"), frappe.db.get_value("Person", self.student.person, "first_name")
		)
		frappe.set_user("Guest")
		self.assertEqual(returning.signed_in_prefill(), {})


class TestLostEmail(ReturningCase):
	def test_a_request_reaches_the_registrars_and_creates_no_person(self):
		registrar = fx.make_user(roles=("Registrar",))
		persons = frappe.db.count("Person")
		returning.request_access(
			full_name="Ana <b>Silva</b>",
			new_email="ana.new@example.test",
			old_email="ana.old@example.test",
			phone="+55 11 99999-0000",
		)
		todo = frappe.get_all(
			"ToDo", filters={"allocated_to": registrar.name}, fields=["description"], limit=1
		)
		self.assertIn("ana.new@example.test", todo[0].description)
		self.assertNotIn("<b>Silva</b>", todo[0].description)
		bell = frappe.get_all(
			"Notification Log",
			filters={"for_user": registrar.name, "document_type": "ToDo"},
			fields=["subject"],
		)
		self.assertEqual(len(bell), 1)
		self.assertIn("Ana", bell[0].subject)
		self.assertEqual(frappe.db.count("Person"), persons)

	def test_a_request_needs_a_name_and_a_valid_email(self):
		with self.assertRaises(frappe.ValidationError):
			returning.request_access(full_name="Ana", new_email="not-an-email")
