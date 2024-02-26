# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from education.education.utils import validate_duplicate_student


class StudentGroup(Document):
	def validate(self):
		self.validate_strength()
		self.validate_students()
		self.validate_and_set_child_table_fields()
		validate_duplicate_student(self.students)

	

	def validate_strength(self):
		if cint(self.max_strength) < 0:
			frappe.throw(_("""Max number of students cannot be less than zero."""))
		if self.max_strength and len(self.students) > self.max_strength:
			frappe.throw(
				_("""Cannot enroll more than {0} students for this student group.""").format(
					self.max_strength
				)
			)

	def validate_students(self):
		program_enrollment = get_program_enrollment(
			self.academic_year,
			self.academic_term,
			self.program,
		)
		students = [d.student for d in program_enrollment] if program_enrollment else []
		for d in self.students:
			if (
				not frappe.db.get_value("Student", d.student, "enabled")
				and d.active
				and not self.disabled
			):
				frappe.throw(
					_("{0} - {1} is inactive student").format(d.group_roll_number, d.student_name)
				)

	def validate_and_set_child_table_fields(self):
		roll_numbers = [d.group_roll_number for d in self.students if d.group_roll_number]
		max_roll_no = max(roll_numbers) if roll_numbers else 0
		roll_no_list = []
		for d in self.students:
			if not d.student_name:
				d.student_name = frappe.db.get_value("Student", d.student, "title")
			if not d.group_roll_number:
				max_roll_no += 1
				d.group_roll_number = max_roll_no
			if d.group_roll_number in roll_no_list:
				frappe.throw(_("Duplicate roll number for student {0}").format(d.student_name))
			else:
				roll_no_list.append(d.group_roll_number)


@frappe.whitelist()
def get_students(
	academic_year,
	academic_term=None,
	program=None,
):
	enrolled_students = get_program_enrollment(
		academic_year, academic_term, program
	)

	if enrolled_students:
		student_list = []
		for s in enrolled_students:
			if frappe.db.get_value("Student", s.student, "enabled"):
				s.update({"active": 1})
			else:
				s.update({"active": 0})
			student_list.append(s)
		return student_list
	else:
		frappe.msgprint(_("No students found"))
		return []


def get_program_enrollment(
	academic_year,
	academic_term=None,
	program=None,
):

	condition1 = " "
	condition2 = " "
	if academic_term:
		condition1 += " and pe.academic_term = %(academic_term)s"
	if program:
		condition1 += " and pe.program = %(program)s"
	
	return frappe.db.sql(
		"""
		select
			pe.student, pe.student_name
		from
			`tabProgram Enrollment` pe {condition2}
		where
			pe.academic_year = %(academic_year)s  
			and pe.docstatus = 0 {condition1}
		order by
			pe.student_name asc
		""".format(
			condition1=condition1, condition2=condition2
		),
		(
			{
				"academic_year": academic_year,
				"academic_term": academic_term,
				"program": program,
				
			}
		),
		as_dict=1,
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def fetch_students(doctype, txt, searchfield, start, page_len, filters):
	enrolled_students = get_program_enrollment(
			filters.get("academic_year"),
			filters.get("academic_term"),
			filters.get("program"),
			)
	student_group_student = frappe.db.sql_list(
			"""select student from `tabStudent Group Student` where parent=%s""",
			(filters.get("student_group")),
		)
	students = (
			[d.student for d in enrolled_students if d.student not in student_group_student]
			if enrolled_students
			else [""]
		) or [""]
	return frappe.db.sql(
			"""select name, student_name from tabStudent
			where name in ({0}) and (`{1}` LIKE %s or student_name LIKE %s)
			order by idx desc, name
			limit %s, %s""".format(
				", ".join(["%s"] * len(students)), searchfield
			),
			tuple(students + ["%%%s%%" % txt, "%%%s%%" % txt, start, page_len]),
		)