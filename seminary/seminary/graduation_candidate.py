# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Graduation candidacy evaluator.

Computes whether a Program Enrollment has reached the final-courses
condition that makes its student eligible to file a Graduation Request.
The trigger is configured per Program (`graduation_request_trigger`):

- "Enrolled in final courses": candidate when remaining mandatory +
  emphasis-mandatory courses are 0 *counting in-progress courses*, and
  remaining credits <= in-progress credits.
- "Passed final courses":      candidate when the same conditions hold
  *counting only completed courses*.

The evaluator is idempotent and bidirectional — it always recomputes from
current PEC + CEI state and overwrites `grad_candidate`. A withdrawal
that drops the student below requirements flips the flag back to 0
without any special unset path.

Persisted via `frappe.db.set_value(..., update_modified=False)` to avoid
touching the PE's modified timestamp on read-driven recomputation.
"""

import frappe
from frappe.model.document import Document


def evaluate_candidacy(pe_name: str) -> bool:
    """Recompute and persist `grad_candidate` for one Program Enrollment.
    Returns the new value. Safe to call multiple times.
    """
    pe = frappe.db.get_value(
        "Program Enrollment",
        pe_name,
        [
            "name",
            "program",
            "docstatus",
            "pgmenrol_active",
            "totalcredits",
            "grad_candidate",
        ],
        as_dict=True,
    )
    if not pe:
        return False

    new_value = _compute(pe)
    if new_value != bool(pe.grad_candidate):
        frappe.db.set_value(
            "Program Enrollment",
            pe.name,
            "grad_candidate",
            int(new_value),
            update_modified=False,
        )
    return new_value


def evaluate_candidacy_safe(pe_name: str) -> bool:
    """Same as evaluate_candidacy but swallows + logs any exception.

    Use at hook callsites where a candidacy bug must never block the
    primary operation (course enrollment, withdrawal, grade entry).
    """
    try:
        return evaluate_candidacy(pe_name)
    except Exception:
        frappe.log_error(
            title="Graduation candidacy evaluation failed",
            message=frappe.get_traceback(),
        )
        return False


def recompute_for_program(program: str) -> int:
    """Re-evaluate every active PE on a program. Returns count flipped.

    Bench-callable for backfill or after changing a program's trigger.
    """
    pe_names = frappe.get_all(
        "Program Enrollment",
        filters={"program": program, "docstatus": 1, "pgmenrol_active": 1},
        pluck="name",
    )
    flipped = 0
    for name in pe_names:
        before = frappe.db.get_value("Program Enrollment", name, "grad_candidate")
        after = evaluate_candidacy(name)
        if bool(before) != after:
            flipped += 1
    return flipped


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _compute(pe) -> bool:
    """Pure computation — returns True/False without persisting."""
    if pe.docstatus != 1 or not pe.pgmenrol_active:
        return False

    program = frappe.get_cached_doc("Program", pe.program)
    if program.is_ongoing:
        return False
    if not program.students_can_request_graduation:
        return False
    if not program.graduation_request_trigger:
        return False

    completed, in_progress = _course_status_sets(pe.name)
    mandatory_program = _mandatory_program_courses(program)
    mandatory_emphasis = _mandatory_emphasis_courses(pe, program)
    in_progress_credits = _credit_sum(program, in_progress)

    count_in_progress = (
        program.graduation_request_trigger == "Enrolled in final courses"
    )
    satisfied = completed | (in_progress if count_in_progress else set())

    if mandatory_program - satisfied:
        return False
    if mandatory_emphasis - satisfied:
        return False

    completed_credits = pe.totalcredits or 0
    credits_required = program.credits_complete or 0
    if program.program_type == "Credits-based":
        available = completed_credits + (
            in_progress_credits if count_in_progress else 0
        )
        if available < credits_required:
            return False

    if _has_pending_blocker(pe.name):
        return False

    return True


def _has_pending_blocker(pe_name: str) -> bool:
    """True iff at least one mandatory SGR row marked
    `blocks_graduation_request` is not yet Fulfilled or Waived.
    """
    rows = frappe.get_all(
        "Student Graduation Requirement",
        filters={
            "parent": pe_name,
            "parenttype": "Program Enrollment",
            "blocks_graduation_request": 1,
            "mandatory": 1,
            "status": ("not in", ("Fulfilled", "Waived")),
        },
        limit=1,
    )
    return bool(rows)


def _course_status_sets(pe_name: str):
    """Return (completed, in_progress) sets of course names for the PE."""
    completed = set(
        frappe.get_all(
            "Program Enrollment Course",
            filters={"parent": pe_name, "status": "Pass"},
            pluck="course_name",
        )
    )

    in_progress = set(
        frappe.get_all(
            "Course Enrollment Individual",
            filters={
                "program_ce": pe_name,
                "docstatus": 1,
                "withdrawn": 0,
                "course_cancelled": 0,
                "workflow_state": "Submitted",
            },
            pluck="course_data",
        )
    )
    # A course can appear in both sets if a final grade lands while a CEI
    # row is still flagged Submitted; treat completed as authoritative.
    in_progress -= completed
    return completed, in_progress


def _mandatory_program_courses(program: Document) -> set:
    return {pc.course for pc in program.courses if pc.required}


def _mandatory_emphasis_courses(pe, program: Document) -> set:
    """Mandatory courses across the student's active emphasis tracks."""
    active_tracks = (
        [
            e.emphasis_track
            for e in (pe.emphases or [])
            if e.status in ("Active", "Completed")
        ]
        if hasattr(pe, "emphases")
        else []
    )

    if not active_tracks:
        # pe came from db.get_value (no child tables loaded) — fetch directly
        active_tracks = frappe.get_all(
            "Program Enrollment Emphasis",
            filters={
                "parent": pe.name,
                "status": ("in", ("Active", "Completed")),
            },
            pluck="emphasis_track",
        )

    if not active_tracks:
        return set()

    rows = frappe.get_all(
        "Program Track Courses",
        filters={
            "parent": program.name,
            "program_track": ("in", active_tracks),
            "pgm_track_course_mandatory": 1,
        },
        pluck="program_track_course",
    )
    return set(rows)


def _credit_sum(program: Document, course_names: set) -> float:
    if not course_names:
        return 0
    total = 0
    for pc in program.courses:
        if pc.course in course_names:
            total += pc.pgmcourse_credits or 0
    return total
