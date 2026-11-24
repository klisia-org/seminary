# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""A key this site signs LTI messages with (decisions/110 §2). See `seminary.lti.keys`."""

from frappe.model.document import Document


class LTIPlatformKey(Document):
	pass
