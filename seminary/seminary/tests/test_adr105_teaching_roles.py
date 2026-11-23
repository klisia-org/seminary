# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/105 -- what an instructor's category lets them do on a section,
and observers who read a course without seeing its students.

One section, four people: an instructor with every action, a grader (grades
only), an instructor whose row has no category, and an observer with no
Instructor record at all.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from seminary.seminary import guards, student_permissions, utils
from seminary.seminary.tests import cohort_fixtures as cf


def _reset():
	frappe.local.p007_cache = {}


def _category(**actions):
	values = dict.fromkeys(guards.ACTION_FIELDS.values(), 0)
	values.update(actions)
	doc = frappe.get_doc({"doctype": "Instructor Category", "category_name": cf.uid("Cat"), **values})
	doc.insert(ignore_permissions=True)
	return doc.name


def _section(published=1):
	cs = frappe.get_doc(
		{
			"doctype": "Course Schedule",
			"name": cf.uid("CS"),
			"workflow_state": "Open",
			"published": published,
			"open_ended": 1,
		}
	)
	cs.db_insert()
	return cs.name


def _child(cs, doctype, parentfield, **values):
	row = frappe.get_doc(
		{
			"doctype": doctype,
			"name": frappe.generate_hash(length=10),
			"parent": cs,
			"parenttype": "Course Schedule",
			"parentfield": parentfield,
			**values,
		}
	)
	row.db_insert()
	return row


def _instructor(cs, category=None, default=None):
	instructor = cf.make_instructor()
	if default:
		instructor.db_set("default_inst_category", default, update_modified=False)
	user = frappe.db.get_value("Instructor", instructor.name, "user")
	frappe.get_doc("User", user).add_roles("Instructor")
	_child(
		cs,
		"Course Schedule Instructors",
		"instructor1",
		instructor=instructor.name,
		instructor_category=category,
	)
	return user


class TestTeachingRoles(IntegrationTestCase):
	def setUp(self):
		try:
			self.full = _category(
				may_edit_content=1, may_grade=1, may_record_attendance=1, may_post_to_class=1
			)
			self.grader = _category(may_grade=1)
			self.cs = _section()
			self.lead = _instructor(self.cs, self.full)
			self.grader_user = _instructor(self.cs, self.grader)
		except Exception:
			frappe.db.rollback()
			raise
		_reset()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		super().tearDown()

	def as_user(self, user):
		frappe.set_user(user)
		_reset()

	def test_the_category_sets_what_a_section_instructor_may_do(self):
		self.as_user(self.lead)
		self.assertEqual(guards.section_actions(self.cs), set(guards.ACTION_FIELDS))
		self.as_user(self.grader_user)
		self.assertEqual(guards.section_actions(self.cs), {guards.GRADE})
		self.assertTrue(guards.may_act(self.cs, guards.GRADE))
		for action in (guards.CONTENT, guards.ATTENDANCE, guards.POST):
			self.assertFalse(guards.may_act(self.cs, action))
		# Still on the section's staff: reads do not change.
		self.assertTrue(guards.is_course_staff(self.cs))

	def test_row_category_falls_back_to_default_then_to_everything(self):
		with_default = _instructor(self.cs, default=self.grader)
		bare = _instructor(self.cs)
		self.as_user(with_default)
		self.assertEqual(guards.section_actions(self.cs), {guards.GRADE})
		self.as_user(bare)
		self.assertEqual(guards.section_actions(self.cs), set(guards.ACTION_FIELDS))

	def test_a_grader_is_refused_course_writes(self):
		self.as_user(self.grader_user)
		with self.assertRaises(frappe.PermissionError):
			utils.create_student_group(self.cs, "G", None, "[]")
		with self.assertRaises(frappe.PermissionError):
			guards.require_section_capability(self.cs, guards.ATTENDANCE, include_registrar=True)
		guards.require_section_capability(self.cs, guards.GRADE)

	def test_the_row_hook_asks_for_the_action(self):
		lesson = frappe._dict(doctype="Course Lesson", course_sc=self.cs, name="x")
		section = frappe.get_doc("Course Schedule", self.cs)
		hook_lesson = student_permissions.has_for("Course Lesson")
		hook_cs = student_permissions.has_for("Course Schedule")
		self.as_user(self.grader_user)
		self.assertTrue(hook_lesson(lesson, "read", self.grader_user))
		self.assertFalse(hook_lesson(lesson, "write", self.grader_user))
		# An announcement is Frappe's "email" on the section.
		self.assertFalse(hook_cs(section, "email", self.grader_user))
		self.as_user(self.lead)
		self.assertTrue(hook_lesson(lesson, "write", self.lead))
		self.assertTrue(hook_cs(section, "email", self.lead))

	def test_school_roles_are_not_narrowed(self):
		self.as_user("Administrator")
		for action in guards.ACTION_FIELDS:
			self.assertTrue(guards.may_act(self.cs, action))


class TestObservers(IntegrationTestCase):
	def setUp(self):
		try:
			self.cs = _section()
			self.user = cf.make_user().name
			self.person = cf.make_person("Observer", user=self.user)
		except Exception:
			frappe.db.rollback()
			raise
		_reset()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		super().tearDown()

	def observe(self, cs=None, until=None):
		_child(cs or self.cs, "Course Schedule Observers", "observers", person=self.person.name, until=until)
		frappe.set_user(self.user)
		_reset()

	def test_an_observer_reads_the_course_and_nothing_more(self):
		self.observe()
		self.assertTrue(guards.may_view_content(self.cs))
		self.assertEqual(guards.section_access(self.cs), "observer")
		self.assertFalse(guards.is_course_staff(self.cs))
		self.assertFalse(guards.is_enrolled(self.cs))
		self.assertEqual(utils.get_roster(self.cs), [])
		self.assertIn(self.cs, [c.name for c in utils.get_courses(page_length=500)])
		utils.get_course_outline(self.cs)
		with self.assertRaises(frappe.PermissionError):
			guards.require_enrolled(self.cs)

	def test_access_ends_by_itself(self):
		self.observe(until=add_days(today(), -1))
		self.assertFalse(guards.may_view_content(self.cs))
		frappe.set_user("Administrator")
		draft = _section(published=0)
		self.observe(cs=draft)
		self.assertNotIn(draft, guards.observed_sections())
		frappe.set_user("Administrator")
		frappe.db.set_value("Course Schedule", self.cs, "workflow_state", "Cancelled")
		self.observe(until=add_days(today(), 1))
		self.assertNotIn(self.cs, guards.observed_sections())

	def test_no_person_no_access(self):
		other = cf.make_user().name
		self.observe()
		frappe.set_user(other)
		_reset()
		self.assertFalse(guards.may_view_content(self.cs))


class TestCategoryPatch(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()
		super().tearDown()

	def test_starter_categories_get_their_defaults_and_others_get_everything(self):
		from seminary.seminary.patches import adr105_category_actions

		custom = _category()
		if not frappe.db.exists("Instructor Category", "Grader"):
			frappe.get_doc({"doctype": "Instructor Category", "category_name": "Grader"}).insert(
				ignore_permissions=True
			)
		adr105_category_actions.execute()
		fields = list(guards.ACTION_FIELDS.values())
		self.assertEqual(
			frappe.db.get_value("Instructor Category", custom, fields, as_dict=True),
			dict.fromkeys(fields, 1),
		)
		grader = frappe.db.get_value("Instructor Category", "Grader", fields, as_dict=True)
		self.assertEqual({f for f in fields if grader[f]}, {"may_grade"})
