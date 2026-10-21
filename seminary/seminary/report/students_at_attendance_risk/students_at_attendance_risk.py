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
        {
            "label": "Decision",
            "fieldname": "absence_decision",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": "Decided By",
            "fieldname": "absence_decided_by",
            "fieldtype": "Link",
            "options": "User",
            "width": 160,
        },
        {
            "label": "Reason",
            "fieldname": "absence_decision_reason",
            "fieldtype": "Data",
            "width": 220,
        },
    ]

    fields = [
        "name as roster",
        "stuname_roster as student_name",
        "program_std_scr as program",
        "course_sc as course",
        "effective_absences",
        "absence_limit",
        "attendance_alert_level",
        "failed_for_absence",
        "absence_decision",
        "absence_decided_by",
        "absence_decision_reason",
        "active",
    ]
    # Students still in class who are at risk, plus every decision made at or
    # after Send Grades -- those rosters are no longer active (ADR 081).
    rows = frappe.get_all(
        "Scheduled Course Roster",
        filters={"active": 1, "audit_bool": 0, "attendance_alert_level": [">=", 1]},
        fields=fields,
    )
    seen = {r.roster for r in rows}
    rows += [
        r
        for r in frappe.get_all(
            "Scheduled Course Roster",
            filters={"absence_decision": ["is", "set"]},
            fields=fields,
        )
        if r.roster not in seen
    ]

    decision = (filters or {}).get("absence_decision")
    if decision:
        rows = [r for r in rows if r.absence_decision == decision]

    for r in rows:
        if not r.active:
            r["status"] = "Grades sent"
        else:
            r["status"] = (
                "Over limit" if (r.attendance_alert_level or 0) >= 2 else "At risk"
            )
    rows.sort(
        key=lambda r: (
            r.absence_decision != "No recommendation",
            -(r.attendance_alert_level or 0),
            r.course or "",
            r.student_name or "",
        )
    )

    return columns, rows
