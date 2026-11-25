# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ApplicationReview(Document):
	"""One reviewer's reading of one application (decisions/112 §3). Made by
	`admissions.assign_review`; submitted or recused through its buttons."""

	def before_insert(self):
		if not self.flags.from_admissions:
			frappe.throw(_("Reviews are assigned when an application is complete."))

	def validate(self):
		if self.is_new() or self.flags.from_admissions:
			return
		before = self.get_doc_before_save()
		if before.status != "Open":
			frappe.throw(_("A submitted or recused review cannot change."))
		for field in ("student_applicant", "reviewer", "status", "rubric", "due_date", "conflict_note"):
			if self.get(field) != before.get(field):
				frappe.throw(_("{0} cannot be changed here.").format(_(self.meta.get_label(field))))

	def on_trash(self):
		if self.status != "Open" and not frappe.flags.in_test:
			frappe.throw(_("A submitted or recused review is kept."))
