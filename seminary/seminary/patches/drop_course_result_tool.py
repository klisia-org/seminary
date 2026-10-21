"""Retire Course Result Tool.

A single doctype with an empty controller and an HTML field nothing filled; its
course link pointed at a doctype that does not exist. Course Gradebook is the
working grid. A single keeps only its settings row, so nothing is converted.
"""

import frappe


def execute():
    if frappe.db.exists("DocType", "Course Result Tool"):
        frappe.delete_doc(
            "DocType", "Course Result Tool", force=True, ignore_missing=True
        )
    frappe.db.delete("Singles", {"doctype": "Course Result Tool"})
