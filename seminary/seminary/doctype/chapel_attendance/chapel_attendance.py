# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Chapel Attendance — one record per student per chapel, created when a student
self checks in (see seminary/seminary/chapel.py). Insert/trash reflects the
student's running count onto their Chapel Attendance graduation requirement."""

import frappe
from frappe import _
from frappe.model.document import Document


class ChapelAttendance(Document):
    def validate(self):
        self._guard_duplicate()

    def _guard_duplicate(self):
        if not (self.chapel and self.student):
            return
        existing = frappe.db.exists(
            "Chapel Attendance",
            {
                "chapel": self.chapel,
                "student": self.student,
                "name": ("!=", self.name or ""),
            },
        )
        if existing:
            frappe.throw(
                _("{0} has already checked in to this chapel.").format(self.student),
                frappe.DuplicateEntryError,
            )
