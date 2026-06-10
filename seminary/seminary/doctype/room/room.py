# Copyright (c) 2015, Klisia / SeminaryERP and contributors
# For license information, please see license.txt


from frappe.model.document import Document

from seminary.seminary import locations


class Room(Document):
    def on_update(self):
        locations.ensure_room_location(self)

    def on_trash(self):
        locations.detach_location(self)
