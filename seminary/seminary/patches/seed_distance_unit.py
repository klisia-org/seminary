# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Give an existing site a distance unit for the cohort planner (ADR 067 §6).

A Select's `default` only reaches documents created after it, and Seminary
Settings is a Single that already exists everywhere -- so without this the field
reads blank on every site that has ever migrated.

Kilometres unless the school is somewhere that thinks in miles. The list is
short and worth being exact about: the United States, Liberia and Myanmar never
adopted the metric system, and the United Kingdom is metric by law but signs its
roads in miles -- and "how far is my mentor" is a road-sign question.
"""

import frappe

MILE_COUNTRIES = ("United States", "Liberia", "Myanmar", "United Kingdom")


def execute():
    # Not `db.has_column`: Seminary Settings is a Single, so there is no
    # `tabSeminary Settings` to look a column up in and the check raises rather
    # than returning False.
    if not frappe.get_meta("Seminary Settings").get_field("distance_unit"):
        return
    if frappe.db.get_single_value("Seminary Settings", "distance_unit"):
        return

    country = frappe.db.get_default("country") or frappe.db.get_single_value(
        "System Settings", "country"
    )
    unit = "Miles" if country in MILE_COUNTRIES else "Kilometres"
    frappe.db.set_single_value("Seminary Settings", "distance_unit", unit)
