# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import set_name_by_naming_series
import time

class Instructor(Document):
	def autoname(self):
		naming_method = frappe.db.get_value(
			"Seminary Settings", None, "instructor_created_by"
		)
		if not naming_method:
			frappe.throw(
				_("Please setup Instructor Naming System in Seminary > Seminary Settings")
			)
		else:
			if naming_method == "Naming Series":
				set_name_by_naming_series(self)
			elif naming_method == "Employee Number":
				if not self.employee:
					frappe.throw(_("Please select Employee"))
				self.name = self.employee
			elif naming_method == "Full Name":
				self.name = self.instructor_name

	def validate(self):
		self.validate_duplicate_employee()

	def validate_duplicate_employee(self):
		if self.employee and frappe.db.get_value(
			"Instructor", {"employee": self.employee, "name": ["!=", self.name]}, "name"
		):
			frappe.throw(_("Employee ID is linked with another instructor"))


def get_timeline_data(doctype, name):
	"""Return timeline for course schedule"""
	timeline_data = dict(
		frappe.db.sql(
			"""
			SELECT unix_timestamp(`cs.c_datestart`), count(cs.name)
			FROM `tabCourse Schedule` cs, `tabCourse Schedule Instructor` csi
			WHERE
				cs.name = csi.parent and
				csi.instructor = %s and
				cs.c_datestart > date_sub(curdate(), interval 1 year)
			GROUP BY cs.c_datestart
			""",
			name,
		)
	)
	if not timeline_data:
		timeline_data = {int(time.time()): 0}  # Set current date as c_datestart if timeline_data is empty
	return timeline_data
