# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Backfill Person.gender from existing Student records.

Gender is a shared human attribute and now lives on the Person spine (ADR 042).
Existing students already carry a gender; copy it onto their Person where the
spine has none yet, so roles read a consistent value going forward."""

import frappe


def execute():
    if not frappe.db.has_column("Person", "gender"):
        return
    rows = frappe.get_all(
        "Student",
        filters={"person": ("is", "set"), "gender": ("is", "set")},
        fields=["person", "gender"],
    )
    for row in rows:
        if not frappe.db.get_value("Person", row.person, "gender"):
            frappe.db.set_value(
                "Person", row.person, "gender", row.gender, update_modified=False
            )
    frappe.db.commit()
