# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from seminary.seminary import catalog
from seminary.seminary.utils import assert_url_safe_code


class Course(Document):
	def before_validate(self):
		self.set_course_code()

	def validate(self):
		assert_url_safe_code(self.course_id, _("Course ID"))
		assert_url_safe_code(self.coursecode, _("Course Code"))
		catalog.validate_prerequisite_rows(self)
		catalog.validate_replaced_rows(self)
		self.validate_assessment_criteria()
		self.clean_name()
		self.set_disabled_on()

	def on_update(self):
		before = self.get_doc_before_save()
		if before and before.coursecode != self.coursecode:
			catalog.refresh_code_copies(self.name, self.coursecode)

	def set_course_code(self):
		"""coursecode = <unit code>-<course_id> (decisions/114 §4). A new course
		given only a code (Data Import, older callers) has its Course ID taken
		from it. An existing course without a Course ID keeps its code, and the
		mandatory Course ID asks for one."""
		prefix = catalog.unit_prefix(self.academic_unit)
		if not self.course_id and self.is_new():
			self.course_id = catalog.split_code(self.coursecode, prefix) or (self.coursecode or "").strip()
		if self.course_id:
			self.course_id = self.course_id.strip()
			self.coursecode = catalog.course_code(self.course_id, prefix)

	def set_disabled_on(self):
		if self.disabled and not self.disabled_on:
			self.disabled_on = today()

	def clean_name(self):
		if self.course_name and ("/" in self.course_name or "\\" in self.course_name):
			# Just remove forward slashes and let Frappe handle the rest
			self.course_name = self.course_name.replace("/", "-").replace("\\", "-")

	def validate_assessment_criteria(self):
		if self.assessment_criteria:
			total_weightage = 0
			for criteria in self.assessment_criteria:
				total_weightage += criteria.weightage or 0
			if total_weightage != 100:
				frappe.throw(_("Total Weightage of all Assessment Criteria must be 100%"))

	def get_topics(self):
		topic_data = []
		for topic in self.topics:
			topic_doc = frappe.get_doc("Topic", topic.topic)
			if topic_doc.topic_content:
				topic_data.append(topic_doc)
		return topic_data


@frappe.whitelist()
def add_course_to_programs(course, programs, mandatory=False):
	programs = json.loads(programs)
	credits = frappe.db.get_value("Course", course, "course_credits")
	for entry in programs:
		program = frappe.get_doc("Program", entry)
		program.append(
			"courses",
			{
				"course": course,
				"course_name": course,
				"required": mandatory,
				"pgmcourse_credits": credits,
			},
		)
		program.flags.ignore_mandatory = True
		program.save()
	frappe.msgprint(
		_("Course {0} has been added to all the selected programs successfully.").format(frappe.bold(course)),
		title=_("Programs updated"),
		indicator="green",
	)


@frappe.whitelist()
def bulk_add_courses_to_program(courses, program, mandatory=False):
	if isinstance(courses, str):
		courses = json.loads(courses)

	if not frappe.has_permission("Program", "write", doc=program):
		frappe.throw(_("Not permitted to modify Program {0}").format(program))

	program_doc = frappe.get_doc("Program", program)
	existing = {c.course for c in program_doc.courses if not c.disabled}

	credits_by_course = {
		row.name: row.course_credits
		for row in frappe.get_all(
			"Course",
			filters={"name": ["in", courses]},
			fields=["name", "course_credits"],
		)
	}

	added, skipped = [], []
	for course in courses:
		if course in existing:
			skipped.append(course)
			continue
		program_doc.append(
			"courses",
			{
				"course": course,
				"course_name": course,
				"required": mandatory,
				"pgmcourse_credits": credits_by_course.get(course),
			},
		)
		added.append(course)

	if added:
		program_doc.flags.ignore_mandatory = True
		program_doc.save()

	return {"added": added, "skipped": skipped}


@frappe.whitelist()
def get_programs_without_course(course):
	data = []
	for entry in frappe.db.get_all("Program"):
		program = frappe.get_doc("Program", entry.name)
		courses = [c.course for c in program.courses if not c.disabled]
		if not courses or course not in courses:
			data.append(program.name)
	return data
