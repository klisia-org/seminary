# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""More time on an Incomplete than the instructor may grant (decisions/119 §1)."""

import frappe
from frappe.model.document import Document

from seminary.seminary import incompletes


class IncompleteExtensionRequest(Document):
	def validate(self):
		incompletes.fill_extension_request(self)

	def after_insert(self):
		incompletes._notify(
			incompletes._roster(self.roster),
			"incomplete-extension-requested",
			{
				"requested": frappe.format(self.requested_until, "Date"),
				"reason": self.reason,
				"request": self.name,
			},
		)
