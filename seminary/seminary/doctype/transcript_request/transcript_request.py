# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""A request for an official transcript (decisions/119 §5)."""

from frappe.model.document import Document

from seminary.seminary import transcripts


class TranscriptRequest(Document):
	def validate(self):
		transcripts.validate_request(self)

	def after_insert(self):
		transcripts.after_insert_request(self)
