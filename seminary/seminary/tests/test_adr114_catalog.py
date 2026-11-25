# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/114: course codes from the unit, replaced courses, prerequisite groups."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from seminary.seminary import catalog, exceptions
from seminary.seminary.required_enrollment import _already_covered, unmet_prerequisites
from seminary.seminary.tests import cohort_fixtures as fx


def _scale():
	return frappe.db.get_value("Grading Scale", {}, "name")


def _code():
	return "Z" + frappe.generate_hash(length=5).upper()


def _unit(unit_type="Academic Department", members=()):
	return frappe.get_doc(
		{
			"doctype": "Academic Unit",
			"unit_name": fx.uid("Unit114"),
			"unit_code": _code(),
			"unit_type": unit_type,
			"member_units": [{"member_unit": m} for m in members],
		}
	).insert(ignore_permissions=True)


def _course(unit=None, course_id=None, prereqs=(), replaces=(), **values):
	name = fx.uid("C114")
	return frappe.get_doc(
		{
			"doctype": "Course",
			"course_name": name,
			"course_id": course_id or frappe.generate_hash(length=6),
			"academic_unit": unit,
			"default_grading_scale": _scale(),
			"course_prerequisite": [
				{"course": c, "prereq_mandatory": mandatory, "prereq_group": group}
				for c, mandatory, group in prereqs
			],
			"replaced_courses": [{"course": c} for c in replaces],
			**values,
		}
	).insert(ignore_permissions=True)


def _graded(pe, course, status="Pass"):
	frappe.get_doc(
		{
			"doctype": "Program Enrollment Course",
			"name": frappe.generate_hash(length=10),
			"parent": pe.name,
			"parenttype": "Program Enrollment",
			"parentfield": "courses",
			"course_name": course,
			"credits": 3,
			"status": status,
			"pec_finalgradecode": "A" if status == "Pass" else "F",
		}
	).db_insert()


class TestSplitCode(UnitTestCase):
	def test_split(self):
		self.assertEqual(catalog.split_code("ST-501", "ST"), "501")
		self.assertEqual(catalog.split_code("ST_501", "ST"), "501")
		self.assertEqual(catalog.split_code("st501", "ST"), "501")
		self.assertEqual(catalog.split_code("XY501", ""), "XY501")
		self.assertIsNone(catalog.split_code("ST501", "S"))
		self.assertIsNone(catalog.split_code("NT501", "ST"))
		self.assertIsNone(catalog.split_code("ST", "ST"))

	def test_code(self):
		self.assertEqual(catalog.course_code("501", "ST"), "ST-501")
		self.assertEqual(catalog.course_code("501", ""), "501")


class ADR114Case(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.savepoint("adr114_test")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="adr114_test")
		super().tearDown()


class TestCourseCode(ADR114Case):
	def test_code_follows_the_unit(self):
		unit = _unit()
		course = _course(unit.name, "501")
		self.assertEqual(course.coursecode, f"{unit.unit_code}-501")

	def test_new_course_given_only_a_code_gets_its_id(self):
		unit = _unit()
		course = frappe.get_doc(
			{
				"doctype": "Course",
				"course_name": fx.uid("C114"),
				"coursecode": f"{unit.unit_code}501",
				"academic_unit": unit.name,
				"default_grading_scale": _scale(),
			}
		).insert(ignore_permissions=True)
		self.assertEqual(course.course_id, "501")
		self.assertEqual(course.coursecode, f"{unit.unit_code}-501")

	def test_moving_to_an_interdepartment_changes_the_code(self):
		dept = _unit()
		joint = _unit("Academic Interdepartment", members=[dept.name])
		course = _course(dept.name, "501")
		with patch.object(catalog, "refresh_code_copies") as refresh:
			course.academic_unit = joint.name
			course.save(ignore_permissions=True)
		self.assertEqual(course.coursecode, f"{joint.unit_code}-501")
		refresh.assert_called_once_with(course.name, course.coursecode)

	def test_code_copies_are_refreshed(self):
		"""Unmocked: every CODE_COPIES column must exist."""
		course = _course(_unit().name, "501")
		catalog.refresh_code_copies(course.name, course.coursecode)

	def test_unit_code_change_rederives_its_courses(self):
		unit = _unit()
		course = _course(unit.name, "501")
		unit.unit_code = _code()
		with patch.object(catalog, "refresh_code_copies") as refresh:
			unit.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Course", course.name, "coursecode"), f"{unit.unit_code}-501")
		refresh.assert_called_once()

	def test_unit_code_that_would_clash_is_rejected(self):
		a, b = _unit(), _unit()
		_course(a.name, "501")
		_course(b.name, "501")
		b.unit_code = a.unit_code
		self.assertRaises(frappe.ValidationError, b.save, ignore_permissions=True)

	def test_instructor_cannot_edit_catalog_fields(self):
		meta = frappe.get_meta("Course")
		instructor = fx.make_user(roles=("Instructor",))
		self.assertNotIn(1, meta.get_permlevel_access("write", user=instructor.name))
		self.assertIn(1, meta.get_permlevel_access("read", user=instructor.name))
		registrar = fx.make_user(roles=("Registrar",))
		self.assertIn(1, meta.get_permlevel_access("write", user=registrar.name))


