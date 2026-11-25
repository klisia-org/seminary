# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/113: application fee windows, codes and waiver requests."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from seminary.seminary import admissions
from seminary.seminary import application_fee as fee
from seminary.seminary.doctype.student_applicant.test_student_applicant import make_applicant
from seminary.seminary.financial.backend import NullFinancialBackend
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.identity_cleanup import module_hooks

setUpModule, tearDownModule = module_hooks()


class FakeBackend(NullFinancialBackend):
	"""A school whose programs all charge an application fee."""

	def __init__(self, paid=0.0, outstanding=True):
		self.paid, self.outstanding, self.waived = paid, outstanding, []

	def application_fee_configured(self, program):
		return True

	def application_fee_outstanding(self, applicant_name):
		return self.outstanding

	def application_fee_paid(self, applicant_name):
		return self.paid

	def waive_application_fee(self, applicant_name, percent, reason):
		self.waived.append((applicant_name, percent, reason))
		self.outstanding = percent < 100
		return ["CREDIT"]


def _program(windows=(), requests=0, director=None):
	program = fx.make_program()
	for label, start, end, pct in windows:
		program.append(
			"application_fee_windows",
			{"label": label, "from_date": start, "to_date": end, "discount_percent": pct},
		)
	program.allow_fee_waiver_requests = requests
	program.program_director = director
	program.save(ignore_permissions=True)
	return program


def _code(code=None, pct=50, programs=(), **kw):
	doc = frappe.get_doc(
		{
			"doctype": "Application Fee Code",
			"code": code or fx.uid("code").replace(" ", ""),
			"discount_percent": pct,
			"programs": [{"program": p} for p in programs],
			**kw,
		}
	)
	return doc.insert(ignore_permissions=True)


class FeeCase(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.savepoint("decisions113")
		self.backend = FakeBackend()
		patcher = patch(
			"seminary.seminary.financial.backend.get_financial_backend", return_value=self.backend
		)
		patcher.start()
		self.addCleanup(patcher.stop)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="decisions113")
		super().tearDown()


class TestWindowsAndCodes(FeeCase):
	def test_the_window_holding_the_application_date_gives_its_discount(self):
		today = nowdate()
		program = _program(
			[
				("Early", add_days(today, -10), add_days(today, 5), 100),
				("Late", add_days(today, 6), add_days(today, 30), 25),
			]
		)
		applicant = make_applicant(program=program.name)
		self.assertEqual((applicant.fee_discount_percent, applicant.fee_discount_source), (100, "Window"))
		self.assertEqual(admissions.application_fee_discount(applicant), (100, "Window"))
		self.assertIn("No application fee until", fee.window_note(program.name))

	def test_overlapping_windows_are_rejected(self):
		today = nowdate()
		with self.assertRaises(frappe.ValidationError):
			_program(
				[("A", today, add_days(today, 10), 50), ("B", add_days(today, 10), add_days(today, 20), 20)]
			)

	def test_a_code_ignores_case_and_the_largest_discount_wins(self):
		today = nowdate()
		program = _program([("Early", add_days(today, -1), add_days(today, 1), 20)])
		code = _code("Partner" + fx.uid("x").replace(" ", ""), pct=60)
		self.assertEqual(code.name, code.name.upper())
		applicant = make_applicant(program=program.name, fee_waiver_code=code.name.lower())
		self.assertEqual((applicant.fee_discount_percent, applicant.fee_discount_source), (60, "Code"))
		self.assertEqual(applicant.fee_waiver_code, code.name)
		self.assertEqual(frappe.get_doc("Application Fee Code", code.name).uses, 1)
		low = _code(pct=10)
		other = make_applicant(program=program.name, fee_waiver_code=low.name)
		self.assertEqual((other.fee_discount_percent, other.fee_discount_source), (20, "Window"))

	def test_a_code_outside_its_programs_dates_or_uses_fails(self):
		program, elsewhere = _program(), _program()
		only_here = _code(programs=[program.name])
		with self.assertRaises(frappe.ValidationError):
			make_applicant(program=elsewhere.name, fee_waiver_code=only_here.name)
		expired = _code(valid_to=add_days(nowdate(), -1))
		with self.assertRaises(frappe.ValidationError):
			make_applicant(program=program.name, fee_waiver_code=expired.name)
		once = _code(max_uses=1)
		make_applicant(program=program.name, fee_waiver_code=once.name)
		with self.assertRaises(frappe.ValidationError):
			make_applicant(program=program.name, fee_waiver_code=once.name)
		with self.assertRaises(frappe.ValidationError):
			make_applicant(program=program.name, fee_waiver_code="NO-SUCH-CODE")

	def test_the_code_is_fixed_once_applied(self):
		applicant = make_applicant(program=_program().name)
		applicant.fee_waiver_code = _code().name
		with self.assertRaises(frappe.ValidationError):
			applicant.save(ignore_permissions=True)

	def test_the_form_offers_fee_fields_only_when_a_fee_is_charged(self):
		program = _program(requests=1)
		self.assertEqual(fee.form_options(program.name)["allow_requests"], True)
		self.backend.application_fee_configured = lambda program: False
		self.assertEqual(fee.form_options(program.name)["has_fee"], False)


