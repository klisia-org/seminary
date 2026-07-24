# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class CohortMembership(Document):
    def validate(self):
        # `active` is derived from invite_status — it is the single field the
        # roster and permission queries filter on, so keep it in lock-step.
        self.active = 1 if self.invite_status == "Active" else 0
        if self.invite_status == "Active" and not self.joined_on:
            self.joined_on = today()
        if self.invite_status in ("Left", "Removed") and not self.left_on:
            self.left_on = today()
        self._guard_single_active()

    def _guard_single_active(self):
        """At most one active membership per (cohort, person)."""
        if not self.active:
            return
        clash = frappe.db.exists(
            "Cohort Membership",
            {
                "cohort": self.cohort,
                "person": self.person,
                "active": 1,
                "name": ["!=", self.name or ""],
            },
        )
        if clash:
            frappe.throw(
                _("{0} is already an active member of this cohort.").format(
                    frappe.bold(self.person)
                )
            )
