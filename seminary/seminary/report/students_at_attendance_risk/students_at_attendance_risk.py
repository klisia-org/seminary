# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = [
        {
            "label": "Roster",
            "fieldname": "roster",
            "fieldtype": "Link",
            "options": "Scheduled Course Roster",
            "width": 200,
        },
        {
            "label": "Student",
            "fieldname": "student_name",
            "fieldtype": "Data",
            "width": 170,
        },
        {"label": "Program", "fieldname": "program", "fieldtype": "Data", "width": 150},
        {
            "label": "Course",
            "fieldname": "course",
            "fieldtype": "Link",
            "options": "Course Schedule",
            "width": 240,
        },
        {
            "label": "Absences",
            "fieldname": "effective_absences",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": "Limit",
            "fieldname": "absence_limit",
            "fieldtype": "Int",
            "width": 70,
        },
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {
            "label": "FA",
            "fieldname": "failed_for_absence",
            "fieldtype": "Check",
            "width": 60,
        },
    ]

    rows = frappe.get_all(
        "Scheduled Course Roster",
        filters={"active": 1, "audit_bool": 0, "attendance_alert_level": [">=", 1]},
        fields=[
            "name as roster",
            "stuname_roster as student_name",
            "program_std_scr as program",
            "course_sc as course",
            "effective_absences",
            "absence_limit",
            "attendance_alert_level",
            "failed_for_absence",
        ],
        order_by="attendance_alert_level desc, course_sc, stuname_roster",
    )
    for r in rows:
        r["status"] = (
            "Over limit" if (r.attendance_alert_level or 0) >= 2 else "At risk"
        )

    return columns, rows
