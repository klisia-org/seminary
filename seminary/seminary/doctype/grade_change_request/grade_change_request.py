# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""A change to a sent grade, approved by the registrar (decisions/119 §3)."""

from frappe.model.document import Document

from seminary.seminary import grade_changes


class GradeChangeRequest(Document):
	def validate(self):
		grade_changes.fill(self)
		if self.is_new():
			grade_changes.assert_may_raise(self)
