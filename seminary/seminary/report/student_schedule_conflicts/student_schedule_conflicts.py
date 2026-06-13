# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Registrar worksheet for student schedule double-bookings (ADR 050).

Double-booking is allowed on purpose (students hold a seat while waiting on a
preferred section), so nothing blocks it — this report is the registrar's
actionable view of the conflicts that resulted. One row per enrolled side of a
clash, so the registrar can check the specific enrollment to drop. The ``alert``
flag is raised whenever either side of a pair is already Submitted (rostered),
which is the case worth prioritising.
"""

import frappe
from frappe import _

# Enrollment states that occupy a student's calendar (mirrors utils.student_schedule_conflicts).
_INACTIVE_STATES = ("Withdrawn", "Unseated")

_DAY_FIELDS = [
    ("monday", "M"),
    ("tuesday", "T"),
    ("wednesday", "W"),
    ("thursday", "Th"),
    ("friday", "F"),
    ("saturday", "Sa"),
    ("sunday", "Su"),
]


def execute(filters=None):
    filters = filters or {}
    columns = _columns()
    rows = _rows(filters)
    return columns, rows


def _columns():
    return [
        {
            "label": _("Alert"),
            "fieldname": "alert",
            "fieldtype": "Check",
            "width": 60,
        },
        {
            "label": _("Student"),
            "fieldname": "student",
            "fieldtype": "Link",
            "options": "Student",
            "width": 150,
        },
        {"label": _("Term"), "fieldname": "term", "fieldtype": "Data", "width": 130},
        {
            "label": _("Enrollment"),
            "fieldname": "enrollment",
            "fieldtype": "Link",
            "options": "Course Enrollment Individual",
            "width": 170,
        },
        {
            "label": _("Course"),
            "fieldname": "course",
            "fieldtype": "Link",
            "options": "Course Schedule",
            "width": 200,
        },
        {"label": _("State"), "fieldname": "state", "fieldtype": "Data", "width": 120},
        {"label": _("Room"), "fieldname": "room", "fieldtype": "Data", "width": 110},
        {"label": _("When"), "fieldname": "when", "fieldtype": "Data", "width": 130},
        {
            "label": _("Conflicts With"),
            "fieldname": "conflicts_with",
            "fieldtype": "Data",
            "width": 260,
        },
        {
            "label": _("Overlap Dates"),
            "fieldname": "overlap_dates",
            "fieldtype": "Data",
            "width": 200,
        },
    ]


def _rows(filters):
    pairs = _conflicting_pairs(filters.get("academic_term"))
    if not pairs:
        return []

    # Day/time label for every course schedule that appears in a clash.
    cs_names = {p[k] for p in pairs for k in ("cs_a", "cs_b")}
    when_by_cs = _when_labels(cs_names)

    # Aggregate to one row per enrolled side; a CEI clashing with several others
    # collects all counterparts and overlap dates under a single row.
    by_cei = {}
    for p in pairs:
        _add_side(by_cei, p, "a", "b", when_by_cs)
        _add_side(by_cei, p, "b", "a", when_by_cs)

    rows = []
    only_alert = frappe.utils.cint(filters.get("submitted_only"))
    for r in by_cei.values():
        if only_alert and not r["alert"]:
            continue
        r["conflicts_with"] = "; ".join(sorted(r.pop("_counterparts")))
        r["overlap_dates"] = ", ".join(
            frappe.utils.formatdate(d, "MMM d") for d in sorted(r.pop("_dates"))
        )
        rows.append(r)

    rows.sort(key=lambda r: (-r["alert"], r["term"] or "", r["student"] or ""))
    return rows


def _add_side(by_cei, p, this, other, when_by_cs):
    cei = p[f"cei_{this}"]
    state = p[f"state_{this}"]
    other_state = p[f"state_{other}"]
    alert = 1 if (state == "Submitted" or other_state == "Submitted") else 0

    row = by_cei.get(cei)
    if not row:
        row = {
            "alert": alert,
            "student": p["student"],
            "term": p["term"],
            "enrollment": cei,
            "course": p[f"cs_{this}"],
            "state": state,
            "room": p[f"room_{this}"] or "",
            "when": when_by_cs.get(p[f"cs_{this}"], ""),
            "_counterparts": set(),
            "_dates": set(),
        }
        by_cei[cei] = row
    row["alert"] = max(row["alert"], alert)
    row["_counterparts"].add(
        "{0} ({1})".format(p[f"title_{other}"] or p[f"cs_{other}"], other_state or "")
    )
    if p["meetdate"]:
        row["_dates"].add(p["meetdate"])


def _conflicting_pairs(academic_term):
    """Overlapping enrollment pairs for the same student (one row per shared date).

    Self-join keeps cei_b.name > cei_a.name so each pair surfaces once; the
    meeting-date join with strict time overlap mirrors ADR-038 room detection.
    """
    conditions = ""
    params = {"inactive": _INACTIVE_STATES}
    if academic_term:
        conditions = "AND cei_a.academic_term = %(term)s"
        params["term"] = academic_term

    return frappe.db.sql(
        f"""
        SELECT DISTINCT
            cei_a.name AS cei_a, cei_a.workflow_state AS state_a,
            cs_a.name AS cs_a, cs_a.title AS title_a, cs_a.room AS room_a,
            cei_b.name AS cei_b, cei_b.workflow_state AS state_b,
            cs_b.name AS cs_b, cs_b.title AS title_b, cs_b.room AS room_b,
            cei_a.student_ce AS student, cei_a.academic_term AS term,
            ma.cs_meetdate AS meetdate
        FROM `tabCourse Enrollment Individual` cei_a
        JOIN `tabCourse Enrollment Individual` cei_b
            ON cei_b.student_ce = cei_a.student_ce
           AND cei_b.name > cei_a.name
           AND cei_b.docstatus < 2
           AND cei_b.audit = 0
           AND cei_b.withdrawn = 0
           AND cei_b.course_cancelled = 0
           AND COALESCE(cei_b.workflow_state, '') NOT IN %(inactive)s
        JOIN `tabCourse Schedule` cs_a
            ON cs_a.name = cei_a.coursesc_ce
           AND COALESCE(cs_a.workflow_state, '') != 'Cancelled'
        JOIN `tabCourse Schedule` cs_b
            ON cs_b.name = cei_b.coursesc_ce
           AND cs_b.name != cs_a.name
           AND COALESCE(cs_b.workflow_state, '') != 'Cancelled'
        JOIN `tabCourse Schedule Meeting Dates` ma ON ma.parent = cs_a.name
        JOIN `tabCourse Schedule Meeting Dates` mb
            ON mb.parent = cs_b.name
           AND mb.cs_meetdate = ma.cs_meetdate
           AND ma.cs_fromtime < mb.cs_totime
           AND mb.cs_fromtime < ma.cs_totime
        WHERE cei_a.docstatus < 2
          AND cei_a.audit = 0
          AND cei_a.withdrawn = 0
          AND cei_a.course_cancelled = 0
          AND COALESCE(cei_a.workflow_state, '') NOT IN %(inactive)s
          {conditions}
        ORDER BY ma.cs_meetdate
        """,
        params,
        as_dict=True,
    )


def _when_labels(cs_names):
    if not cs_names:
        return {}
    fields = ["name", "modality", "from_time", "to_time"] + [
        d for d, _abbr in _DAY_FIELDS
    ]
    labels = {}
    for cs in frappe.get_all(
        "Course Schedule", filters={"name": ["in", list(cs_names)]}, fields=fields
    ):
        days = "".join(abbr for field, abbr in _DAY_FIELDS if cs.get(field))
        time = ""
        if cs.from_time:
            time = frappe.utils.format_time(cs.from_time, "h:mm a")
            if cs.to_time:
                time += "–" + frappe.utils.format_time(cs.to_time, "h:mm a")
        labels[cs.name] = " ".join(part for part in (days, time) if part)
    return labels
