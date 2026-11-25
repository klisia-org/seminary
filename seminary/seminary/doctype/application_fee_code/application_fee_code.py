# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""A code an applicant enters for a discount on the application fee (decisions/113 §3)."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from seminary.seminary.application_fee import code_uses, normalize_code


class ApplicationFeeCode(Document):
	@property
	def uses(self):
		# Counted from the applications, never typed in.
		return code_uses(self.name) if self.name and not self.is_new() else 0

	def before_insert(self):
		self.code = normalize_code(self.code)

	def validate(self):
		if not self.code:
			frappe.throw(_("Enter a code."))
		if not 0 < flt(self.discount_percent) <= 100:
			frappe.throw(_("The discount must be more than 0 and at most 100."))
		if self.valid_from and self.valid_to and getdate(self.valid_to) < getdate(self.valid_from):
			frappe.throw(_("Valid To cannot be before Valid From."))
		if (self.max_uses or 0) < 0:
			frappe.throw(_("Maximum Uses cannot be negative."))
