# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

"""Deferred auto-enrollment for mandatory-on-enrollment program courses.

A Program Course row flagged ``pgm_course_reqonenroll`` ("Mandatory on program
enrollment") means the student should be auto-enrolled into that course. But
enrollment needs a Course Schedule (a concrete offering in an Academic Term),
which may not exist in the student's enrollment term — so fulfillment is
deferred until an offering opens.

Design (ADR 035):
- The *set* of required courses is snapshotted onto the Program Enrollment at
  submit (``required_on_enroll_courses``) by the PE controller. This module
  matches against that frozen snapshot, NOT the live Program flag, so toggling
  the flag later never touches already-enrolled students.
- Fulfillment *status* is computed on the fly from CEI/PEC (no status queue).
- The single enrollment primitive is ``api.course_enroll``; roster/PEC rows are
  its downstream side effects and are never hand-rolled here.

Two seams (registered in hooks.py):
- Program Enrollment ``on_submit`` -> ``fulfill_for_program_enrollment_hook``
  (forward: enroll into anything already open).
- Course Schedule ``on_update`` / ``after_insert`` ->
  ``on_course_schedule_update`` / ``on_course_schedule_insert`` (deferred: when
  an offering opens, back-enroll the students who still owe it). Course Schedule
  is not submittable, so ``on_update_after_submit`` is unavailable.

Plus ``reconcile_required_enrollments`` — an explicit, append-only backfill run
from the Program form button or bench (never automatic).
"""

import frappe
from frappe import _
from frappe.utils import getdate


# ---------------------------------------------------------------------------
# Seam (a): Program Enrollment on_submit
# ---------------------------------------------------------------------------


def fulfill_for_program_enrollment_hook(doc, method=None):
    """PE on_submit hook. Runs after api.get_payers (hooks.py ordering) so any
    auto-created CEI can invoice against a populated fee structure."""
    # Trust the freshly-submitted in-memory doc for the active check; the DB
    # row's derived pgmenrol_active mirror is reliably defaulted to 1 on a new
    # Active enrollment.
    if not doc.pgmenrol_active:
        return
    pe = frappe._dict(
        name=doc.name,
        student=doc.student,
        program=doc.program,
        academic_term=doc.academic_term,
    )
    courses = [r.course for r in (doc.required_on_enroll_courses or []) if r.course]
    for course in courses:
        _try_enroll(pe, course)


def fulfill_for_program_enrollment(pe_name):
    """Re-runnable fulfiller for an existing PE (used by reconcile). Reads the
    PE's frozen snapshot and enrolls into any owed course with an open offering."""
    pe = _load_active_pe(pe_name)
    if not pe:
        return
    for course in _snapshot_courses(pe_name):
        _try_enroll(pe, course)


# ---------------------------------------------------------------------------
# Seam (b): Course Schedule opens
# ---------------------------------------------------------------------------


def on_course_schedule_update(doc, method=None):
    """Course Schedule on_update hook. Acts only when workflow_state just
    transitioned INTO 'Open for Enrollment' — cheap short-circuit otherwise."""
    if doc.workflow_state != "Open for Enrollment":
        return
    if not doc.has_value_changed("workflow_state"):
        return
    _backfill_open_course_schedule(doc.name, doc.course)


def on_course_schedule_insert(doc, method=None):
    """Course Schedule after_insert hook. Covers a CS born directly Open
    (get_default_initial_state) — on_update does not fire on first insert."""
    if doc.workflow_state == "Open for Enrollment":
        _backfill_open_course_schedule(doc.name, doc.course)


def _backfill_open_course_schedule(cs_name, course):
    """Every active PE whose frozen snapshot lists ``course`` and who still owes
    it -> enroll into THIS course schedule."""
    if not course:
        return
    for pe in _active_pes_with_snapshot_course(course):
        _try_enroll(pe, course, cs_name=cs_name)


# ---------------------------------------------------------------------------
# Manual backfill (Program form button / bench) — explicit, append-only
# ---------------------------------------------------------------------------


