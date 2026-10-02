# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt
"""Ethnic groups are a list each school keeps (ADR 086).

The seed is the six values seminary used to ship as a fixed Select, so nothing changes until a
school edits the list. A school replaces it with the categories it reports. Values already stored
are kept: the patch makes each one a group if it is missing.
"""

import frappe
from frappe import _

DOCTYPE = "Ethnic Group"
DEFAULT_GROUPS = (
    "Black",
    "Hispanic",
    "White, Non Hispanic",
    "Native American",
    "Pacific Islander",
    "Other",
)
# (doctype, field) pairs that link to the list.
LINKED = (("Person", "ethnicity"), ("Student Applicant", "ethnic"))


def seed_ethnic_groups():
    """Create-only-if-missing: the list is curated on the desk, so a re-seed never undoes an edit."""
    if not frappe.db.exists("DocType", DOCTYPE):
        return
    for order, name in enumerate(DEFAULT_GROUPS, start=1):
        if not frappe.db.exists(DOCTYPE, name):
            frappe.get_doc(
                {
                    "doctype": DOCTYPE,
                    "group_name": name,
                    "is_active": 1,
                    "display_order": order,
                }
            ).insert(ignore_permissions=True)


def keep_existing_values():
    """Every value already stored becomes a group, so no record loses what it held."""
    if not frappe.db.exists("DocType", DOCTYPE):
        return
    seed_ethnic_groups()
    for doctype, field in LINKED:
        if not frappe.db.has_column(doctype, field):
            continue
        for value in frappe.get_all(
            doctype, filters={field: ("is", "set")}, pluck=field, distinct=True
        ):
            if value and not frappe.db.exists(DOCTYPE, value):
                frappe.get_doc(
                    {"doctype": DOCTYPE, "group_name": value, "is_active": 1}
                ).insert(ignore_permissions=True)


def validate_active(doc, field):
    """A new or changed value must be an active group; a value kept from before is left alone."""
    value = doc.get(field)
    if not value:
        return
    before = doc.get_doc_before_save() if not doc.is_new() else None
    if before and before.get(field) == value:
        return
    if not frappe.db.get_value(DOCTYPE, value, "is_active"):
        frappe.throw(_("{0} is not an active ethnic group.").format(value))
