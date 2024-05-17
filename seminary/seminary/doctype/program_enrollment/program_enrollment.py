# Copyright (c) 2015, Frappe and contributors
# For license information, please see license.txt


import frappe
from frappe import _, msgprint
from frappe.desk.reportview import get_match_cond
from frappe.model.document import Document
from frappe.query_builder.functions import Min
from frappe.utils import comma_and, get_link_to_form, getdate



class ProgramEnrollment(Document):
	def validate(self):
		self.set_student_name()
		self.validate_duplication()
		self.validate_academic_term()

		
	def set_student_name(self):
		if not self.student_name:
			self.student_name = frappe.db.get_value("Student", self.student, "student_name")

	def on_submit(self):
		self.update_student_joining_date()
		self.create_course_enrollments()

	def validate_academic_term(self):
		today = getdate()
		start_date, end_date = frappe.db.get_value(
			"Academic Term", self.academic_term, ["term_start_date", "term_end_date"]
		)
		if self.enrollment_date:
			if getdate(self.enrollment_date) < today:
				frappe.throw(
					_(
						"Enrollment Date cannot be before today"
					).format(get_link_to_form("Academic Term", self.academic_term))
				)

			if end_date and getdate(self.enrollment_date) > getdate(end_date):
				frappe.throw(
					_("Enrollment Date cannot be after the End Date of the Academic Term {0}").format(
						get_link_to_form("Academic Term", self.academic_term)
					)
				)

	def validate_duplication(self):
		enrollment = frappe.db.exists(
			"Program Enrollment",
			{
				"student": self.student,
				"program": self.program,
				"academic_term": self.academic_term,
				"docstatus": ("<", 2),
				"name": ("!=", self.name),
			},
		)
		if enrollment:
			frappe.throw(_("Student is already enrolled."))

	def update_student_joining_date(self):
		table = frappe.qb.DocType("Program Enrollment")
		date = (
			frappe.qb.from_(table)
			.select(Min(table.enrollment_date).as_("enrollment_date"))
			.where(table.student == self.student)
		).run(as_dict=True)

		if date:
			frappe.db.set_value("Student", self.student, "joining_date", date[0].enrollment_date)

	





@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_program_courses(doctype, txt, searchfield, start, page_len, filters):
	if not filters.get("program"):
		frappe.msgprint(_("Please select a Program first."))
		return []

	doctype = "Program Course"
	return frappe.db.sql(
		"""select course, course_name from `tabProgram Course`
		where  parent = %(program)s and course like %(txt)s {match_cond}
		order by
			if(locate(%(_txt)s, course), locate(%(_txt)s, course), 99999),
			idx desc,
			`tabProgram Course`.course asc
		limit {start}, {page_len}""".format(
			match_cond=get_match_cond(doctype), start=start, page_len=page_len
		),
		{
			"txt": "%{0}%".format(txt),
			"_txt": txt.replace("%", ""),
			"program": filters["program"],
		},
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_students(doctype, txt, searchfield, start, page_len, filters):
	enrolled_students = []
	if not filters.get("academic_term"):
		filters["academic_term"] = frappe.defaults.get_defaults().academic_term
		enrolled_students = frappe.get_list(
		"Program Enrollment",
		filters={
			"academic_term": filters.get("academic_term"),
		},
		fields=["student"],
	)

	students = [d.student for d in enrolled_students] if enrolled_students else [""]

	return frappe.db.sql(
		"""select
			name, student_name from tabStudent
		where
			name not in (%s)
		and
			`%s` LIKE %s
		order by
			idx desc, name
		limit %s, %s"""
		% (", ".join(["%s"] * len(students)), searchfield, "%s", "%s", "%s"),
		tuple(students + ["%%%s%%" % txt, start, page_len]),
	)




	
	