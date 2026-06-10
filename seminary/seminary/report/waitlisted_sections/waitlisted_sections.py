"""Waitlisted Sections — every section with students currently on the waitlist,
so the registrar can decide whether to open a bigger room or add a section
(see ADR 035)."""

import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {
            "fieldname": "course_schedule",
            "label": _("Section"),
            "fieldtype": "Link",
            "options": "Course Schedule",
            "width": 260,
        },
        {
            "fieldname": "course",
            "label": _("Course"),
            "fieldtype": "Link",
            "options": "Course",
            "width": 200,
        },
        {
            "fieldname": "academic_term",
            "label": _("Term"),
            "fieldtype": "Link",
            "options": "Academic Term",
            "width": 130,
        },
        {
            "fieldname": "room",
            "label": _("Room"),
            "fieldtype": "Link",
            "options": "Room",
            "width": 130,
        },
        {
            "fieldname": "max_enrollment",
            "label": _("Cap"),
            "fieldtype": "Int",
            "width": 70,
        },
        {
            "fieldname": "seats_used",
            "label": _("Seats Used"),
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "fieldname": "waitlist_count",
            "label": _("Waitlist"),
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "fieldname": "registrations",
            "label": _("Total Demand"),
            "fieldtype": "Int",
            "width": 110,
        },
    ]


def get_data(filters):
    conditions = ["cs.waitlist_count > 0"]
    params = {}
    if filters.get("academic_term"):
        conditions.append("cs.academic_term = %(academic_term)s")
        params["academic_term"] = filters["academic_term"]

    return frappe.db.sql(
        f"""
        SELECT cs.name AS course_schedule, cs.course, cs.academic_term, cs.room,
               cs.max_enrollment, cs.seats_used, cs.waitlist_count, cs.registrations
        FROM `tabCourse Schedule` cs
        WHERE {' AND '.join(conditions)}
        ORDER BY cs.waitlist_count DESC, cs.name
        """,
        params,
        as_dict=True,
    )
