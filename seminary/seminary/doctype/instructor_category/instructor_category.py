# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document


class InstructorCategory(Document):
    def validate(self):
        self.validate_single_active_rate_per_mode()

    def validate_single_active_rate_per_mode(self):
        """At most one active rate per pay mode — older rates must be deactivated."""
        active_by_mode = defaultdict(list)
        for rate in self.get("rates", []):
            if rate.active:
                active_by_mode[rate.pay_mode].append(rate)
        for mode, rows in active_by_mode.items():
            if len(rows) > 1:
                frappe.throw(
                    _(
                        "Only one Active rate is allowed per Pay Mode ({0}). "
                        "Uncheck Active on older rows."
                    ).format(mode)
                )


def resolve_rate(category: str, pay_mode: str, target_date) -> dict | None:
    """Return the rate row that applies on ``target_date`` for the given category/mode.

    Picks the row with the greatest ``effective_from`` that is ≤ target_date.
    Ignores ``active`` so historical slips reprice correctly after a rate is
    deactivated.
    """
    rows = frappe.db.sql(
        """
        select amount, currency, effective_from, active
        from `tabInstructor Category Rate`
        where parent = %(category)s
          and pay_mode = %(pay_mode)s
          and effective_from <= %(target_date)s
        order by effective_from desc
        limit 1
        """,
        {"category": category, "pay_mode": pay_mode, "target_date": target_date},
        as_dict=True,
    )
    return rows[0] if rows else None
