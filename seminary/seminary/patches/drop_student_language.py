"""Retire Student Language.

An Education leftover: a one-field lookup that no field links to and no code
reads. Language preferences live on Frappe's Language (Person.language).
"""

import frappe


def execute():
    if frappe.db.exists("DocType", "Student Language"):
        frappe.delete_doc(
            "DocType", "Student Language", force=True, ignore_missing=True
        )
    frappe.db.sql_ddl("DROP TABLE IF EXISTS `tabStudent Language`")
