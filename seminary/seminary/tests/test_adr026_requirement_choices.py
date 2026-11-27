# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/026: a student picks a 'Choose Option' sub-requirement or a
Culminating Project Type from the portal, once, while the choice is pending."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import graduation
from seminary.seminary.api import _requirement_choice_options
from seminary.seminary.tests import cohort_fixtures as fx


def _gri(requirement_type, **kw):
	doc = frappe.get_doc(
		{
			"doctype": "Graduation Requirement Item",
			"requirement_name": fx.uid("Choice"),
			"requirement_type": requirement_type,
			"mandatory": 1,
			**kw,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def _cp_type():
	return frappe.get_doc({"doctype": "Culminating Project Type", "type_name": fx.uid("CPT")}).insert(
		ignore_permissions=True
	)


def _row_for(pe, gri):
	"""Append a snapshot-shaped SGR row for `gri` (as _build_sgr_row does)."""
	row = {
		"requirement_name": gri.requirement_name,
		"requirement_type": gri.requirement_type,
		"mandatory": 1,
		"status": "Not Started",
		"student_choice": gri.student_choice,
		"link_doctype": gri.link_doctype if gri.requirement_type == "Linked Document" else None,
		"grad_requirement_item": gri.name,
	}
	graduation._apply_initial_choice_state(row, gri)
	pe.append("graduation_requirements", row)
	pe.save(ignore_permissions=True)
	return pe.graduation_requirements[-1].name


def _sgr(name):
	return frappe.get_doc("Student Graduation Requirement", name)


class TestRequirementChoices(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.program = fx.make_program()
		self.student = fx.make_student()
		self.student_user = frappe.db.get_value("Student", self.student.name, "student_email_id")
		self.pe = fx.make_enrollment(self.student, self.program)
		self.t1, self.t2 = _cp_type(), _cp_type()

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def _umbrella(self, student_choice=1):
		manual = _gri("Manual Verification")
		thesis = _gri(
			"Linked Document",
			link_doctype="Culminating Project",
			culm_proj_types=[
				{"culminating_project_type": self.t1.name},
				{"culminating_project_type": self.t2.name},
			],
		)
		umbrella = _gri(
			"Choose Option",
			student_choice=student_choice,
			grad_req_option=[{"grad_req_item": manual.name}, {"grad_req_item": thesis.name}],
		)
		return umbrella, manual, thesis

	def _choose_option(self, sgr, option):
		return graduation.choose_requirement_option(self.pe.name, sgr, option)

	def test_student_picks_an_option_and_a_row_is_spawned(self):
		umbrella, manual, thesis = self._umbrella()
		sgr = _row_for(self.pe, umbrella)
		options = _requirement_choice_options(_sgr(sgr))
		self.assertEqual({o["value"] for o in options}, {manual.name, thesis.name})

		frappe.set_user(self.student_user)
		self._choose_option(sgr, thesis.name)
		frappe.set_user("Administrator")

		self.pe.reload()
		spawned = [r for r in self.pe.graduation_requirements if r.parent_choice == sgr]
		self.assertEqual(len(spawned), 1)
		self.assertEqual(spawned[0].grad_requirement_item, thesis.name)
		self.assertFalse(_sgr(sgr).choice_pending)
		# The spawned thesis row has two types, so its own type choice is pending.
		self.assertTrue(spawned[0].choice_pending)
		self.assertEqual(
			{o["value"] for o in _requirement_choice_options(spawned[0])}, {self.t1.name, self.t2.name}
		)

		frappe.set_user(self.student_user)
		graduation.choose_project_type(self.pe.name, spawned[0].name, self.t2.name)
		frappe.set_user("Administrator")
		row = _sgr(spawned[0].name)
		self.assertEqual((row.chosen_project_type, row.choice_pending), (self.t2.name, 0))

	def test_student_cannot_change_a_made_choice(self):
		umbrella, manual, thesis = self._umbrella()
		sgr = _row_for(self.pe, umbrella)
		frappe.set_user(self.student_user)
		self._choose_option(sgr, manual.name)
		with self.assertRaises(frappe.PermissionError):
			self._choose_option(sgr, thesis.name)
		frappe.set_user("Administrator")
		self.assertEqual(_sgr(sgr).chosen_option, manual.name)

	def test_staff_can_change_a_made_choice(self):
		umbrella, manual, thesis = self._umbrella()
		sgr = _row_for(self.pe, umbrella)
		self._choose_option(sgr, manual.name)
		self._choose_option(sgr, thesis.name)
		self.pe.reload()
		spawned = [r for r in self.pe.graduation_requirements if r.parent_choice == sgr]
		self.assertEqual([r.grad_requirement_item for r in spawned], [thesis.name])

	def test_student_cannot_choose_a_registrar_assigned_requirement(self):
		umbrella, manual, _ = self._umbrella(student_choice=0)
		sgr = _row_for(self.pe, umbrella)
		frappe.set_user(self.student_user)
		with self.assertRaises(frappe.PermissionError):
			self._choose_option(sgr, manual.name)

	def test_option_outside_the_list_is_refused(self):
		umbrella, _, _ = self._umbrella()
		sgr = _row_for(self.pe, umbrella)
		stray = _gri("Manual Verification")
		frappe.set_user(self.student_user)
		with self.assertRaises(frappe.ValidationError):
			self._choose_option(sgr, stray.name)

	def test_project_type_outside_the_list_is_refused(self):
		cp = _gri(
			"Linked Document",
			link_doctype="Culminating Project",
			student_choice=1,
			culm_proj_types=[
				{"culminating_project_type": self.t1.name},
				{"culminating_project_type": self.t2.name},
			],
		)
		sgr = _row_for(self.pe, cp)
		self.assertTrue(_sgr(sgr).choice_pending)
		frappe.set_user(self.student_user)
		with self.assertRaises(frappe.ValidationError):
			graduation.choose_project_type(self.pe.name, sgr, _cp_type().name)
		graduation.choose_project_type(self.pe.name, sgr, self.t1.name)
		with self.assertRaises(frappe.PermissionError):
			graduation.choose_project_type(self.pe.name, sgr, self.t2.name)
