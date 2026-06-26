"""Course Enrollment Individual lifecycle.

The CEI workflow has four states:
    Draft → Awaiting Payment | Submitted → Withdrawn

Submission generates the Sales Invoice (regardless of which post-submit
state the doc lands in). Roster and Program Enrollment Course rows are
only created when the CEI reaches the Submitted state — either directly
(free programs / payment not required) or after the student's payment
crosses the program's `percent_to_pay` threshold.

Hook entry points (registered in hooks.py):
- CEI on_update_after_submit → on_workflow_update

Payment-driven advancement is invoked by the financial backend (oikonomos), which
reacts to its own billing documents and calls `react_to_cei_payment(cei_name)`
here. A Frappe-only seminary has no payment documents, so this is never reached —
enrollments advance as free.
"""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime


# ---------------------------------------------------------------------------
# CEI workflow dispatcher
# ---------------------------------------------------------------------------


def on_workflow_update(doc, method=None):
    """Fired on Course Enrollment Individual `on_update_after_submit`.
    Routes side-effects by workflow state. Idempotent."""
    from seminary.seminary.waitlist import assign_waitlist_positions, recount

    # A student promoted off the waitlist via the manual Promote action arrives
    # here in Submitted / Awaiting Payment without ever passing through
    # on_submit (which skipped invoicing while they were Waitlisted). Raise the
    # invoice now. Auto-promotion goes through waitlist._promote_cei instead and
    # does this itself, so cei_si is already set and this is a no-op there.
    if doc.workflow_state in ("Submitted", "Awaiting Payment") and not doc.cei_si:
        doc.generate_enrollment_invoice()

    if doc.workflow_state == "Submitted":
        enroll_student(doc)

    # A fresh Waitlisted arrival needs a queue position assigned.
    if doc.workflow_state == "Waitlisted" and doc.coursesc_ce:
        assign_waitlist_positions(doc.coursesc_ce)

    # Keep the section's seat/demand caches honest on every state change.
    # "Withdrawn"/"Unseated" free a seat, but those paths (withdrawal.py /
    # waitlist.mark_waitlist_unseated) call recount_and_promote themselves;
    # here a recount is enough.
    if doc.coursesc_ce:
        recount(doc.coursesc_ce)


def enroll_student(cei_doc):
    """Idempotent: create Scheduled Course Roster + Program Enrollment Course
    rows for this CEI if they don't already exist."""
    from seminary.seminary.api import (
        copy_data_to_scheduled_course_roster,
        copy_data_to_program_enrollment_course,
    )
    from seminary.seminary.graduation_candidate import evaluate_candidacy_safe

    if not _roster_exists(cei_doc.coursesc_ce, cei_doc.student_ce):
        copy_data_to_scheduled_course_roster(cei_doc, None)

    if not _pec_exists(cei_doc.program_ce, cei_doc.coursesc_ce):
        copy_data_to_program_enrollment_course(cei_doc, None)

    evaluate_candidacy_safe(cei_doc.program_ce)


def _roster_exists(course_schedule, student):
    if not course_schedule or not student:
        return False
    return bool(
        frappe.db.exists(
            "Scheduled Course Roster",
            {"course_sc": course_schedule, "student": student},
        )
    )


def _pec_exists(program_enrollment, course_schedule):
    if not program_enrollment or not course_schedule:
        return False
    return bool(
        frappe.db.exists(
            "Program Enrollment Course",
            {"parent": program_enrollment, "course": course_schedule},
        )
    )


# ---------------------------------------------------------------------------
# Payment-driven advancement (entry point called by the financial backend)
# ---------------------------------------------------------------------------


def react_to_cei_payment(cei_name):
    """Refresh tracking fields on the CEI and either auto-advance (if threshold
    crossed upward) or notify registrar (if a Submitted CEI fell below).

    The academic entry point for payment-driven advancement: it asks the
    financial backend for the payment aggregate and acts on the academic state
    machine. The bridge (oikonomos) calls this from its own Sales Invoice /
    Payment Entry handlers; seminary itself never reacts to billing documents."""
    paid_percent, threshold = _recompute_cei_payment_status(cei_name)

    state = frappe.db.get_value(
        "Course Enrollment Individual", cei_name, "workflow_state"
    )
    if state == "Awaiting Payment" and paid_percent >= threshold:
        _advance_cei_to_submitted(cei_name)
    elif state == "Submitted" and paid_percent < threshold:
        _notify_registrar_payment_dropped(cei_name, paid_percent, threshold)


