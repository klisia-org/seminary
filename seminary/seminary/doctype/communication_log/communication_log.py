# Copyright (c) 2026, Murilo Melo and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CommunicationLog(Document):
    def validate(self):
        if not self.idempotency_key:
            # Unique column: blank rows would collide. No caller-supplied key
            # means "always send" — give it a random one.
            self.idempotency_key = frappe.generate_hash(length=24)
