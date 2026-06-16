# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from seminary.partner import internship


class InternshipHoursLog(Document):
    def validate(self):
        if (self.hours or 0) <= 0:
            frappe.throw(_("Logged hours must be greater than zero."))
        self._stamp_verification()

    def after_insert(self):
        internship.recompute_placement_hours(self.internship_placement)

    def on_update(self):
        internship.recompute_placement_hours(self.internship_placement)

    def on_trash(self):
        internship.recompute_placement_hours(self.internship_placement)

    def _stamp_verification(self):
        if self.supervisor_verified:
            if not self.verified_on:
                self.verified_on = now_datetime()
                self.verified_by = frappe.db.get_value(
                    "Person", {"user": frappe.session.user}, "name"
                )
        else:
            self.verified_on = None
            self.verified_by = None
