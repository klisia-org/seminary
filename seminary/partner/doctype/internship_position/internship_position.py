# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class InternshipPosition(Document):
    def validate(self):
        self._set_route()
        self._validate_dates()
        self._validate_allowed_type()

    def _validate_allowed_type(self):
        """An organization that lists approved internship types may only post
        positions of those types; an empty list means any type is allowed."""
        allowed = frappe.get_all(
            "Partner Allowed Internship Type",
            filters={"parenttype": "Partner Organization", "parent": self.partner_org},
            pluck="internship_type",
        )
        if allowed and self.internship_type not in allowed:
            frappe.throw(
                _(
                    "{0} is not approved to offer the internship type {1}. Approved types: {2}."
                ).format(
                    frappe.bold(self.partner_org),
                    frappe.bold(self.internship_type),
                    ", ".join(allowed),
                )
            )

    def _set_route(self):
        if not self.route:
            self.route = f"internships/{self.name}"

    def _validate_dates(self):
        if self.flexible_dates:
            return
        if (
            self.preferred_start
            and self.preferred_end
            and self.preferred_end < self.preferred_start
        ):
            frappe.throw(
                _("Preferred end date cannot be before the preferred start date.")
            )

    def sync_placements_filled(self):
        """Keep `placements_filled` in step with accepted applications, and
        auto-close (never auto-reopen) the position when full."""
        accepted = frappe.db.count(
            "Internship Application",
            {
                "internship_position": self.name,
                "status": ("in", ("Accepted", "Active", "Completed")),
            },
        )
        updates = {"placements_filled": accepted}
        if (
            (self.planned_placements or 0)
            and accepted >= self.planned_placements
            and self.status == "Open"
        ):
            updates["status"] = "Closed"
        frappe.db.set_value("Internship Position", self.name, updates)