def _recompute_cei_payment_status(cei_name):
    """Aggregate submitted invoices linked to a CEI via the financial backend,
    write the tracking fields on the CEI, and return (paid_percent, threshold).

    The invoice aggregate is a financial fact (owned by the backend); the
    tracking-field bookkeeping and the program payment threshold are academic
    and stay here. With no financial backend the aggregate reads fully-paid, so
    `threshold` is vacuously met and the CEI advances as free."""
    from seminary.seminary.financial.backend import get_financial_backend

    agg = get_financial_backend().payment_status_for_cei(cei_name)

    threshold = flt(
        frappe.db.get_value("Course Enrollment Individual", cei_name, "percent_to_pay")
        or 100.0
    )

    frappe.db.set_value(
        "Course Enrollment Individual",
        cei_name,
        {
            "total_invoiced": agg.invoiced,
            "total_paid": agg.paid,
            "paid_percent": agg.paid_percent,
        },
        update_modified=False,
    )
    return agg.paid_percent, threshold


def _advance_cei_to_submitted(cei_name):
    """System-driven advance from Awaiting Payment to Submitted.

    Per ADR 013, system-driven workflow transitions bypass apply_workflow via
    db.set_value. We also manually fire the post-submit side effects (roster
    + PEC creation) because db.set_value doesn't invoke on_update_after_submit.
    """
    frappe.db.set_value(
        "Course Enrollment Individual",
        cei_name,
        {
            "workflow_state": "Submitted",
            "paid_threshold_met_on": now_datetime(),
        },
        update_modified=False,
    )
    cei = frappe.get_doc("Course Enrollment Individual", cei_name)
    cei.workflow_state = "Submitted"
    enroll_student(cei)

    # Payment-driven advance bypasses on_update_after_submit (db.set_value
    # above), so refresh the seat caches here.
    if cei.coursesc_ce:
        from seminary.seminary.waitlist import recount

        recount(cei.coursesc_ce)


def _notify_registrar_payment_dropped(cei_name, paid_percent, threshold):
    """Create a ToDo on the CEI for every Registrar and send a templated
    email summarizing the situation. Triggered when a refund or invoice cancel
    drops a Submitted CEI's paid_percent below threshold."""
    recipients = _registrar_emails()
    if not recipients:
        return

    cei = frappe.db.get_value(
        "Course Enrollment Individual",
        cei_name,
        ["student_ce", "course_data", "program_data"],
        as_dict=True,
    )
    student_label = cei.student_ce if cei else cei_name
    course_label = cei.course_data if cei else "?"
    description = _(
        "Payment threshold no longer met for {0} (course {1}). "
        "Now at {2:.1f}%, threshold is {3:.1f}%. "
        "Review whether to file a Withdrawal Request or follow up with the student."
    ).format(student_label, course_label, paid_percent, threshold)

    for user in recipients:
        try:
            frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "owner": user,
                    "allocated_to": user,
                    "description": description,
                    "reference_type": "Course Enrollment Individual",
                    "reference_name": cei_name,
                    "priority": "Medium",
                    "status": "Open",
                }
            ).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"cei_lifecycle: failed to assign ToDo for {cei_name} to {user}",
            )

    from seminary.seminary import comms

    comms.send_to_role(
        "Registrar",
        "cei-payment-threshold",
        context={
            "student": student_label,
            "course": course_label,
            "paid_percent": round(paid_percent, 1),
            "threshold": round(threshold, 1),
        },
        reference_doctype="Course Enrollment Individual",
        reference_name=cei_name,
        triggered_by="cei-payment-threshold",
    )


def _registrar_emails():
    """Return distinct enabled User emails who hold the Registrar role."""
    rows = frappe.db.sql(
        """SELECT DISTINCT u.name
           FROM `tabUser` u
           INNER JOIN `tabHas Role` r ON r.parent = u.name
           WHERE u.enabled = 1
             AND r.role = 'Registrar'""",
        as_dict=True,
    )
    return [r.name for r in rows if r.name]
