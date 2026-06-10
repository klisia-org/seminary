# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from seminary.seminary import locations


class Building(Document):
    def on_update(self):
        locations.ensure_building_location(self)

    def on_trash(self):
        locations.detach_location(self)
