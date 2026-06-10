"""Normalize Room.seating_capacity before it becomes an Int column.

`seating_capacity` shipped as a Data (text) field; ADR 038 needs it as an Int
for capacity math. This runs in pre_model_sync (column is still text) and
normalizes every value to a plain digit string so the post-sync Data→Int alter
coerces cleanly. Two cases the raw alter would choke on:
  - free text like "100 seats" → strip to "100"
  - NULL → "0" (Frappe Int columns are NOT NULL DEFAULT 0, and MariaDB strict
    mode rejects converting a NULL row into them)
"""

import re

import frappe


def execute():
    if not frappe.db.has_column("Room", "seating_capacity"):
        return
    rows = frappe.db.sql("SELECT name, seating_capacity FROM `tabRoom`", as_dict=True)
    for row in rows:
        raw = row.seating_capacity
        digits = "" if raw is None else re.sub(r"[^0-9]", "", str(raw))
        cleaned = digits or "0"
        if raw is None or cleaned != str(raw):
            frappe.db.set_value(
                "Room", row.name, "seating_capacity", cleaned, update_modified=False
            )
    frappe.db.commit()
