# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/115: catalog years.

The checklist's test is the first one: a requirement change must not alter students on an
earlier catalog, and two catalog years can be shown side by side.
"""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from seminary.seminary import catalog_year as cy
from seminary.seminary.api import _program_audit
from seminary.seminary.exceptions import mandatory_courses
from seminary.seminary.graduation import resnapshot
from seminary.seminary.graduation_candidate import _mandatory_program_courses
from seminary.seminary.tests import cohort_fixtures as fx


def _course():
	name = fx.uid("C115")
	frappe.get_doc(
		{"doctype": "Course", "name": name, "course_name": name, "coursecode": name[-10:]}
	).db_insert()
	return name


def _term(year, label, start, end):
	return (
		frappe.get_doc(
			{
				"doctype": "Academic Term",
				"academic_year": year,
				"term_name": f"{fx.PREFIX} {label} {fx.uid()}",
				"term_start_date": start,
				"term_end_date": end,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _year(start, end):
	name = fx.uid("AY115")
	frappe.get_doc(
		{
			"doctype": "Academic Year",
			"academic_year_name": name,
			"year_start_date": start,
			"year_end_date": end,
		}
	).insert(ignore_permissions=True)
	return name


def _submit(name):
	doc = frappe.get_doc(cy.CATALOG, name)
	apply_workflow(doc, "Submit")
	return frappe.get_doc(cy.CATALOG, name)


def _enroll(student, program, term):
	doc = frappe.get_doc(
		{
			"doctype": "Program Enrollment",
			"student": student.name,
			"program": program,
			"academic_term": term,
			"enrollment_date": today(),
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return frappe.get_doc("Program Enrollment", doc.name)


class CatalogCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Users commit, so the students are made once and kept out of the savepoint.
		cls.early = fx.make_student()
		cls.late = fx.make_student()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.savepoint("adr115_test")
		now = getdate(today())
		past = _year(add_days(now, -800), add_days(now, -400))
		current = _year(add_days(now, -399), add_days(now, 199))
		coming = _year(add_days(now, 200), add_days(now, 600))
		self.t1 = _term(past, "Past", add_days(now, -800), add_days(now, -400))
		self.t2 = _term(current, "Current", add_days(now, -399), add_days(now, 199))
		self.t3 = _term(coming, "Coming", add_days(now, 200), add_days(now, 600))
		self.core, self.elective, self.dropped = _course(), _course(), _course()
		program = fx.make_program("Credits-based")
		program.credits_complete = 9
		program.append("courses", {"course": self.core, "required": 1, "pgmcourse_credits": 3})
		program.append("courses", {"course": self.elective, "required": 0, "pgmcourse_credits": 3})
		program.append("courses", {"course": self.dropped, "required": 0, "pgmcourse_credits": 3})
		program.append("honors_levels", {"honor_name": "Cum Laude", "min_gpa": 3.5})
		program.save(ignore_permissions=True)
		self.program = program.name
		self.first = cy.publish_first_catalog(self.program, self.t1)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="adr115_test")
		super().tearDown()

	def _next_catalog(self, term=None, edit=None):
		"""Draft the next catalog from term t3, change it, and submit it."""
		name = cy.new_catalog_year(self.program, term or self.t3)
		doc = frappe.get_doc(cy.CATALOG, name)
		if edit:
			edit(doc)
			doc.save(ignore_permissions=True)
		return _submit(name)

	def _stricter(self, doc):
		for row in doc.catalog_courses:
			if row.course == self.elective:
				row.required = 1
			if row.course == self.core:
				row.credits = 4
		doc.catalog_courses = [r for r in doc.catalog_courses if r.course != self.dropped]
		doc.credits_complete = 12
		doc.honors_levels = []
		doc.append("honors_levels", {"honor_name": "Cum Laude", "min_gpa": 3.7})

	def _take_effect(self, catalog):
		"""Bring the coming term forward so the scheduled catalog takes effect today."""
		frappe.db.set_value("Academic Term", self.t3, "term_start_date", today())
		frappe.db.set_value(cy.CATALOG, catalog, "starts_on", today())
		cy.activate_due(self.program)


class TestCatalogContract(CatalogCase):
	def test_a_change_does_not_reach_a_student_on_an_earlier_catalog(self):
		early = _enroll(self.early, self.program, self.t2)
		self.assertEqual(early.graduation_policy, self.first)

		second = self._next_catalog(edit=self._stricter)
		self.assertEqual(second.workflow_state, "Scheduled")
		self._take_effect(second.name)

		late = _enroll(self.late, self.program, self.t3)
		self.assertEqual(late.graduation_policy, second.name)

		self.assertEqual(mandatory_courses(early), {self.core})
		self.assertEqual(mandatory_courses(late), {self.core, self.elective})
		self.assertEqual(_program_audit(early.name)["credits_required"], 9)
		self.assertEqual(_program_audit(late.name)["credits_required"], 12)
		self.assertEqual(cy.course_credits(early.name, self.core), 3)
		self.assertEqual(cy.course_credits(late.name, self.core), 4)
		self.assertEqual(cy.for_enrollment(early).honors_levels[0].min_gpa, 3.5)
		self.assertEqual(cy.for_enrollment(late).honors_levels[0].min_gpa, 3.7)

	def test_the_draft_leaves_the_program_alone_until_it_takes_effect(self):
		second = self._next_catalog(edit=self._stricter)
		program = frappe.get_doc("Program", self.program)
		self.assertEqual(program.credits_complete, 9)
		self.assertFalse(next(r for r in program.courses if r.course == self.elective).required)

		self._take_effect(second.name)
		self.assertEqual(frappe.db.get_value(cy.CATALOG, second.name, "workflow_state"), "Active")
		self.assertEqual(frappe.db.get_value(cy.CATALOG, self.first, "workflow_state"), "Superseded")
		self.assertEqual(frappe.db.get_value(cy.CATALOG, self.first, "superseded_by"), second.name)
		program = frappe.get_doc("Program", self.program)
		self.assertEqual(program.credits_complete, 12)
		rows = {r.course: r for r in program.courses}
		self.assertTrue(rows[self.elective].required)
		self.assertEqual(rows[self.core].pgmcourse_credits, 4)
		self.assertTrue(rows[self.dropped].disabled)
		self.assertIn(second.catalog_year, rows[self.dropped].disable_reason)

	def test_the_previous_catalog_ends_the_term_before(self):
		second = self._next_catalog()
		self.assertEqual(
			frappe.db.get_value(cy.CATALOG, self.first, "academic_term_to"), cy.term_before(second.starts_on)
		)
		self.assertEqual(second.supersedes, self.first)

	def test_catalogs_follow_each_other(self):
		self._next_catalog()
		name = cy.new_catalog_year(self.program, self.t2)
		with self.assertRaises(frappe.ValidationError):
			_submit(name)

	def test_a_draft_copies_the_requirements_and_stays_the_one_draft(self):
		catalog = frappe.get_doc(cy.CATALOG, self.first)
		catalog.db_set("max_transfer_credits", 6, update_modified=False)
		name = cy.new_catalog_year(self.program, self.t3)
		self.assertEqual(cy.new_catalog_year(self.program), name)
		draft = frappe.get_doc(cy.CATALOG, name)
		self.assertEqual(draft.supersedes, self.first)
		self.assertEqual({r.course for r in draft.catalog_courses}, {self.core, self.elective, self.dropped})

	def test_only_the_programs_courses_can_be_listed(self):
		name = cy.new_catalog_year(self.program, self.t3)
		doc = frappe.get_doc(cy.CATALOG, name)
		doc.append("catalog_courses", {"course": _course()})
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)


class TestCompareAndStatus(CatalogCase):
	def test_compare_shows_two_catalog_years_side_by_side(self):
		second = self._next_catalog(edit=self._stricter)
		result = cy.compare(second.name)
		self.assertEqual(result["other"]["name"], self.first)
		text = "\n".join(result["changes"])
		self.assertIn("Credits for completion: 9", text)
		self.assertIn("mandatory No", text)
		self.assertIn("Course removed", text)
		self.assertIn("Cum Laude", text)

	def test_the_program_form_reports_pending_and_differences(self):
		status = cy.program_status(self.program)
		self.assertFalse(status["pending"])
		self.assertEqual(status["differences"], [])

		program = frappe.get_doc("Program", self.program)
		program.credits_complete = 10
		program.save(ignore_permissions=True)
		self.assertTrue(cy.program_status(self.program)["differences"])

		cy.new_catalog_year(self.program, self.t3)
		status = cy.program_status(self.program)
		self.assertEqual(status["pending"][0].workflow_state, "Draft")
		self.assertEqual(status["differences"], [])


class TestGuards(CatalogCase):
	def test_no_catalog_no_enrollment_and_no_publishing(self):
		program = fx.make_program("Credits-based")
		with self.assertRaises(frappe.ValidationError):
			_enroll(self.early, program.name, self.t2)
		program.published = 1
		with self.assertRaises(frappe.ValidationError):
			program.save(ignore_permissions=True)

	def test_resnapshot_moves_a_student_and_logs_it(self):
		early = _enroll(self.early, self.program, self.t2)
		second = self._next_catalog(edit=self._stricter)
		resnapshot(early.name, catalog=second.name)
		self.assertEqual(
			frappe.db.get_value("Program Enrollment", early.name, "graduation_policy"), second.name
		)
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{"reference_name": early.name, "content": ("like", f"%{second.catalog_year}%")},
			)
		)

	def test_a_disabled_required_course_is_not_required(self):
		program = frappe.get_doc("Program", self.program)
		row = next(r for r in program.courses if r.course == self.core)
		row.disabled = 1
		self.assertEqual(_mandatory_program_courses(program), set())