def reconcile_required_enrollments(program=None):
    """Push currently-flagged mandatory-on-enrollment courses to active PEs of
    a program. Append-only: adds any newly-flagged course missing from each
    PE's frozen snapshot, then fulfills. Never wipes the snapshot. Returns a
    summary dict. Callable from the Program button and from bench."""
    if not program:
        frappe.throw(_("A program is required."))

    flagged = frappe.get_all(
        "Program Course",
        filters={"parent": program, "pgm_course_reqonenroll": 1, "disabled": 0},
        pluck="course",
    )
    pes = frappe.get_all(
        "Program Enrollment",
        filters={"program": program, "docstatus": 1, "pgmenrol_active": 1},
        pluck="name",
    )

    snapshots_updated = 0
    for pe_name in pes:
        pe_doc = frappe.get_doc("Program Enrollment", pe_name)
        existing = {r.course for r in (pe_doc.required_on_enroll_courses or [])}
        added = [c for c in flagged if c not in existing]
        if added:
            for course in added:
                pe_doc.append("required_on_enroll_courses", {"course": course})
            # allow_on_submit field — persist the snapshot rows on a submitted doc.
            pe_doc.save(ignore_permissions=True)
            snapshots_updated += 1
        fulfill_for_program_enrollment(pe_name)

    return {
        "program": program,
        "active_enrollments": len(pes),
        "snapshots_updated": snapshots_updated,
        "flagged_courses": len(flagged),
    }


# ---------------------------------------------------------------------------
# Core enrollment decision
# ---------------------------------------------------------------------------


def _try_enroll(pe, course, cs_name=None):
    """Enroll ``pe`` into ``course`` if owed, prereqs met, and an offering is
    open. ``pe`` is a dict with name/student/program/academic_term. When
    ``cs_name`` is given (seam b knows the CS), enroll into it directly;
    otherwise pick the best open offering."""
    if _already_covered(pe.name, course):
        return
    if not _prereqs_met(pe.name, course):
        _notify_registrar_prereq_block(pe, course)
        return
    if cs_name is None:
        cs_name = _pick_offering(_open_offerings(course), pe.academic_term)
    if not cs_name:
        return  # no open offering yet — deferred to seam (b)
    _safe_course_enroll(pe.name, cs_name)


def _safe_course_enroll(pe_name, cs_name):
    """try/except wrapper around api.course_enroll. The CEI's own
    validate_duplicate* is the authoritative idempotency guard; a duplicate
    throw here is a benign 'already enrolled, skip'."""
    from seminary.seminary.api import course_enroll

    try:
        course_enroll(pe_name, cs_name)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"required_enrollment: course_enroll failed (pe={pe_name}, cs={cs_name})",
        )


# ---------------------------------------------------------------------------
# Predicates / queries
# ---------------------------------------------------------------------------


def _snapshot_courses(pe_name):
    return frappe.get_all(
        "Program Enrollment Required Course",
        filters={"parent": pe_name},
        pluck="course",
    )


def _load_active_pe(pe_name):
    pe = frappe.db.get_value(
        "Program Enrollment",
        pe_name,
        ["name", "student", "program", "academic_term", "pgmenrol_active", "docstatus"],
        as_dict=True,
    )
    if not pe or pe.docstatus != 1 or not pe.pgmenrol_active:
        return None
    return pe


def _active_pes_with_snapshot_course(course):
    """Active PEs whose frozen snapshot includes ``course``."""
    rows = frappe.db.sql(
        """
        SELECT pe.name, pe.student, pe.program, pe.academic_term
        FROM `tabProgram Enrollment` pe
        INNER JOIN `tabProgram Enrollment Required Course` rc
            ON rc.parent = pe.name
        WHERE rc.course = %s
          AND pe.docstatus = 1
          AND pe.pgmenrol_active = 1
        """,
        (course,),
        as_dict=True,
    )
    return rows


def _already_covered(pe_name, course):
    """True if the student already has a live CEI for this course (any
    non-withdrawn / non-cancelled / non-audit state) OR a passing (graded,
    non-Fail) PEC. A Failed PEC leaves the course owed. This makes a repeatable
    mandatory course fulfill once via the auto path."""
    if frappe.db.exists(
        "Course Enrollment Individual",
        {
            "program_ce": pe_name,
            "course_data": course,
            "audit": 0,
            "docstatus": ["!=", 2],
            "course_cancelled": 0,
            "withdrawn": 0,
        },
    ):
        return True
    return bool(
        frappe.db.exists(
            "Program Enrollment Course",
            {
                "parent": pe_name,
                "course_name": course,
                "pec_finalgradecode": ["is", "set"],
                "status": ["!=", "Fail"],
            },
        )
    )


