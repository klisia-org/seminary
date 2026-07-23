"""Auto-enroll cohort members into a Cohort Type's backing course (Phase 7).

When a membership becomes active in a cohort whose type sets a `course` and
`auto_enroll_on_join`, the member's active Program Enrollment is enrolled into
that course by reusing `api.course_enroll` — the same primitive culminating
projects and required-enrollment use. Billing then rides the Course Enrollment
Individual's own `on_submit` → FinancialBackend (ADR 063); this module never
names a billing doctype. Members without an active Program Enrollment (e.g.
invited pastors) are skipped.
"""

import frappe


def maybe_auto_enroll(membership):
    """Idempotent: link/create the backing-course CEI for an active membership."""
    if not membership.active or membership.course_enrollment:
        return
    ct_name = frappe.db.get_value("Cohort", membership.cohort, "cohort_type")
    if not ct_name:
        return
    ct = frappe.get_cached_doc("Cohort Type", ct_name)
    if not (ct.course and ct.auto_enroll_on_join):
        return

    pe = _member_active_pe(membership.person, ct.program)
    if not pe:
        return  # non-enrolled member (e.g. a pastor) — nothing to bill

    # Already has a live enrollment for this course? Just record the tie.
    existing = _live_cei(pe.name, ct.course)
    if existing:
        membership.db_set("course_enrollment", existing, update_modified=False)
        return

    from seminary.seminary.api import course_enroll
    from seminary.seminary.required_enrollment import _open_offerings, _pick_offering

    cs_name = _pick_offering(_open_offerings(ct.course), pe.academic_term)
    if not cs_name:
        return  # no open offering yet — nothing to enroll into

    try:
        result = course_enroll(pe.name, cs_name)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"cohort auto-enroll failed (membership={membership.name}, course={ct.course})",
        )
        return

    cei = (result or {}).get("name")
    if cei:
        membership.db_set("course_enrollment", cei, update_modified=False)


def _member_active_pe(person, program=None):
    """The member's active Program Enrollment (optionally within the type's
    program), resolved Person → Student → Program Enrollment."""
    student = frappe.db.get_value("Student", {"person": person}, "name")
    if not student:
        return None
    filters = {"student": student, "pgmenrol_active": 1, "docstatus": 1}
    if program:
        filters["program"] = program
    pe_name = frappe.db.get_value("Program Enrollment", filters, "name")
    if not pe_name:
        return None
    return frappe.db.get_value(
        "Program Enrollment", pe_name, ["name", "academic_term"], as_dict=True
    )


def _live_cei(pe_name, course):
    return frappe.db.get_value(
        "Course Enrollment Individual",
        {
            "program_ce": pe_name,
            "course_data": course,
            "docstatus": ["!=", 2],
            "withdrawn": 0,
            "course_cancelled": 0,
        },
        "name",
    )
