# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""ADR 056 follow-up: the Course/Emphasis prerequisites were first modeled as
Table MultiSelect child tables on Program Grad Req Items, but Frappe forbids
table fields on a child doctype (no grandchildren), so they never loaded or
saved. They were reworked to single Link fields. Drop the now-orphaned child
doctypes (and their empty tables) if an earlier migrate created them."""

import frappe


def execute():
    for dt in ("Grad Req Course Prerequisite", "Grad Req Emphasis Scope"):
        if frappe.db.exists("DocType", dt):
            frappe.delete_doc("DocType", dt, force=1, ignore_permissions=True)