def unmet_prerequisites(pe_name, course):
    """Mandatory prerequisite courses the student lacks a graded, non-Fail PEC
    for, scoped to this enrollment. PEC.course_name holds the underlying Course
    (fetched from Course Schedule.course). Returns a list of Course names (empty
    when all mandatory prerequisites are satisfied)."""
    mandatory = frappe.get_all(
        "Course_prerequisite",
        filters={"parent": course, "prereq_mandatory": "Mandatory"},
        pluck="course",
    )
    missing = []
    for prereq in mandatory:
        ok = frappe.db.exists(
            "Program Enrollment Course",
            {
                "parent": pe_name,
                "course_name": prereq,
                "pec_finalgradecode": ["is", "set"],
                "status": ["!=", "Fail"],
            },
        )
        if not ok:
            missing.append(prereq)
    return missing


def _prereqs_met(pe_name, course):
    """True when the course has no unmet mandatory prerequisite for this PE."""
    return not unmet_prerequisites(pe_name, course)


def _open_offerings(course):
    """Open Course Schedules for ``course`` whose Academic Term is open."""
    return frappe.db.sql(
        """
        SELECT cs.name, cs.academic_term, cs.modality, cs.c_datestart
        FROM `tabCourse Schedule` cs
        INNER JOIN `tabAcademic Term` at ON at.name = cs.academic_term
        WHERE cs.course = %s
          AND cs.workflow_state = 'Open for Enrollment'
          AND at.open = 1
        """,
        (course,),
        as_dict=True,
    )


def _pick_offering(offerings, pe_term):
    """Pick one open offering. Order: same term as the enrollment, then prefer
    Virtual (no room contention), then earliest class start, then name."""
    if not offerings:
        return None

    far_future = getdate("2999-12-31")

    def sort_key(o):
        return (
            0 if o.academic_term == pe_term else 1,
            0 if (o.modality or "") == "Virtual" else 1,
            getdate(o.c_datestart) if o.c_datestart else far_future,
            o.name,
        )

    return sorted(offerings, key=sort_key)[0].name


# ---------------------------------------------------------------------------
# Registrar notification (unmet prerequisites)
# ---------------------------------------------------------------------------


def _notify_registrar_prereq_block(pe, course):
    """Create one open ToDo per Registrar when a mandatory-on-enrollment course
    cannot be auto-enrolled because its prerequisites are unmet. Idempotent:
    skips if an open ToDo for this PE already mentions the course."""
    from seminary.seminary.cei_lifecycle import _registrar_emails

    recipients = _registrar_emails()
    if not recipients:
        return

    description = _(
        "Mandatory-on-enrollment course {0} could not be auto-enrolled for "
        "enrollment {1}: prerequisites are not met. Review sequencing or enroll "
        "the student manually once prerequisites are satisfied."
    ).format(course, pe.name)

    for user in recipients:
        if frappe.db.exists(
            "ToDo",
            {
                "allocated_to": user,
                "reference_type": "Program Enrollment",
                "reference_name": pe.name,
                "status": "Open",
                "description": ["like", f"%{course}%"],
            },
        ):
            continue
        try:
            frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "owner": user,
                    "allocated_to": user,
                    "description": description,
                    "reference_type": "Program Enrollment",
                    "reference_name": pe.name,
                    "priority": "Medium",
                    "status": "Open",
                }
            ).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"required_enrollment: failed to assign prereq ToDo for {pe.name} to {user}",
            )


def _notify_registrar_enroll_failure(pe, course, reason):
    """Create one open ToDo per Registrar when a term-roll auto-enroll attempt
    fails for a reason other than unmet prerequisites (e.g. a CEI validation
    error). Idempotent: skips if an open ToDo for this PE already mentions the
    course. Mirrors _notify_registrar_prereq_block."""
    from seminary.seminary.cei_lifecycle import _registrar_emails

    recipients = _registrar_emails()
    if not recipients:
        return

    description = _(
        "Course {0} could not be auto-enrolled for enrollment {1} during term "
        "roll: {2}. Review and enroll the student manually if appropriate."
    ).format(course, pe.name, reason)

    for user in recipients:
        if frappe.db.exists(
            "ToDo",
            {
                "allocated_to": user,
                "reference_type": "Program Enrollment",
                "reference_name": pe.name,
                "status": "Open",
                "description": ["like", f"%{course}%"],
            },
        ):
            continue
        try:
            frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "owner": user,
                    "allocated_to": user,
                    "description": description,
                    "reference_type": "Program Enrollment",
                    "reference_name": pe.name,
                    "priority": "Medium",
                    "status": "Open",
                }
            ).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"required_enrollment: failed to assign enroll-failure ToDo for {pe.name} to {user}",
            )
