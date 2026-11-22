# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""One oral recording and the products of its steps (decisions/100 §2).

Every field is written by ``seminary.seminary.oral``: recording, processing and
retention go through it, so the Desk form is read-only.
"""

from frappe.model.document import Document


class OralRecording(Document):
	pass
