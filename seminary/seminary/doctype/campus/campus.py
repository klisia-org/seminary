# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

from frappe.contacts.address_and_contact import load_address_and_contact
from frappe.model.document import Document

from seminary.seminary import locations


class Campus(Document):
    def onload(self):
        load_address_and_contact(self)

    def on_update(self):
        locations.ensure_campus_location(self)

    def on_trash(self):
        locations.detach_location(self)
