# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt
"""Backfill Faculty Capability.requires_instructor (ADR 062).

The flag was added when the capability engine became person-keyed. Existing
capabilities all required an Instructor except the Committee/Board Member seat, so
set requires_instructor = 1 everywhere, then clear it for the organizational
capacities a plain Person may hold (Committee/Board Member, training oversight).
One-time; admins curate after.
"""

import frappe

# routes_to keys for organizational capacities that do NOT require an Instructor.
ORG_ROUTES = (
    "Committee/Board Member",
    "Oversees Unit Training",
)


def execute():
    if not frappe.db.has_column("Faculty Capability", "requires_instructor"):
        return
    # Default everything to "needs a faculty record" — matches pre-ADR-062 behaviour.
    frappe.db.sql("UPDATE `tabFaculty Capability` SET requires_instructor = 1")
    # Then exempt the organizational capacities.
    frappe.db.set_value(
        "Faculty Capability",
        {"routes_to": ("in", ORG_ROUTES)},
        "requires_instructor",
        0,
        update_modified=False,
    )
    frappe.db.commit()
