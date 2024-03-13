# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from frappe.utils.csvutils import getlink


class CourseEnrollmentIndividual(Document):
	def validate(self):
		self.validate_duplicate()

	def validate_duplicate(self):
		CEI= frappe.get_list(
			"Course Enrollment Individual",
			filters={
				"program_ce": (self.program_ce),
				"coursesc_ce": self.coursesc_ce,
				"docstatus": ("!=", 2),
			},
		)
		if CEI:
			frappe.throw(
				_("This Course Enrollment {0} already exists.").format(
					getlink("Course Enrollment Individual", CEI[0].name)
				)
			)
