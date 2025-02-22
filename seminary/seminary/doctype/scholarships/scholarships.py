# Copyright (c) 2025, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Scholarships(Document):
	@frappe.whitelist()
	def get_program_fees(program):
		program_fees = []
		program_fees = frappe.get_all(
			"Program Fees",
			filters={"parent": program},
			fields=["pgm_feecategory"],
		)
		print(program_fees)
		return program_fees
	
