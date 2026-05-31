# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Chapel attendance: student self check-in + count-based graduation fulfilment.

Chapel is a public, recurring Event (all students/instructors invited). A
graduation requirement of type "Chapel Attendance" is *count-based* ("attend N
chapels"), unlike ADR 028's single-occurrence "Event Attendance". Students self
check-in from the portal; each check-in is a Chapel Attendance record, and the
running count is reflected onto the student's Chapel Attendance Student
Graduation Requirement (SGR) rows. Kept separate from events.py on purpose.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime, today

from seminary.seminary.utils import get_current_student

SGR_DOCTYPE = "Student Graduation Requirement"
CHAPEL_REQUIREMENT_TYPE = "Chapel Attendance"


# ---------------------------------------------------------------------------
# Check-in window / code
# ---------------------------------------------------------------------------


def _checkin_bounds(chapel_doc, settings):
    """(open_dt, close_dt) for self check-in, or None when the window is
    disabled (both settings 0 → check-in allowed any time)."""
    before = int(settings.chapel_checkin_opens_before_mins or 0)
    after = int(settings.chapel_checkin_closes_after_mins or 0)
    if before == 0 and after == 0:
        return None
    start = get_datetime(chapel_doc.starts_on)
    end = get_datetime(chapel_doc.ends_on) if chapel_doc.get("ends_on") else start
    return add_to_date(start, minutes=-before), add_to_date(end, minutes=after)


def _is_open_now(chapel_doc, settings, now=None):
    bounds = _checkin_bounds(chapel_doc, settings)
    if bounds is None:
        return True
    now = now or now_datetime()
    return bounds[0] <= now <= bounds[1]


def _validate_window(chapel_doc, settings):
    if not _is_open_now(chapel_doc, settings):
        frappe.throw(_("Check-in for this chapel is not open right now."))


def _validate_code(chapel_doc, settings, code):
    if not settings.require_chapel_checkin_code:
        return
    expected = (chapel_doc.checkin_code or "").strip().upper()
    given = (code or "").strip().upper()
    if not expected or given != expected:
        frappe.throw(_("Incorrect or missing check-in code."))


# ---------------------------------------------------------------------------
# Student self check-in (portal)
# ---------------------------------------------------------------------------


def _active_enrollment(student):
    """A submitted Program Enrollment for this student, preferring one that
    carries a Chapel Attendance requirement. Informational on the record;
    fulfilment recomputes across all enrollments regardless."""
    with_req = frappe.db.sql(
        """
        SELECT pe.name
        FROM `tabProgram Enrollment` pe
        JOIN `tabStudent Graduation Requirement` sgr ON sgr.parent = pe.name
        WHERE pe.student = %(student)s AND pe.docstatus = 1
          AND sgr.parenttype = 'Program Enrollment'
          AND sgr.requirement_type = %(t)s
        ORDER BY pe.creation DESC
        LIMIT 1
        """,
        {"student": student, "t": CHAPEL_REQUIREMENT_TYPE},
    )
    if with_req:
        return with_req[0][0]
    return frappe.db.get_value(
        "Program Enrollment", {"student": student, "docstatus": 1}, "name"
    )


@frappe.whitelist()
def check_in(chapel, code=None):
    """Student self check-in to a chapel. Validates the chapel is confirmed,
    the check-in window (unless disabled), and the code (if required); rejects
    duplicates. Returns the student's updated Chapel Attendance progress."""
    student = get_current_student()
    if not student:
        frappe.throw(
            _("Only enrolled students can check in to chapel."), frappe.PermissionError
        )

    chapel_doc = frappe.get_doc("Chapel", chapel)
    if not chapel_doc.confirmed:
        frappe.throw(_("This chapel is not open for check-in yet."))

    settings = frappe.get_cached_doc("Seminary Settings")
    _validate_window(chapel_doc, settings)
    _validate_code(chapel_doc, settings, code)

    if frappe.db.exists(
        "Chapel Attendance", {"chapel": chapel, "student": student.name}
    ):
        frappe.throw(_("You have already checked in to this chapel."))

    frappe.get_doc(
        {
            "doctype": "Chapel Attendance",
            "chapel": chapel,
            "student": student.name,
            "program_enrollment": _active_enrollment(student.name),
            "check_in_time": now_datetime(),
        }
    ).insert(ignore_permissions=True)

    return _student_progress(student.name)


@frappe.whitelist()
def get_chapel_status():
    """Portal feed: recent confirmed chapels (with open-for-check-in / already-
    checked-in flags) plus the student's Chapel Attendance requirement progress."""
    student = get_current_student()
    if not student:
        return {"chapels": [], "requires_code": False, "progress": []}

    settings = frappe.get_cached_doc("Seminary Settings")
    now = now_datetime()
    checked_in = set(
        frappe.get_all(
            "Chapel Attendance", filters={"student": student.name}, pluck="chapel"
        )
    )
    requires_code = bool(settings.require_chapel_checkin_code)

    chapels = []
    for c in frappe.get_all(
        "Chapel",
        filters={"confirmed": 1},
        fields=["name", "chapel_topic", "starts_on", "ends_on", "room"],
        order_by="starts_on desc",
        limit=20,
    ):
        chapels.append(
            {
                **c,
                "open_for_checkin": _is_open_now(frappe._dict(c), settings, now),
                "already_checked_in": c.name in checked_in,
            }
        )

    return {
        "chapels": chapels,
        "requires_code": requires_code,
        "progress": _student_progress(student.name),
    }


def _student_progress(student):
    return frappe.db.sql(
        """
        SELECT sgr.name AS sgr_name, sgr.requirement_name, sgr.status,
               sgr.required_count, sgr.attended_count,
               pe.name AS program_enrollment, pe.program
        FROM `tabStudent Graduation Requirement` sgr
        JOIN `tabProgram Enrollment` pe ON pe.name = sgr.parent
        WHERE sgr.parenttype = 'Program Enrollment'
          AND sgr.requirement_type = %(t)s
          AND pe.student = %(student)s AND pe.docstatus = 1
        ORDER BY pe.name
        """,
        {"student": student, "t": CHAPEL_REQUIREMENT_TYPE},
        as_dict=True,
    )


# ---------------------------------------------------------------------------
# Count-based fulfilment (hooked on Chapel Attendance after_insert / on_trash)
# ---------------------------------------------------------------------------


def reflect_attendance(doc, method=None):
    """`after_insert` / `on_trash` hook on Chapel Attendance. Recompute the
    student's Chapel Attendance requirement progress."""
    if doc.get("student"):
        recompute_for_student(doc.student)


def recompute_for_student(student):
    """For each submitted enrollment of this student carrying a Chapel
    Attendance requirement: count the student's check-ins (since the enrollment
    date) and reflect it onto the SGR row's attended_count + status. Fully
    count-driven — Waived rows are left untouched; manual overrides on this type
    are reconciled on the next check-in."""
    enrollments = frappe.get_all(
        "Program Enrollment", filters={"student": student, "docstatus": 1}, pluck="name"
    )
    for pe_name in enrollments:
        pe = frappe.get_doc("Program Enrollment", pe_name)
        chapel_rows = [
            r
            for r in (pe.graduation_requirements or [])
            if r.requirement_type == CHAPEL_REQUIREMENT_TYPE
        ]
        if not chapel_rows:
            continue

        attendance_filters = {"student": student}
        if pe.enrollment_date:
            attendance_filters["check_in_time"] = (">=", pe.enrollment_date)
        count = frappe.db.count("Chapel Attendance", attendance_filters)

        changed = False
        for row in chapel_rows:
            if row.waived or row.status == "Waived":
                continue
            required = row.required_count or 1
            new_status = (
                "Fulfilled"
                if count >= required
                else ("In Progress" if count > 0 else "Not Started")
            )
            new_fulfilled_on = today() if new_status == "Fulfilled" else None
            if (
                row.attended_count != count
                or row.status != new_status
                or row.fulfilled_on != new_fulfilled_on
            ):
                row.attended_count = count
                row.status = new_status
                row.fulfilled_on = new_fulfilled_on
                changed = True

        if changed:
            pe.save(ignore_permissions=True)
