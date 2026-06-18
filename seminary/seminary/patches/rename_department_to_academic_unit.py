# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt
"""Rename Course.department / Program.department -> academic_unit (ADR 059).

Runs in [pre_model_sync] so the physical column is renamed BEFORE the new JSON
(fieldname academic_unit, Link -> Academic Unit) is synced — otherwise model
sync would add an empty academic_unit column and orphan the old data.

The old columns held ERPNext HR Department links (the fields were hidden stubs);
those values are not valid Academic Unit names, so they are nulled.
"""

import frappe

# (DocType, table) pairs whose `department` Link becomes `academic_unit`.
TARGETS = (("Course", "tabCourse"), ("Program", "tabProgram"))


def execute():
    for doctype, table in TARGETS:
        if not frappe.db.table_exists(doctype):
            continue
        columns = frappe.db.get_table_columns(doctype)
        if "department" in columns and "academic_unit" not in columns:
            frappe.db.sql_ddl(
                f"ALTER TABLE `{table}` "
                f"CHANGE `department` `academic_unit` varchar(140)"
            )
        # Null stale HR Department values — the Link now points at Academic Unit.
        if "academic_unit" in frappe.db.get_table_columns(doctype):
            frappe.db.sql(f"UPDATE `{table}` SET `academic_unit` = NULL")

    frappe.db.commit()
