# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from seminary.seminary import application_form


class ApplicationQuestion(Document):
	"""One question in the shared pool (decisions/111 §1)."""

	def validate(self):
		if self.answer_type == "Select" and not application_form.choices(self):
			frappe.throw(_("Add at least one choice, one per line."))
		if self.answer_type != "Select":
			self.options = None
		if self.answer_type != application_form.TABLE_SECTION:
			self.table_section = None
		elif not self.table_section:
			frappe.throw(_("Choose which table this question shows."))

	def on_trash(self):
		if application_form.has_answers(self.name):
			frappe.throw(
				_("Applicants have answered this question, so it cannot be deleted. Untick Active instead."),
				title=_("Question in use"),
			)
