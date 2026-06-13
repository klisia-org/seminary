# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Course attendance: student self check-in.

Mirrors the Chapel self check-in pattern (seminary/seminary/chapel.py) for
regular class meetings. Each Course Schedule meeting (a row in the
`cs_meetinfo` child table) can carry a human-readable `checkin_code`, generated
on demand by the instructor from the attendance page.

Students check in from their course card ("Mark my attendance"). Two modes,
controlled by Seminary Settings `enforce_time_window`:

* **Enforced (time-based):** the meeting happening now (inside the configured
  window) is auto-selected; a code may be required; a late check-in is recorded
  Tardy. Relies on the site Time Zone matching the seminary.
* **Not enforced (catch-up):** the student picks any past meeting they have no
  attendance for. No clock dependency, no code.

Either way the instructor still reviews and finalizes the roster via
`mark_attendance` (api.py). Records are written through the shared, idempotent
`make_attendance_records` helper.
"""

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import add_to_date, get_time, getdate, now_datetime, today

from seminary.seminary.api import make_attendance_records
from seminary.seminary.utils import generate_checkin_code, get_current_student

# Auditors (audit_bool=1) are excluded — matches the instructor attendance roster.
ROSTER_FILTERS = {"active": 1, "audit_bool": 0}


# ---------------------------------------------------------------------------
# Meeting time window / code / status helpers
# ---------------------------------------------------------------------------


def _combine(meetdate, time_val):
    """A datetime from a meeting Date + a Time field (stored as a timedelta)."""
    d = getdate(meetdate)
    base = datetime(d.year, d.month, d.day)
    if time_val is None or time_val == "":
        return base
    if isinstance(time_val, timedelta):
        return base + time_val
    return datetime.combine(d, get_time(time_val))


def _window_bounds(start_dt, end_dt, settings):
    """(open_dt, close_dt) for self check-in: the meeting's span widened by the
    configured grace minutes. Used only when the time window is enforced."""
    before = int(settings.course_checkin_opens_before_mins or 0)
    after = int(settings.course_checkin_closes_after_mins or 0)
    return (
        add_to_date(start_dt, minutes=-before),
        add_to_date(end_dt or start_dt, minutes=after),
    )


def _is_open_now(start_dt, end_dt, settings, now=None):
    lo, hi = _window_bounds(start_dt, end_dt, settings)
    now = now or now_datetime()
    return lo <= now <= hi


def _validate_code(meeting_row, settings, code):
    if not settings.require_course_checkin_code:
        return
    expected = (meeting_row.get("checkin_code") or "").strip().upper()
    given = (code or "").strip().upper()
    if not expected or given != expected:
        frappe.throw(_("Incorrect or missing check-in code."))


def _status_for(start_dt, settings, now=None):
    """Present, or Tardy when checking in past the grace period after start."""
    grace = int(settings.course_checkin_tardy_after_mins or 0)
    if grace <= 0:
        return "Present"
    now = now or now_datetime()
    return "Tardy" if now > add_to_date(start_dt, minutes=grace) else "Present"


def _meeting_times(row):
    start = _combine(row.cs_meetdate, row.cs_fromtime)
    end = _combine(row.cs_meetdate, row.cs_totime) if row.cs_totime else None
    return start, end


def _meetings_on(schedule_doc, meeting_date):
    """All meeting rows on a given date. Attendance is keyed per (student,
    course, date), but a schedule may carry more than one row for a date."""
    target = getdate(meeting_date)
    return [
        row
        for row in (schedule_doc.cs_meetinfo or [])
        if getdate(row.cs_meetdate) == target
    ]


def _open_meeting(rows, settings, now=None):
    """The first row on the date whose check-in window is open now, else None.
    Resolves the same-date collision: validate/generate against the row that is
    actually happening, not just the first one matching the date."""
    now = now or now_datetime()
    for row in rows:
        start, end = _meeting_times(row)
        if _is_open_now(start, end, settings, now):
            return row
    return None


def _enrolled(course_schedule, student):
    return frappe.db.exists(
        "Scheduled Course Roster",
        {"course_sc": course_schedule, "student": student, **ROSTER_FILTERS},
    )


def _tracks_online(settings):
    """Whether online meetings are attendance-bearing (ADR 051). Defaults to True
    when the setting is absent."""
    v = settings.get("track_online_attendance")
    return v is None or bool(v)


def _recorded(student, course_schedule):
    """(meeting names, dates as strings) the student already has attendance for.

    Meetings is authoritative once attendance is keyed per-meeting (ADR 051);
    dates still covers legacy rows whose ``meeting`` isn't set yet."""
    rows = frappe.get_all(
        "Student Attendance",
        filters={"student": student, "course_schedule": course_schedule},
        fields=["meeting", "date"],
    )
    meetings = {r.meeting for r in rows if r.meeting}
    dates = {str(r.date) for r in rows if r.date}
    return meetings, dates


