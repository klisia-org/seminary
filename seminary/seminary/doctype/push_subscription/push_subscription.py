# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import hashlib

from frappe.model.document import Document


def endpoint_hash(endpoint):
	"""Endpoints run to several hundred characters, too long for a unique index."""
	return hashlib.sha256((endpoint or "").encode()).hexdigest()


class PushSubscription(Document):
	def validate(self):
		self.endpoint_hash = endpoint_hash(self.endpoint)
