"""Retire Student Leave Application (ADR 081).

A leave of absence is a Program Enrollment status, read from its Status History,
and short excused absences are an attendance status. Nothing used the doctype in
production, so its rows are deleted rather than converted.
"""

import frappe


def execute():
    if frappe.db.exists("DocType", "Student Leave Application"):
        frappe.delete_doc(
            "DocType", "Student Leave Application", force=True, ignore_missing=True
        )
    frappe.db.sql_ddl("DROP TABLE IF EXISTS `tabStudent Leave Application`")
    # Ask the table, not has_column: its cache can outlive the column.
    if frappe.db.sql(
        "SHOW COLUMNS FROM `tabStudent Attendance` LIKE 'leave_application'"
    ):
        frappe.db.sql_ddl(
            "ALTER TABLE `tabStudent Attendance` DROP COLUMN `leave_application`"
        )
