"""Room-capacity waitlist engine for Course Enrollment Individual (CEI).

This is the single choke point for seat accounting and waitlist promotion.
See ADR 035.

Seat semantics (all counts exclude withdrawn / course-cancelled CEIs):
- ``enrollments``    = rostered students          → workflow_state = Submitted
- ``seats_used``     = seat-holders (capacity)     → Submitted + Awaiting Payment
- ``registrations``  = total demand                → Draft + Awaiting Payment
                                                      + Submitted + Waitlisted
- ``waitlist_count`` = queue length                → Waitlisted

A section is *full* when ``max_enrollment`` is set and
``seats_used >= max_enrollment``. A null/zero cap means uncapped — the waitlist
states and this engine stay dormant (progressive: opt-in by data presence).

Promotion only runs while the Course Schedule is in ``Open for Enrollment``.
When enrollment closes, any remaining Waitlisted CEIs are moved to the terminal
``Unseated`` state (the room-scarcity signal).
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

# Seat-holding states (consume capacity). Awaiting Payment holds a seat: the
# student has committed and we must not oversell while they pay.
SEAT_HOLDER_STATES = ("Submitted", "Awaiting Payment")
# States that count as live demand.
DEMAND_STATES = ("Draft", "Awaiting Payment", "Submitted", "Waitlisted")
# Promotion is only meaningful while enrollment is open.
PROMOTABLE_CS_STATES = ("Open for Enrollment",)


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------


def count_states(cs_name):
    """Return the seat/demand counts for a Course Schedule from CEI state."""
    row = frappe.db.sql(
        """
        SELECT
          COALESCE(SUM(workflow_state = 'Submitted'), 0)        AS submitted,
          COALESCE(SUM(workflow_state = 'Awaiting Payment'), 0) AS awaiting,
          COALESCE(SUM(workflow_state = 'Draft'), 0)            AS draft,
          COALESCE(SUM(workflow_state = 'Waitlisted'), 0)       AS waitlisted
        FROM `tabCourse Enrollment Individual`
        WHERE coursesc_ce = %s
          AND docstatus < 2
          AND COALESCE(course_cancelled, 0) = 0
          AND COALESCE(withdrawn, 0) = 0
        """,
        (cs_name,),
        as_dict=True,
    )[0]
    submitted = int(row.submitted or 0)
    awaiting = int(row.awaiting or 0)
    draft = int(row.draft or 0)
    waitlisted = int(row.waitlisted or 0)
    return {
        "enrollments": submitted,
        "seats_used": submitted + awaiting,
        "registrations": submitted + awaiting + draft + waitlisted,
        "waitlist_count": waitlisted,
    }


def recount(cs_name):
    """Recompute and persist the four cache fields on the Course Schedule.

    Replaces the old increment-only ``enrollments`` counter, which drifted
    because withdrawals never decremented it. Writes with
    ``update_modified=False`` so the cache refresh doesn't bump the doc
    timestamp or fire save hooks.
    """
    counts = count_states(cs_name)
    frappe.db.set_value("Course Schedule", cs_name, counts, update_modified=False)

    # Keep every pending Draft's seat_available flag current with the live seat
    # count. The CEI workflow conditions read this stored flag at transition
    # time (Frappe safe_eval can't call a function), so refreshing it whenever
    # the count changes closes the common staleness window: a draft created when
    # there was room is flipped to 0 once the section fills, and back to 1 when a
    # seat frees. Simultaneous races remain (see ADR 038).
    cap = frappe.db.get_value("Course Schedule", cs_name, "max_enrollment")
    available = 0 if (cap and counts["seats_used"] >= cap) else 1
    frappe.db.sql(
        """
        UPDATE `tabCourse Enrollment Individual`
        SET seat_available = %s
        WHERE coursesc_ce = %s AND workflow_state = 'Draft' AND docstatus = 0
        """,
        (available, cs_name),
    )
    return counts


def seats_used(cs_name, exclude_cei=None):
    """Live count of seat-holders, optionally excluding one CEI (the doc being
    validated, so it doesn't count itself)."""
    filters = {
        "coursesc_ce": cs_name,
        "docstatus": ["<", 2],
        "course_cancelled": 0,
        "withdrawn": 0,
        "workflow_state": ["in", list(SEAT_HOLDER_STATES)],
    }
    if exclude_cei:
        filters["name"] = ["!=", exclude_cei]
    return frappe.db.count("Course Enrollment Individual", filters)


def is_seat_available(cs_name, exclude_cei=None):
    """True when the section has an open seat — or no cap at all."""
    if not cs_name:
        return True
    cap = frappe.db.get_value("Course Schedule", cs_name, "max_enrollment")
    if not cap:  # null / 0 → uncapped
        return True
    return seats_used(cs_name, exclude_cei) < cap


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------


def recount_and_promote(cs_name):
    """Refresh caches, then promote waitlisted students into any open seats.

    Called from every seat-changing event (withdrawal, cancellation,
    capacity/room increase, a fresh Submitted enrollment). Promotion is gated
    on the CS being Open for Enrollment and on a real cap being set.
    """
    if not cs_name:
        return
    counts = recount(cs_name)
    state, cap = frappe.db.get_value(
        "Course Schedule", cs_name, ["workflow_state", "max_enrollment"]
    )
    if not cap or state not in PROMOTABLE_CS_STATES:
        _reassign_positions(cs_name)
        return

    promoted = []
    # Guard against a non-advancing loop (e.g. a promotion that fails to take
    # a seat): bail if seats_used stops increasing.
    while counts["seats_used"] < cap:
        nxt = _next_waitlisted(cs_name)
        if not nxt:
            break
        before = counts["seats_used"]
        _promote_cei(nxt)
        promoted.append(nxt)
        counts = recount(cs_name)
        if counts["seats_used"] <= before:
            break

    _reassign_positions(cs_name)
    for cei_name in promoted:
        _notify_promotion(cei_name)


def _next_waitlisted(cs_name):
    rows = frappe.get_all(
        "Course Enrollment Individual",
        filters={
            "coursesc_ce": cs_name,
            "workflow_state": "Waitlisted",
            "docstatus": 1,
        },
        order_by="creation asc",
        limit=1,
        pluck="name",
    )
    return rows[0] if rows else None


def _promote_cei(cei_name):
    """System-driven Waitlisted → Submitted / Awaiting Payment.

    Per ADR 013, system-driven workflow transitions bypass apply_workflow via
    db.set_value. The seat-holding side effects (invoice on Awaiting Payment,
    roster + PEC on Submitted) are fired manually because db.set_value does not
    invoke on_update_after_submit.
    """
    cei = frappe.get_doc("Course Enrollment Individual", cei_name)
    target = (
        "Submitted"
        if (cei.is_free or not cei.require_pay_submit)
        else "Awaiting Payment"
    )

    frappe.db.set_value(
        "Course Enrollment Individual",
        cei_name,
        {"workflow_state": target, "waitlist_position": 0},
        update_modified=False,
    )
    cei.workflow_state = target

    # Generate the enrollment invoice now (skipped while Waitlisted). Mirrors
    # CourseEnrollmentIndividual.on_submit for the non-free case.
    cei.generate_enrollment_invoice()

    if target == "Submitted":
        from seminary.seminary.cei_lifecycle import enroll_student

        frappe.db.set_value(
            "Course Enrollment Individual",
            cei_name,
            "paid_threshold_met_on",
            now_datetime(),
            update_modified=False,
        )
        enroll_student(cei)


def assign_waitlist_positions(cs_name):
    """Public entry point to (re)number a section's waitlist."""
    _reassign_positions(cs_name)


def _reassign_positions(cs_name):
    """Renumber the waitlist 1..n by arrival order (creation = FIFO)."""
    names = frappe.get_all(
        "Course Enrollment Individual",
        filters={
            "coursesc_ce": cs_name,
            "workflow_state": "Waitlisted",
            "docstatus": 1,
        },
        order_by="creation asc",
        pluck="name",
    )
    for i, name in enumerate(names, start=1):
        frappe.db.set_value(
            "Course Enrollment Individual",
            name,
            "waitlist_position",
            i,
            update_modified=False,
        )


# ---------------------------------------------------------------------------
# Enrollment close → Unseated
# ---------------------------------------------------------------------------


def mark_waitlist_unseated(cs_name):
    """Move every remaining Waitlisted CEI to the terminal Unseated state.

    Called when a Course Schedule leaves Open for Enrollment. Unseated is the
    persistent record that a student wanted the section but room scarcity kept
    them out — the Unmet Demand report counts these.
    """
    if not cs_name:
        return
    names = frappe.get_all(
        "Course Enrollment Individual",
        filters={
            "coursesc_ce": cs_name,
            "workflow_state": "Waitlisted",
            "docstatus": 1,
        },
        pluck="name",
    )
    if not names:
        return
    for name in names:
        frappe.db.set_value(
            "Course Enrollment Individual",
            name,
            {"workflow_state": "Unseated", "waitlist_position": 0},
            update_modified=False,
        )
        _notify_unseated(name)
    recount(cs_name)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def _cei_notice_context(cei_name):
    return frappe.db.get_value(
        "Course Enrollment Individual",
        cei_name,
        ["student_ce", "stu_user", "course_data", "workflow_state"],
        as_dict=True,
    )


def _notify_promotion(cei_name):
    """Tell the student and the registrars a seat opened, through the
    Communication Log (ADR 043) — templated, consent-aware, rate-limited.
    Failures are logged, never fatal to the transaction."""
    from seminary.seminary import comms
    from seminary.seminary.person import find_person

    ctx = _cei_notice_context(cei_name)
    if not ctx:
        return

    if ctx.stu_user:
        try:
            comms.send(
                find_person(user=ctx.stu_user),
                "waitlist-promoted",
                to_address=ctx.stu_user,
                context={
                    "course": ctx.course_data,
                    "awaiting_payment": ctx.workflow_state == "Awaiting Payment",
                },
                reference_doctype="Course Enrollment Individual",
                reference_name=cei_name,
                triggered_by="waitlist-promotion",
            )
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"waitlist: student promotion notice failed for {cei_name}",
            )

    comms.send_to_role(
        "Registrar",
        "waitlist-promoted-registrar",
        context={
            "student": ctx.student_ce,
            "course": ctx.course_data,
            "state": ctx.workflow_state,
        },
        reference_doctype="Course Enrollment Individual",
        reference_name=cei_name,
        triggered_by="waitlist-promotion",
    )


def _notify_unseated(cei_name):
    from seminary.seminary import comms
    from seminary.seminary.person import find_person

    ctx = _cei_notice_context(cei_name)
    if not ctx or not ctx.stu_user:
        return
    try:
        comms.send(
            find_person(user=ctx.stu_user),
            "waitlist-closed",
            to_address=ctx.stu_user,
            context={"course": ctx.course_data},
            reference_doctype="Course Enrollment Individual",
            reference_name=cei_name,
            triggered_by="waitlist-closed",
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"waitlist: unseated notice failed for {cei_name}",
        )