def _is_recorded(row, recorded):
    """Whether this meeting row is already attended — by meeting name, or by date
    for un-backfilled legacy rows."""
    meetings, dates = recorded
    return row.name in meetings or str(getdate(row.cs_meetdate)) in dates


# ---------------------------------------------------------------------------
# Per-course context (drives the "Mark my attendance" button on the course card)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_course_checkin_context(course_schedule):
    """Whether the current student can self check-in to this course, and what to
    offer them. `eligible` is False (button hidden) unless they are enrolled and
    the course has meeting dates.

    Enforced mode → `open_meeting` (the meeting happening now) or None.
    Catch-up mode → `pending` (past meetings with no attendance yet)."""
    student = get_current_student()
    if not student or not _enrolled(course_schedule, student.name):
        return {"eligible": False}

    schedule_doc = frappe.get_doc("Course Schedule", course_schedule)
    meetings = schedule_doc.cs_meetinfo or []
    if not meetings:
        return {"eligible": False}

    settings = frappe.get_cached_doc("Seminary Settings")
    enforce = bool(settings.enforce_time_window)
    track_online = _tracks_online(settings)
    recorded = _recorded(student.name, course_schedule)

    ctx = {
        "eligible": True,
        "enforce": enforce,
        "requires_code": bool(settings.require_course_checkin_code) and enforce,
        "course_title": schedule_doc.title or schedule_doc.course,
    }

    if enforce:
        now = now_datetime()
        ctx["open_meeting"] = None
        for row in meetings:
            if row.cs_online and not track_online:
                continue
            start, end = _meeting_times(row)
            if _is_open_now(start, end, settings, now):
                ctx["open_meeting"] = {
                    "meeting_date": str(getdate(row.cs_meetdate)),
                    "meeting": row.name,
                    "from_time": str(row.cs_fromtime) if row.cs_fromtime else None,
                    "to_time": str(row.cs_totime) if row.cs_totime else None,
                    "already_checked_in": _is_recorded(row, recorded),
                }
                break
    else:
        today_d = getdate(today())
        ctx["pending"] = [
            {
                "meeting_date": str(getdate(r.cs_meetdate)),
                "meeting": r.name,
                "from_time": str(r.cs_fromtime) if r.cs_fromtime else None,
                "to_time": str(r.cs_totime) if r.cs_totime else None,
            }
            for r in meetings
            if getdate(r.cs_meetdate) <= today_d
            and not _is_recorded(r, recorded)
            and (track_online or not r.cs_online)
        ]

    return ctx


# ---------------------------------------------------------------------------
# Student self check-in
# ---------------------------------------------------------------------------


@frappe.whitelist()
def course_check_in(course_schedule, meeting_date, code=None, meeting=None):
    """Student self check-in for a class meeting. Validates enrollment, then —
    when the time window is enforced — the window and code, recording Present or
    Tardy. In catch-up mode (window not enforced) records Present for any past
    meeting. Idempotent: a later check-in updates the existing record.

    ``meeting`` (the specific Course Schedule Meeting Dates row) keys attendance
    per-meeting; a section may meet more than once on one date (ADR 051)."""
    student = get_current_student()
    if not student:
        frappe.throw(_("Only enrolled students can check in."), frappe.PermissionError)

    if not _enrolled(course_schedule, student.name):
        frappe.throw(_("You are not enrolled in this course."), frappe.PermissionError)

    schedule_doc = frappe.get_doc("Course Schedule", course_schedule)
    rows = _meetings_on(schedule_doc, meeting_date)
    if not rows:
        frappe.throw(_("There is no class meeting on that date."))

    settings = frappe.get_cached_doc("Seminary Settings")
    enforce = bool(settings.enforce_time_window)

    # Online meetings aren't attendance-bearing when the policy is off — drop them
    # so neither the open-now resolution nor catch-up can record against one.
    if not _tracks_online(settings):
        rows = [r for r in rows if not r.cs_online]
        if not rows:
            frappe.throw(_("Online meetings don't track attendance."))

    if enforce:
        # Validate against the row that is actually open now (handles >1 row
        # sharing the date), not just the first one matching the date.
        meeting_row = _open_meeting(rows, settings)
        if not meeting_row:
            frappe.throw(_("Check-in for this meeting is not open right now."))
        _validate_code(meeting_row, settings, code)
        status = _status_for(_meeting_times(meeting_row)[0], settings)
    else:
        # Catch-up mode: any past meeting, no code, never auto-Tardy.
        if getdate(meeting_date) > getdate(today()):
            frappe.throw(_("You cannot check in for a future meeting."))
        # Honour the meeting the student picked; fall back to the lone row on
        # the date when the caller didn't specify one.
        meeting_row = next((r for r in rows if r.name == meeting), None)
        if not meeting_row and len(rows) == 1:
            meeting_row = rows[0]
        status = "Present"

    stuname = (
        frappe.db.get_value(
            "Scheduled Course Roster",
            {"course_sc": course_schedule, "student": student.name, **ROSTER_FILTERS},
            "stuname_roster",
        )
        or student.student_name
    )
    make_attendance_records(
        student.name,
        stuname,
        status,
        course_schedule,
        getdate(meeting_date),
        meeting=meeting_row.name if meeting_row else None,
    )
    frappe.db.commit()

    return {
        "status": status,
        "course_schedule": course_schedule,
        "meeting_date": str(getdate(meeting_date)),
        "meeting": meeting_row.name if meeting_row else None,
    }


