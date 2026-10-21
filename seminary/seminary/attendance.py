# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Attendance standing: per-student absence tally, limit, and alerting.

Attendance is captured as Student Attendance rows (Present/Tardy/Absent). This
module turns that into a *standing* on each Scheduled Course Roster row:

* **effective absences** = recorded absences (none on a leave-of-absence day;
  Excused is not an absence — ADR 081) +
  ``tardies // tardies_per_absence`` (Seminary Settings; 0 disables conversion).
* **absence limit** (per student): the course's policy resolved against the
  *student's* program — a course has no single program (a course can serve
  several), so the Auto limit = ``round(program.default_max_absence_percent% ×
  scheduled meetings)``; Custom applies a fixed number to everyone; Disabled and
  Virtual(+Auto) mean no limit (0).
* **alert level** 0/1/2 (ok / within the warning band / over the limit), which
  drives once-per-crossing Notification Logs to instructor + registrar/Program
  Chair + student.

Enforcement is flag-and-notify only — grades are never changed automatically.
Standing is recomputed on every Student Attendance change (doc_events), on
Course Schedule save (limit may move when meeting dates are added), and by a
daily backstop. See ADR 037.
"""

import frappe
from frappe import _
from frappe.utils import getdate
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs

from seminary.seminary.guards import require_course_staff

POLICY_AUTO = "Auto (from program)"
POLICY_CUSTOM = "Custom"
POLICY_DISABLED = "Disabled"

# Roles allowed to set the per-course attendance policy (controller-enforced,
# mirroring cancel_course / import_template in course_schedule.py).
POLICY_EDIT_ROLES = {"Registrar", "Program Chair", "Seminary Manager", "System Manager"}

ALERT_NONE, ALERT_DANGER, ALERT_OVER = 0, 1, 2


# ---------------------------------------------------------------------------
# Limit resolution
# ---------------------------------------------------------------------------


def _tracks_online_attendance():
    """Whether online meetings are attendance-bearing (ADR 051). Defaults to
    True when the setting is absent (pre-migration / unset)."""
    val = frappe.db.get_single_value("Seminary Settings", "track_online_attendance")
    return val is None or bool(val)


def _cs_meta(course_schedule, cs=None):
    """Policy inputs for a Course Schedule (from a loaded doc when available)."""
    track_online = _tracks_online_attendance()
    if cs is not None:
        rows = cs.get("cs_meetinfo") or []
        total = len([r for r in rows if track_online or not r.get("cs_online")])
        return {
            "policy": cs.get("attendance_policy") or POLICY_AUTO,
            "custom": cs.get("max_absences_custom"),
            "modality": cs.get("modality"),
            "total": total,
        }
    row = (
        frappe.db.get_value(
            "Course Schedule",
            course_schedule,
            ["attendance_policy", "max_absences_custom", "modality"],
            as_dict=True,
        )
        or frappe._dict()
    )
    meeting_filters = {"parent": course_schedule}
    if not track_online:
        meeting_filters["cs_online"] = 0
    return {
        "policy": row.attendance_policy or POLICY_AUTO,
        "custom": row.max_absences_custom,
        "modality": row.modality,
        "total": frappe.db.count("Course Schedule Meeting Dates", meeting_filters),
    }


def _absence_limit(meta, program):
    """Allowed absences for a student in this course (0 = no limit)."""
    policy = meta["policy"]
    if policy == POLICY_DISABLED:
        return 0
    if policy == POLICY_CUSTOM:
        return max(0, int(meta["custom"] or 0))
    # Auto — disabled for Virtual; otherwise % of scheduled meetings.
    if (meta["modality"] or "") == "Virtual" or not meta["total"]:
        return 0
    pct = (
        float(
            frappe.db.get_value("Program", program, "default_max_absence_percent") or 0
        )
        if program
        else 0
    )
    if pct <= 0:
        return 0
    return round(pct / 100.0 * meta["total"])


def compute_max_absences(cs):
    """Convenience for staff display: the Auto/Custom limit ignoring per-student
    program (Auto here can't resolve a program, so returns the Custom value or 0).
    The authoritative per-student value is `absence_limit` on the roster."""
    meta = _cs_meta(cs.name, cs)
    if meta["policy"] == POLICY_CUSTOM:
        return max(0, int(meta["custom"] or 0))
    return 0


# ---------------------------------------------------------------------------
# Tally
# ---------------------------------------------------------------------------


def leave_periods(student, program):
    """Leave-of-absence periods for a student's enrollment in ``program``, read
    from Program Enrollment Status History (ADR 081). Each is ``(start, end)``
    with ``end`` exclusive (the return date) or ``None`` while still on leave.
    Nothing is copied when a leave changes, so extensions and early returns are
    always reflected."""
    from seminary.seminary.program_status import LEAVE_STATUS

    if not (student and program):
        return []
    pes = frappe.get_all(
        "Program Enrollment",
        filters={"student": student, "program": program, "docstatus": 1},
        pluck="name",
    )
    if not pes:
        return []
    rows = frappe.get_all(
        "Program Enrollment Status History",
        filters={"parent": ["in", pes], "parentfield": "status_history"},
        fields=["effective_date", "to_status"],
        order_by="effective_date asc, idx asc",
    )
    periods, start = [], None
    for r in rows:
        if not r.effective_date:
            continue
        if r.to_status == LEAVE_STATUS:
            start = start or getdate(r.effective_date)
        elif start:
            periods.append((start, getdate(r.effective_date)))
            start = None
    if start:
        periods.append((start, None))
    return periods


def on_leave(date, periods):
    date = getdate(date)
    return any(s <= date and (e is None or date < e) for s, e in periods)


def _counts(student, course_schedule, program=None):
    """(absences, tardies) for a student in a course. Excused rows count as
    neither, and an absence on a leave-of-absence day is not counted (ADR 081)."""
    # When online meetings aren't attendance-bearing, ignore any attendance rows
    # tied to an online meeting (e.g. recorded before the policy was turned off).
    online_clause = (
        ""
        if _tracks_online_attendance()
        else (
            "AND NOT EXISTS (SELECT 1 FROM `tabCourse Schedule Meeting Dates` m "
            "WHERE m.name = sa.meeting AND m.cs_online = 1)"
        )
    )
    rows = frappe.db.sql(
        f"""
        SELECT sa.status, sa.date
        FROM `tabStudent Attendance` sa
        WHERE sa.student = %s AND sa.course_schedule = %s AND sa.docstatus < 2
        {online_clause}
        """,  # nosec B608 -- interpolates a clause built from constants in this function
        (student, course_schedule),
        as_dict=True,
    )
    periods = leave_periods(student, program)
    absences = tardies = 0
    for r in rows:
        if r.status == "Absent":
            if r.date and periods and on_leave(r.date, periods):
                continue
            absences += 1
        elif r.status == "Tardy":
            tardies += 1
    return absences, tardies


def _effective(absences, tardies, settings):
    per = int(settings.tardies_per_absence or 0)
    return absences + (tardies // per if per > 0 else 0)


def _level(effective, limit, buffer):
    if limit <= 0:
        return ALERT_NONE
    if effective > limit:
        return ALERT_OVER
    if effective > 0 and effective >= limit - max(0, int(buffer or 0)):
        return ALERT_DANGER
    return ALERT_NONE


# ---------------------------------------------------------------------------
# Recompute
# ---------------------------------------------------------------------------


def recompute_standing(course_schedule, student, cs=None, settings=None, notify=True):
    """Recompute one student's attendance standing on their roster row and fire
    a notification when the alert level rises (once per crossing)."""
    if not course_schedule or not student:
        return
    roster = frappe.db.get_value(
        "Scheduled Course Roster",
        {"course_sc": course_schedule, "student": student},
        [
            "name",
            "active",
            "audit_bool",
            "program_std_scr",
            "stuname_roster",
            "attendance_alert_level",
        ],
        as_dict=True,
    )
    if not roster:
        return

    settings = settings or frappe.get_cached_doc("Seminary Settings")

    if roster.audit_bool or not roster.active:
        # Auditors / inactive enrollments are never flagged.
        absences = tardies = effective = limit = 0
        new_level = ALERT_NONE
    else:
        limit = _absence_limit(_cs_meta(course_schedule, cs), roster.program_std_scr)
        absences, tardies = _counts(student, course_schedule, roster.program_std_scr)
        effective = _effective(absences, tardies, settings)
        new_level = _level(effective, limit, settings.absence_warning_buffer)

    # Direct DB write — no roster on_update hook (avoids the grading-advance
    # hook) and no modified-timestamp churn.
    frappe.db.set_value(
        "Scheduled Course Roster",
        roster.name,
        {
            "absence_count": absences,
            "tardy_count": tardies,
            "effective_absences": effective,
            "absence_limit": limit,
            "attendance_alert_level": new_level,
        },
        update_modified=False,
    )

    if (
        notify
        and new_level > int(roster.attendance_alert_level or 0)
        and new_level >= ALERT_DANGER
    ):
        _notify(course_schedule, student, roster, new_level, effective, limit)


def recompute_for_attendance(doc, method=None):
    """doc_events hook on Student Attendance (after_insert / on_update / on_trash)."""
    recompute_standing(doc.get("course_schedule"), doc.get("student"))


def recompute_for_course_schedule(course_schedule):
    """Re-level every active, non-audit roster of a course (e.g. after the
    instructor adds meeting dates, which moves the Auto limit)."""
    settings = frappe.get_cached_doc("Seminary Settings")
    cs = frappe.get_doc("Course Schedule", course_schedule)
    for student in frappe.get_all(
        "Scheduled Course Roster",
        filters={"course_sc": course_schedule, "active": 1, "audit_bool": 0},
        pluck="student",
    ):
        recompute_standing(course_schedule, student, cs=cs, settings=settings)


def recompute_for_program(program):
    """Re-level standings for every course a student of this program is on
    (used when the program's max absence % changes — the Auto limit moves)."""
    for cs_name in set(
        filter(
            None,
            frappe.get_all(
                "Scheduled Course Roster",
                filters={"program_std_scr": program, "active": 1, "audit_bool": 0},
                pluck="course_sc",
                distinct=True,
            ),
        )
    ):
        recompute_for_course_schedule(cs_name)


def recompute_on_program_update(doc, method=None):
    """doc_events hook on Program: re-level affected rosters when the default
    max absence % changes, so the registrar sees the effect immediately."""
    if doc.has_value_changed("default_max_absence_percent"):
        recompute_for_program(doc.name)


def recompute_for_enrollment(program_enrollment):
    """Re-level a student's active courses in a program, e.g. when a leave of
    absence starts or ends (ADR 081)."""
    student, program = frappe.db.get_value(
        "Program Enrollment", program_enrollment, ["student", "program"]
    ) or (None, None)
    if not (student and program):
        return
    for cs_name in frappe.get_all(
        "Scheduled Course Roster",
        filters={"student": student, "program_std_scr": program, "active": 1},
        pluck="course_sc",
    ):
        recompute_standing(cs_name, student)


def recompute_all():
    """Daily backstop — re-level standings across all active rosters."""
    for cs_name in set(
        filter(
            None,
            frappe.get_all(
                "Scheduled Course Roster",
                filters={"active": 1, "audit_bool": 0},
                pluck="course_sc",
                distinct=True,
            ),
        )
    ):
        try:
            recompute_for_course_schedule(cs_name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"attendance.recompute_all: {cs_name}"
            )


# ---------------------------------------------------------------------------
# Notifications (once per rising crossing)
# ---------------------------------------------------------------------------


def _role_users(roles):
    users = set(
        frappe.get_all(
            "Has Role",
            filters={"role": ["in", roles], "parenttype": "User"},
            pluck="parent",
        )
    )
    if not users:
        return set()
    enabled = set(
        frappe.get_all(
            "User", filters={"name": ["in", list(users)], "enabled": 1}, pluck="name"
        )
    )
    enabled.discard("Administrator")
    enabled.discard("Guest")
    return enabled


def _send(subject, content, document_type, document_name, users):
    users = [u for u in users if u]
    if not users:
        return
    # make_notification_logs reads `doc.type` (attribute access) — it must be a
    # frappe._dict, not a plain dict, or it raises AttributeError when a
    # recipient equals from_user (the `for_user == from_user` short-circuit
    # falls through to `doc.type`).
    make_notification_logs(
        frappe._dict(
            type="Alert",
            document_type=document_type,
            document_name=document_name,
            subject=subject,
            email_content=content,
            from_user=frappe.session.user or "Administrator",
        ),
        users,
    )


def _notify(course_schedule, student, roster, level, effective, limit):
    title = (
        frappe.db.get_value("Course Schedule", course_schedule, "title")
        or course_schedule
    )
    name = roster.stuname_roster or student

    if level >= ALERT_OVER:
        subject = _("Attendance limit exceeded: {0}").format(title)
        staff_body = _(
            "{0} has {1} effective absences in {2}, over the limit of {3}."
        ).format(name, effective, title, limit)
        student_body = _(
            "You have {0} absences in {1}, over the allowed {2}. "
            "Please contact your instructor or the registrar."
        ).format(effective, title, limit)
    else:
        subject = _("Attendance warning: {0}").format(title)
        staff_body = _(
            "{0} has {1} of {2} absences in {3} — approaching the limit."
        ).format(name, effective, limit, title)
        student_body = _(
            "You have {0} of {1} allowed absences in {2}. "
            "Further absences may put your standing at risk."
        ).format(effective, limit, title)

    # Instructor(s) + registrar / Program Chair → Course Schedule.
    staff = set()
    for instr in frappe.get_all(
        "Course Schedule Instructors", {"parent": course_schedule}, pluck="instructor"
    ):
        u = frappe.db.get_value("Instructor", instr, "user")
        if u:
            staff.add(u)
    staff |= _role_users(["Registrar", "Program Chair"])
    _send(subject, staff_body, "Course Schedule", course_schedule, staff)

    # Student → their roster row.
    student_user = frappe.db.get_value("Student", student, "user")
    if student_user:
        _send(
            subject,
            student_body,
            "Scheduled Course Roster",
            roster.name,
            {student_user},
        )


# ---------------------------------------------------------------------------
# Policy edit guard + instructor-facing standings
# ---------------------------------------------------------------------------


def assert_can_edit_policy():
    if not (POLICY_EDIT_ROLES & set(frappe.get_roles(frappe.session.user))):
        frappe.throw(
            _("Only the registrar or Program Chair can change the attendance policy."),
            frappe.PermissionError,
        )


@frappe.whitelist()
def get_course_attendance_standings(course_schedule):
    """Per-student attendance standing for the instructor attendance page,
    keyed by student id. Empty unless an absence limit is in force.

    Course staff only. The read below is ``frappe.get_all``, which is
    ``get_list(ignore_permissions=True)``, so ``query_scheduled_course_roster``
    (p007 F2) never runs on it — without this gate any authenticated user could
    read who is one absence from failing out, for any section in the school
    (p005a A01-18). The registrar is included because attendance standing is a
    registrar concern as much as an instructor one.
    """
    require_course_staff(course_schedule, include_registrar=True)
    rows = frappe.get_all(
        "Scheduled Course Roster",
        filters={"course_sc": course_schedule, "active": 1, "audit_bool": 0},
        fields=[
            "student",
            "absence_count",
            "tardy_count",
            "effective_absences",
            "absence_limit",
            "attendance_alert_level",
            "program_std_scr",
        ],
    )
    # Leave periods let the page show "On leave" on the meeting being taken.
    for r in rows:
        r["leave_periods"] = [
            [str(s), str(e) if e else None]
            for s, e in leave_periods(r.student, r.pop("program_std_scr"))
        ]
    return {r.student: r for r in rows}
