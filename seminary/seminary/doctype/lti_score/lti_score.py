# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""A score an LTI tool posted (decisions/110 §7). Written only by the scores
endpoint in `seminary.lti.services`; whether it reaches the gradebook is
`seminary.lti.grades`."""

from frappe.model.document import Document


class LTIScore(Document):
	pass
