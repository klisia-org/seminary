# -*- coding: utf-8 -*-
# Course Schedule lifecycle: date resolver, scheduled jobs, event-driven
# Grading transition.
#
# State machine (see ADR 013):
#   Draft → Open for Enrollment → Enrollment Closed → Grading → Closed
#                ↓                       ↓
#            Cancelled               Cancelled (terminal)
#
# Triggers:
#   - Draft → Open: scheduled job at enrollment_open_date
#   - Open → Enrollment Closed: scheduled job at enrollment_close_date
#   - Enrollment Closed → Grading: first non-null grade (event-driven)
#   - Grading → Closed: Send Grades action only (no date)
#   - Cancelled: from Open or Enrollment Closed; terminal

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import getdate

from seminary.seminary import date_rules


WINDOWS = ("enrollment_open", "enrollment_close", "grade_close")


def resolve_window_dates(cs) -> dict:
    """Resolve enrollment_open / enrollment_close / grade_close for a Course Schedule.

    Reads the seminary-wide rule from Seminary Settings (anchor + offset days)
    and applies per-CS overrides. Per-CS override always wins. Date math runs
    through the shared `date_rules` resolver (ADR 025).

    Returns ``{"enrollment_open": date_or_None, "enrollment_close": ..., "grade_close": ...}``.
    A window is ``None`` when there is no rule and no override — the scheduler
    then ignores it for state advance, and the late-grade nag stays silent.
    """
    settings = frappe.get_cached_doc("Seminary Settings")
    context = {"anchors": _cs_anchor_dates(cs)}
    resolved = {}
    for window in WINDOWS:
        override = cs.get(f"{window}_date_override")
        if override:
            resolved[window] = getdate(override)
            continue

        anchor = settings.get(f"{window}_anchor")
        offset = settings.get(f"{window}_offset_days") or 0
        resolved[window] = date_rules.resolve(anchor, offset, "Days", context)
    return resolved


def _cs_anchor_dates(cs) -> dict:
    """The candidate anchor dates for a Course Schedule's window rules."""
    term_dates = (
        frappe.db.get_value(
            "Academic Term",
            cs.academic_term,
            ["term_start_date", "term_end_date"],
            as_dict=True,
        )
        if cs.academic_term
        else None
    ) or {}
    return {
        "term_start": term_dates.get("term_start_date"),
        "term_end": term_dates.get("term_end_date"),
        "classes_start": cs.c_datestart,
        "classes_end": cs.c_dateend,
    }


def get_default_initial_state(cs) -> str:
    """Return the workflow_state to set on a new Course Schedule.

    If a future enrollment_open_date can be resolved, land in ``Draft`` so the
    scheduler can promote the doc when the date arrives. Otherwise land
    directly in ``Open for Enrollment`` (preserves the previous default-open
    behavior when no rule is configured).
    """
    dates = resolve_window_dates(cs)
    open_date = dates.get("enrollment_open")
    if open_date and getdate(open_date) > getdate():
        return "Draft"
    return "Open for Enrollment"


# ── Event-driven trigger: first grade saved → Grading ──────────────────────


def check_and_advance_to_grading(cs_name):
    """Advance ``cs_name`` from Enrollment Closed → Grading if any non-null
    grade exists on an active, non-course-cancelled roster row.

    Called from multiple hook points (Course Assess Results Detail save,
    Scheduled Course Roster save) so the auto-advance fires regardless of
    which save path the grade came in on. Idempotent: no-op once the CS is
    already past Enrollment Closed.

    System-driven transition — bypasses ``apply_workflow`` because the user
    saving a grade is typically an Instructor without the Program Chair role
    required by the workflow's Begin Grading action.
    """
    if not cs_name:
        return

    state = frappe.db.get_value("Course Schedule", cs_name, "workflow_state")
    if state != "Enrollment Closed":
        return

    has_grade = frappe.db.sql(
        """
		SELECT 1
		FROM `tabCourse Assess Results Detail` card
		JOIN `tabScheduled Course Roster` scr ON card.parent = scr.name
		LEFT JOIN `tabCourse Enrollment Individual` cei
			ON cei.coursesc_ce = scr.course_sc
		   AND cei.student_ce = scr.student
		   AND cei.docstatus = 1
		WHERE scr.course_sc = %s
		  AND scr.active = 1
		  AND COALESCE(cei.course_cancelled, 0) = 0
		  AND (card.rawscore_card IS NOT NULL OR card.actualextrapt_card IS NOT NULL)
		LIMIT 1
		""",
        (cs_name,),
    )
    if not has_grade:
        return

    try:
        frappe.db.set_value("Course Schedule", cs_name, "workflow_state", "Grading")
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"CS auto-advance to Grading failed: {cs_name}",
        )


