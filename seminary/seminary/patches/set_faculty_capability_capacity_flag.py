# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt
"""Backfill Faculty Capability.tracks_capacity (ADR 059).

The flag was added after the starter capabilities were first seeded. Set it on
the capacity-aware routes (advising / examining / verifying); the rest default to
0 (Course Instructor, Mentor, Board/Committee). One-time; admins curate after.
"""

import frappe

CAPACITY_ROUTES = (
    "Thesis/CP Advisor",
    "Internship Advisor",
    "Placement Examiner",
    "Manual-Verification Verifier",
)


def execute():
    if not frappe.db.has_column("Faculty Capability", "tracks_capacity"):
        return
    frappe.db.set_value(
        "Faculty Capability",
        {"routes_to": ("in", CAPACITY_ROUTES)},
        "tracks_capacity",
        1,
        update_modified=False,
    )
    frappe.db.commit()
