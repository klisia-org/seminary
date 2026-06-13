"""Backfill Student Attendance.meeting (ADR 051).

Attendance is now keyed to the specific class meeting (a section can meet more
than once on a date). This links each legacy row — keyed only by
(student, course_schedule, date) — to its Course Schedule Meeting Dates row.
When a date carries more than one meeting the earliest (by time) is chosen and
the count of such ambiguous rows is reported. Running this before per-meeting
marking is used prevents a re-mark from creating a duplicate record.
"""

import frappe


def execute():
    rows = frappe.get_all(
        "Student Attendance",
        filters={
            "meeting": ("in", (None, "")),
            "course_schedule": ("is", "set"),
            "date": ("is", "set"),
        },
        fields=["name", "course_schedule", "date"],
    )
    if not rows:
        return

    meetings_by_cs = {}
    updated = ambiguous = 0
    for r in rows:
        meetings = meetings_by_cs.get(r.course_schedule)
        if meetings is None:
            meetings = frappe.get_all(
                "Course Schedule Meeting Dates",
                filters={"parent": r.course_schedule},
                fields=["name", "cs_meetdate", "cs_fromtime"],
                order_by="cs_meetdate asc, cs_fromtime asc",
            )
            meetings_by_cs[r.course_schedule] = meetings

        same_date = [m for m in meetings if str(m.cs_meetdate) == str(r.date)]
        if not same_date:
            continue
        if len(same_date) > 1:
            ambiguous += 1
        frappe.db.set_value(
            "Student Attendance",
            r.name,
            "meeting",
            same_date[0].name,
            update_modified=False,
        )
        updated += 1

    frappe.db.commit()
    print(
        f"Student Attendance.meeting backfilled: {updated} of {len(rows)} rows "
        f"({ambiguous} on multi-meeting dates resolved to the earliest meeting)."
    )