@frappe.whitelist()
def get_open_course_checkins():
    """Fallback portal feed (e.g. a QR landing with no course preselected): the
    student's meetings available for check-in across all their courses. Honours
    the same enforced / catch-up modes as the per-course context."""
    student = get_current_student()
    if not student:
        return {"meetings": [], "requires_code": False}

    settings = frappe.get_cached_doc("Seminary Settings")
    enforce = bool(settings.enforce_time_window)
    track_online = _tracks_online(settings)
    now = now_datetime()
    today_d = getdate(today())

    schedules = set(
        frappe.get_all(
            "Scheduled Course Roster",
            filters={"student": student.name, **ROSTER_FILTERS},
            pluck="course_sc",
        )
    )

    meetings = []
    for cs_name in schedules:
        cs = frappe.get_doc("Course Schedule", cs_name)
        title = cs.title or cs.course
        recorded = _recorded(student.name, cs_name)
        for row in cs.cs_meetinfo or []:
            if row.cs_online and not track_online:
                continue
            mdate = getdate(row.cs_meetdate)
            mdate_s = str(mdate)
            already = _is_recorded(row, recorded)
            if enforce:
                start, end = _meeting_times(row)
                if not _is_open_now(start, end, settings, now):
                    continue
            else:
                if mdate > today_d or already:
                    continue
            meetings.append(
                {
                    "course_schedule": cs_name,
                    "course_title": title,
                    "meeting_date": mdate_s,
                    "meeting": row.name,
                    "from_time": str(row.cs_fromtime) if row.cs_fromtime else None,
                    "already_checked_in": already,
                }
            )

    meetings.sort(key=lambda m: (m["meeting_date"], m["course_title"]))
    return {
        "meetings": meetings,
        "requires_code": bool(settings.require_course_checkin_code) and enforce,
    }


# ---------------------------------------------------------------------------
# Instructor: on-demand code generation (attendance page)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def ensure_meeting_checkin_code(course_schedule, meeting_date, meeting=None):
    """Return the meeting's check-in code, generating + persisting one the first
    time the instructor displays it. Kept once set so it stays stable for the
    class. Requires write access to the Course Schedule.

    A code is per-MEETING (a section can meet more than once on a date — ADR
    051), so the instructor passes the specific ``meeting`` row; without one we
    fall back to the row open now, else the first on the date."""
    if not frappe.has_permission("Course Schedule", "write", doc=course_schedule):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    schedule_doc = frappe.get_doc("Course Schedule", course_schedule)
    rows = _meetings_on(schedule_doc, meeting_date)
    if not rows:
        frappe.throw(_("There is no class meeting on that date."))

    settings = frappe.get_cached_doc("Seminary Settings")
    row = next((r for r in rows if r.name == meeting), None) if meeting else None
    if not row:
        # Prefer the row open now so the displayed code matches what students
        # validate against this moment; otherwise the first row on the date.
        row = _open_meeting(rows, settings) or rows[0]

    if row.cs_online and not _tracks_online(settings):
        frappe.throw(_("Online meetings don't track attendance."))

    if not row.checkin_code:
        row.checkin_code = generate_checkin_code()
        schedule_doc.save(ignore_permissions=True)
        frappe.db.commit()

    return {"checkin_code": row.checkin_code, "meeting": row.name}