class TestRequests(FeeCase):
	def test_a_program_that_takes_no_requests_ignores_one(self):
		applicant = make_applicant(program=_program().name, fee_waiver_requested=1, fee_waiver_reason="x")
		self.assertFalse(applicant.fee_waiver_status)
		self.assertFalse(applicant.fee_waiver_requested)

	def test_a_request_needs_a_reason_and_holds_review_and_payment(self):
		program = _program(requests=1, director=fx.make_user(roles=("Instructor",)).name)
		with self.assertRaises(frappe.ValidationError):
			make_applicant(program=program.name, fee_waiver_requested=1)
		applicant = make_applicant(
			program=program.name, fee_waiver_requested=1, fee_waiver_reason="Pastor on a small salary"
		)
		self.assertEqual(applicant.fee_waiver_status, "Requested")
		self.assertEqual(
			frappe.db.get_value("Student Applicant", applicant.name, "application_status"), "Applied"
		)
		self.assertIn("Fee waiver decision", admissions.missing(applicant))
		from seminary.seminary.api import get_application_payment_url

		self.assertIsNone(get_application_payment_url(applicant.name, applicant.access_key))

	def test_approval_credits_the_fee_and_starts_review(self):
		program = _program(requests=1, director=fx.make_user(roles=("Instructor",)).name)
		applicant = make_applicant(program=program.name, fee_waiver_requested=1, fee_waiver_reason="Hardship")
		with self.assertRaises(frappe.ValidationError):
			fee.decide_waiver(applicant.name, 1, "")
		self.assertEqual(fee.decide_waiver(applicant.name, 1, "Missionary family", 100), "Approved")
		self.assertEqual(self.backend.waived, [(applicant.name, 100, "Missionary family")])
		row = frappe.db.get_value(
			"Student Applicant",
			applicant.name,
			[
				"fee_waiver_status",
				"fee_waiver_percent",
				"fee_discount_source",
				"fee_waiver_decided_by",
				"application_status",
			],
			as_dict=True,
		)
		self.assertEqual(
			(
				row.fee_waiver_status,
				row.fee_waiver_percent,
				row.fee_discount_source,
				row.fee_waiver_decided_by,
			),
			("Approved", 100, "Request", "Administrator"),
		)
		self.assertEqual(row.application_status, "In Review")
		with self.assertRaises(frappe.ValidationError):
			fee.decide_waiver(applicant.name, 0, "again")

	def test_a_decline_leaves_the_fee_to_pay(self):
		program = _program(requests=1)
		applicant = make_applicant(program=program.name, fee_waiver_requested=1, fee_waiver_reason="Hardship")
		self.assertEqual(fee.decide_waiver(applicant.name, 0, "Our fund is spent this year"), "Declined")
		self.assertEqual(self.backend.waived, [])
		doc = frappe.get_doc("Student Applicant", applicant.name)
		self.assertEqual(admissions.missing(doc), ["Application fee"])

	def test_a_paid_fee_cannot_be_waived(self):
		self.backend.paid = 50
		applicant = make_applicant(
			program=_program(requests=1).name, fee_waiver_requested=1, fee_waiver_reason="x"
		)
		with self.assertRaises(frappe.ValidationError):
			fee.decide_waiver(applicant.name, 1, "too late", 100)

	def test_the_admissions_chair_may_decide_and_others_may_not(self):
		program = _program(requests=1)
		chair = fx.make_user(roles=("Instructor",)).name
		person = frappe.db.get_value("Person", {"user": chair}) or fx.make_person(user=chair).name
		unit = frappe.get_doc(
			{
				"doctype": "Academic Unit",
				"unit_name": fx.uid("Admissions"),
				"unit_type": "Program Admissions",
				"chair": person,
				"is_active": 1,
			}
		).insert(ignore_permissions=True)
		program.admissions_unit = unit.name
		program.save(ignore_permissions=True)
		self.assertTrue(fee.may_decide_waiver(program.name, chair))
		self.assertFalse(fee.may_decide_waiver(program.name, fx.make_user(roles=("Instructor",)).name))
		applicant = make_applicant(program=program.name, fee_waiver_requested=1, fee_waiver_reason="x")
		frappe.set_user(fx.make_user(roles=("Instructor",)).name)
		with self.assertRaises(frappe.PermissionError):
			fee.decide_waiver(applicant.name, 1, "no", 100)
