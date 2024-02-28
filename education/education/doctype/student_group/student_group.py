# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe import _, msgprint
from frappe.model.document import Document
from frappe.utils import cint

class StudentGroup(Document):
	def validate(self):
		self.validate_strength()
	
	def validate_strength(self):
		if cint(self.max_strength) < 0:
			frappe.throw(_("""Max number of students cannot be less than zero."""))
		if self.max_strength and len(self.students) > self.max_strength:
			frappe.throw(
				_("""Cannot enroll more than {0} students for this student group. Please remove excess students and create a new student group to include them.""").format(
					self.max_strength
				)
			)

@frappe.whitelist()
def get_students(self, academic_year, academic_term=None, program=None):
	return frappe.db.sql(
		"""
		select
			pe.student
		from
			`tabProgram Enrollment` pe, `tabStudent` t 
		where
			pe.academic_year = %(academic_year)s  AND
			pe.academic_term = %(academic_term)s AND
			pe.program = %(program)s AND
			pe.docstatus = 1 AND
			pe.student = t.name AND
			t.enabled = 1 AND
			t.docstatus = 1 AND
			pe.name NOT IN (select student from `tabStudent Group Student`)
		order by
			pe.student asc
		""",
		(self.student_group),
		{
			"academic_year": academic_year,
			"academic_term": academic_term,
			"program": program,
		},
		as_dict=1,
	)