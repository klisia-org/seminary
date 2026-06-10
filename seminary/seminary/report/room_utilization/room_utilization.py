"""Room Utilization — what each room is used for in a term, and which rooms are
free. Helps registrars shift sections around when a room is over-subscribed or
sitting empty (see ADR 035)."""

import frappe
from frappe import _

_DAYS = [
    ("monday", "Mon"),
    ("tuesday", "Tue"),
    ("wednesday", "Wed"),
    ("thursday", "Thu"),
    ("friday", "Fri"),
    ("saturday", "Sat"),
    ("sunday", "Sun"),
]


def execute(filters=None):
    filters = filters or {}
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {
            "fieldname": "room",
            "label": _("Room"),
            "fieldtype": "Link",
            "options": "Room",
            "width": 160,
        },
        {
            "fieldname": "seating_capacity",
            "label": _("Capacity"),
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "fieldname": "course_schedule",
            "label": _("Section"),
            "fieldtype": "Link",
            "options": "Course Schedule",
            "width": 240,
        },
        {"fieldname": "days", "label": _("Days"), "fieldtype": "Data", "width": 140},
        {
            "fieldname": "from_time",
            "label": _("From"),
            "fieldtype": "Time",
            "width": 80,
        },
        {"fieldname": "to_time", "label": _("To"), "fieldtype": "Time", "width": 80},
        {
            "fieldname": "seats_used",
            "label": _("Seats Used"),
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "fieldname": "max_enrollment",
            "label": _("Cap"),
            "fieldtype": "Int",
            "width": 70,
        },
        {
            "fieldname": "waitlist_count",
            "label": _("Waitlist"),
            "fieldtype": "Int",
            "width": 80,
        },
    ]


def get_data(filters):
    term_cond = "aterm.iscurrent_acterm = 1"
    params = {}
    if filters.get("academic_term"):
        term_cond = "cs.academic_term = %(academic_term)s"
        params["academic_term"] = filters["academic_term"]

    sections = frappe.db.sql(
        f"""
        SELECT cs.name AS course_schedule, cs.room, cs.from_time, cs.to_time,
               cs.seats_used, cs.max_enrollment, cs.waitlist_count,
               cs.monday, cs.tuesday, cs.wednesday, cs.thursday,
               cs.friday, cs.saturday, cs.sunday,
               r.seating_capacity
        FROM `tabCourse Schedule` cs
        JOIN `tabAcademic Term` aterm ON aterm.name = cs.academic_term
        LEFT JOIN `tabRoom` r ON r.name = cs.room
        WHERE {term_cond}
          AND COALESCE(cs.workflow_state, '') != 'Cancelled'
          AND cs.room IS NOT NULL AND cs.room != ''
        ORDER BY cs.room, cs.from_time
        """,
        params,
        as_dict=True,
    )

    used_rooms = set()
    data = []
    for s in sections:
        used_rooms.add(s.room)
        s["days"] = " ".join(label for field, label in _DAYS if s.get(field))
        data.append(s)

    # Surface rooms with no sections this term so "what's free" is visible.
    for room in frappe.get_all(
        "Room", fields=["name", "seating_capacity"], order_by="name"
    ):
        if room.name not in used_rooms:
            data.append(
                {
                    "room": room.name,
                    "seating_capacity": room.seating_capacity,
                    "course_schedule": None,
                    "days": _("(no sections — free)"),
                }
            )

    return data