class TestPrerequisites(ADR114Case):
	def setUp(self):
		super().setUp()
		self.greek, self.hebrew, self.intro = _course(), _course(), _course()
		self.exegesis = _course(
			prereqs=[
				(self.greek.name, "Mandatory", 1),
				(self.hebrew.name, "Mandatory", 1),
				(self.intro.name, "Mandatory", 0),
			]
		)
		self.program = fx.make_program("Credits-based")
		for c in (self.intro, self.exegesis):
			self.program.append(
				"courses", {"course": c.name, "course_name": c.name, "required": 1, "pgmcourse_credits": 3}
			)
		self.program.save(ignore_permissions=True)
		self.pe = fx.make_enrollment(fx.make_student(), self.program)

	def test_group_needs_one_course_and_labels_the_options(self):
		missing = unmet_prerequisites(self.pe.name, self.exegesis.name)
		self.assertEqual(len(missing), 2)
		self.assertIn(self.intro.name, missing)
		self.assertTrue(any(self.greek.name in m and self.hebrew.name in m for m in missing))
		_graded(self.pe, self.hebrew.name)
		_graded(self.pe, self.intro.name)
		self.assertEqual(unmet_prerequisites(self.pe.name, self.exegesis.name), [])

	def test_failed_course_does_not_count(self):
		_graded(self.pe, self.greek.name, status="Fail")
		_graded(self.pe, self.intro.name)
		self.assertEqual(len(unmet_prerequisites(self.pe.name, self.exegesis.name)), 1)

	def test_waived_prerequisite_unblocks(self):
		_graded(self.pe, self.greek.name)
		with patch.object(exceptions, "_notify"):
			frappe.get_doc(
				{
					"doctype": "Requirement Exception",
					"program_enrollment": self.pe.name,
					"kind": "Course Waiver",
					"required_course": self.intro.name,
					"reason": "Placed out",
				}
			).insert(ignore_permissions=True)
		self.assertEqual(unmet_prerequisites(self.pe.name, self.exegesis.name), [])

	def test_single_course_group_is_rejected(self):
		self.assertRaises(frappe.ValidationError, _course, prereqs=[(self.greek.name, "Mandatory", 2)])

	def test_recommended_row_takes_no_group(self):
		self.assertRaises(
			frappe.ValidationError,
			_course,
			prereqs=[(self.greek.name, "Recommended", 1), (self.hebrew.name, "Recommended", 1)],
		)


class TestReplacedCourses(ADR114Case):
	def setUp(self):
		super().setUp()
		self.old = _course()
		self.new = _course(replaces=[self.old.name])
		self.next = _course(prereqs=[(self.new.name, "Mandatory", 0)])
		self.program = fx.make_program("Credits-based")
		self.pe = fx.make_enrollment(fx.make_student(), self.program)
		_graded(self.pe, self.old.name)

	def test_passing_the_old_course_counts_for_the_new_one(self):
		self.assertEqual(unmet_prerequisites(self.pe.name, self.next.name), [])
		self.assertIn(self.new.name, exceptions.satisfied_courses(self.pe.name))
		self.assertTrue(_already_covered(self.pe.name, self.new.name))

	def test_only_one_way(self):
		pe = fx.make_enrollment(fx.make_student(), self.program)
		_graded(pe, self.new.name)
		self.assertNotIn(self.old.name, exceptions.satisfied_courses(pe.name))

	def test_cycle_is_rejected(self):
		self.old.append("replaced_courses", {"course": self.new.name})
		self.assertRaises(frappe.ValidationError, self.old.save, ignore_permissions=True)

	def test_course_cannot_replace_itself(self):
		self.new.append("replaced_courses", {"course": self.new.name})
		self.assertRaises(frappe.ValidationError, self.new.save, ignore_permissions=True)


class TestProgramPage(ADR114Case):
	def test_course_list(self):
		dept = _unit()
		joint = _unit("Academic Interdepartment", members=[dept.name])
		a, b = _course(), _course()
		shared = _course(
			joint.name,
			"610",
			prereqs=[(a.name, "Mandatory", 1), (b.name, "Mandatory", 1)],
			description="<p>Reading the <b>text</b>.</p>",
		)
		retired = _course(disabled=1, disable_reason="Gone")
		program = fx.make_program("Credits-based")
		for c in (shared, retired):
			program.append("courses", {"course": c.name, "course_name": c.name, "pgmcourse_credits": 3})
		program.save(ignore_permissions=True)

		rows = catalog.program_courses(program)
		self.assertEqual([r.name for r in rows], [shared.name])
		row = rows[0]
		self.assertEqual(row.code, f"{joint.unit_code}-610")
		self.assertEqual(row.description, "Reading the text.")
		self.assertEqual(len(row.prerequisites), 1)
		self.assertIn(a.name, row.prerequisites[0])
		self.assertIn(b.name, row.prerequisites[0])
		self.assertEqual(row.joint, dept.unit_name)