def maybe_advance_to_grading(doc, method=None):
    """Hook on Course Assess Results Detail on_update."""
    if doc.rawscore_card is None and doc.actualextrapt_card is None:
        return
    course_sc = frappe.db.get_value("Scheduled Course Roster", doc.parent, "course_sc")
    check_and_advance_to_grading(course_sc)


def maybe_advance_to_grading_from_roster(doc, method=None):
    """Hook on Scheduled Course Roster on_update.

    Covers the case where grades are entered via the SCR form (saving the
    parent doesn't fire child rows' on_update, so the CARD-side hook would
    miss). The helper short-circuits cheaply when the CS isn't in Enrollment
    Closed, so the cost of running this on every SCR save is one indexed
    lookup.
    """
    check_and_advance_to_grading(getattr(doc, "course_sc", None))


# ── Scheduled jobs ──────────────────────────────────────────────────────────


def advance_due_course_schedules(today=None):
    """Daily job: advance Draft→Open and Open→Enrollment Closed by date.

    Per-row try/except so one bad row doesn't stop the rest. Idempotent:
    re-runs are safe (filtered query only picks up due rows still in the
    source state).
    """
    today = getdate(today) if today else getdate()

    for name in frappe.get_all(
        "Course Schedule",
        filters={
            "workflow_state": "Draft",
            "enrollment_open_date": ["<=", today],
        },
        pluck="name",
    ):
        try:
            apply_workflow(frappe.get_doc("Course Schedule", name), "Open Enrollment")
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"CS Draft→Open failed: {name}")

    for name in frappe.get_all(
        "Course Schedule",
        filters={
            "workflow_state": "Open for Enrollment",
            "enrollment_close_date": ["<=", today],
        },
        pluck="name",
    ):
        try:
            apply_workflow(frappe.get_doc("Course Schedule", name), "Close Enrollment")
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"CS Open→Closed failed: {name}")


def nag_late_graders(today=None):
    """Daily job: nag instructors when a course in Grading is past its
    grade_close_date, through the Communication Log (ADR 043). One nag per
    course (idempotent via late_grade_nag_sent); registrars get their own copy
    instead of a CC so it lands on their timelines too.
    """
    from seminary.seminary import comms

    today = getdate(today) if today else getdate()

    overdue = frappe.get_all(
        "Course Schedule",
        filters={
            "workflow_state": ["in", ["Enrollment Closed", "Grading"]],
            "grade_close_date": ["<", today],
            "late_grade_nag_sent": 0,
        },
        fields=["name", "title", "academic_term", "grade_close_date"],
    )
    if not overdue:
        return

    for cs in overdue:
        try:
            instructors = _instructor_persons_for_cs(cs.name)
            if not instructors:
                frappe.log_error(
                    f"No instructor on file for {cs.name}; nag skipped.",
                    "Late-grade nag: missing instructor",
                )
                continue
            context = {
                "course": cs.title,
                "term": cs.academic_term,
                "due": cs.grade_close_date,
                "days": (today - getdate(cs.grade_close_date)).days,
            }
            for person in instructors:
                comms.send(
                    person,
                    "late-grades-nag",
                    context=context,
                    reference_doctype="Course Schedule",
                    reference_name=cs.name,
                    triggered_by="late-grades-nag",
                )
            comms.send_to_role(
                "Registrar",
                "late-grades-nag",
                context=context,
                reference_doctype="Course Schedule",
                reference_name=cs.name,
                triggered_by="late-grades-nag",
            )
            frappe.db.set_value("Course Schedule", cs.name, "late_grade_nag_sent", 1)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"Late-grade nag failed: {cs.name}"
            )


def _instructor_persons_for_cs(cs_name) -> list:
    return frappe.db.sql_list(
        """
		SELECT DISTINCT i.person
		FROM `tabCourse Schedule Instructors` csi
		JOIN `tabInstructor` i ON csi.instructor = i.name
		WHERE csi.parent = %s AND IFNULL(i.person, '') != ''
		""",
        (cs_name,),
    )


def _instructor_emails_for_cs(cs_name) -> list:
    rows = frappe.db.sql(
        """
		SELECT DISTINCT i.prof_email
		FROM `tabCourse Schedule Instructors` csi
		JOIN `tabInstructor` i ON csi.instructor = i.name
		WHERE csi.parent = %s AND IFNULL(i.prof_email, '') != ''
		""",
        (cs_name,),
        as_dict=True,
    )
    return [r.prof_email for r in rows]


def _registrar_emails() -> list:
    rows = frappe.db.sql(
        """
		SELECT DISTINCT u.email
		FROM `tabHas Role` r
		JOIN `tabUser` u ON r.parent = u.name
		WHERE r.role = 'Registrar'
		  AND u.enabled = 1
		  AND IFNULL(u.email, '') != ''
		""",
        as_dict=True,
    )
    return [r.email for r in rows]
