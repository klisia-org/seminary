"""Unmet Demand — students who waitlisted for a section but never got a seat
(terminal Unseated state). The room-scarcity signal: it quantifies how much
demand the available rooms turned away (see ADR 035)."""

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
            "fieldname": "unseated",
            "label": _("Turned Away"),
            "fieldtype": "Int",
            "width": 110,
        },
    ]


def get_data(filters):
    conditions = ["cei.workflow_state = 'Unseated'"]
    params = {}
    if filters.get("academic_term"):
        conditions.append("cs.academic_term = %(academic_term)s")
        params["academic_term"] = filters["academic_term"]

    return frappe.db.sql(
        f"""
        SELECT cs.name AS course_schedule, cs.course, cs.academic_term, cs.room,
               cs.max_enrollment, COUNT(*) AS unseated
        FROM `tabCourse Enrollment Individual` cei
        JOIN `tabCourse Schedule` cs ON cs.name = cei.coursesc_ce
        WHERE {' AND '.join(conditions)}
        GROUP BY cs.name, cs.course, cs.academic_term, cs.room, cs.max_enrollment
        ORDER BY unseated DESC, cs.name
        """,
        params,
        as_dict=True,
    )
