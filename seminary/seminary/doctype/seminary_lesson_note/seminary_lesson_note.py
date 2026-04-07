# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SeminaryLessonNote(Document):
    def validate(self):
        if not self.member:
            self.member = frappe.session.user


@frappe.whitelist()
def get_note(lesson):
    """Fetch the current user's note for a lesson."""
    note = frappe.db.get_value(
        "Seminary Lesson Note",
        {"lesson": lesson, "member": frappe.session.user},
        ["name", "note"],
        as_dict=True,
    )
    return note
