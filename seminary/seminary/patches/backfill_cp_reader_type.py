# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Backfill Culminating Project reader-type discriminators (ADR 060).

second_reader / third_reader became Dynamic Link fields needing a companion
*_reader_type. Existing rows held Instructors, so stamp 'Instructor' wherever a
reader is set but the type is blank. Idempotent.
"""

import frappe


def execute():
    for field, type_field in (
        ("second_reader", "second_reader_type"),
        ("third_reader", "third_reader_type"),
    ):
        if not frappe.db.has_column("Culminating Project", type_field):
            continue
        frappe.db.sql(
            f"""
            UPDATE `tabCulminating Project`
            SET `{type_field}` = 'Instructor'
            WHERE IFNULL(`{field}`, '') != '' AND IFNULL(`{type_field}`, '') = ''
            """
        )
    frappe.db.commit()
