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
- Sales Invoice on_submit / on_update_after_submit → maybe_advance_cei_on_payment
- Sales Invoice on_cancel → maybe_notify_registrar_on_invoice_cancel
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
    if doc.workflow_state == "Submitted":
        enroll_student(doc)
    # "Awaiting Payment" and "Withdrawn" require no on-arrival side effects:
    # the SI was created at on_submit; withdrawal side-effects already ran in
    # withdrawal.py:process_academic_approval before workflow_state was set.


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
# Payment-driven advancement
# ---------------------------------------------------------------------------


def maybe_advance_cei_on_payment(doc, method=None):
    """Sales Invoice hook. Note: ERPNext updates SI.outstanding_amount via
    db.set_value on payment, which doesn't trigger on_update_after_submit —
    the actual payment-driven advancement happens in `on_payment_entry_submit`.
    This hook still fires for direct SI form saves and runs the same
    recompute, harmlessly."""
    cei_name = getattr(doc, "custom_cei", None)
    if not cei_name:
        return
    _recompute_and_react(cei_name)


def maybe_notify_registrar_on_invoice_cancel(doc, method=None):
    """Sales Invoice on_cancel hook. If a refund/cancellation drops the linked
    CEI's paid_percent below the program threshold while the CEI is already in
    Submitted state, notify registrars (Academics User role) — but do NOT
    revert the workflow state. See plan §7."""
    cei_name = getattr(doc, "custom_cei", None)
    if not cei_name:
        return

    _recompute_and_react(cei_name)


def on_payment_entry_submit(doc, method=None):
    """Payment Entry hook. ERPNext updates Sales Invoice.outstanding_amount via
    db.set_value when a payment posts, which bypasses SI's on_update_after_submit
    — so we hook on Payment Entry directly. For each linked SI that traces back
    to a CEI, recompute payment status and advance / notify as needed."""
    for cei_name in _ceis_from_payment_entry(doc):
        _recompute_and_react(cei_name)


def on_payment_entry_cancel(doc, method=None):
    """Payment Entry on_cancel — refund/reversal path. Same fan-out as submit:
    recompute every linked CEI, notify registrar if a Submitted CEI drops below
    threshold."""
    for cei_name in _ceis_from_payment_entry(doc):
        _recompute_and_react(cei_name)


def _recompute_and_react(cei_name):
    """Refresh tracking fields on the CEI and either auto-advance (if threshold
    crossed upward) or notify registrar (if a Submitted CEI fell below)."""
    paid_percent, threshold = _recompute_cei_payment_status(cei_name)

    state = frappe.db.get_value(
        "Course Enrollment Individual", cei_name, "workflow_state"
    )
    if state == "Awaiting Payment" and paid_percent >= threshold:
        _advance_cei_to_submitted(cei_name)
    elif state == "Submitted" and paid_percent < threshold:
        _notify_registrar_payment_dropped(cei_name, paid_percent, threshold)


def _ceis_from_payment_entry(pe_doc):
    """Distinct CEI names traced from this Payment Entry's references via
    Sales Invoice.custom_cei. Skips reference rows that aren't Sales Invoices
    or whose SI has no linked CEI."""
    cei_names = set()
    for ref in pe_doc.references or []:
        if ref.reference_doctype != "Sales Invoice" or not ref.reference_name:
            continue
        cei = frappe.db.get_value("Sales Invoice", ref.reference_name, "custom_cei")
        if cei:
            cei_names.add(cei)
    return cei_names


def _recompute_cei_payment_status(cei_name):
    """Aggregate submitted Sales Invoices linked to a CEI. Update tracking
    fields on the CEI and return (paid_percent, threshold)."""
    rows = frappe.db.sql(
        """SELECT COALESCE(SUM(grand_total), 0) AS invoiced,
                  COALESCE(SUM(grand_total - outstanding_amount), 0) AS paid,
                  COUNT(*) AS si_count
           FROM `tabSales Invoice`
           WHERE custom_cei = %s
             AND docstatus = 1
             AND is_return = 0""",
        (cei_name,),
        as_dict=True,
    )
    invoiced = flt(rows[0].invoiced) if rows else 0.0
    paid = flt(rows[0].paid) if rows else 0.0
    si_count = int(rows[0].si_count) if rows else 0

    if invoiced > 0:
        paid_percent = paid / invoiced * 100.0
    elif si_count > 0:
        # All linked invoices are $0 (e.g. full scholarship) — vacuously paid.
        paid_percent = 100.0
    else:
        paid_percent = 0.0

    threshold = flt(
        frappe.db.get_value("Course Enrollment Individual", cei_name, "percent_to_pay")
        or 100.0
    )

    frappe.db.set_value(
        "Course Enrollment Individual",
        cei_name,
        {
            "total_invoiced": invoiced,
            "total_paid": paid,
            "paid_percent": paid_percent,
        },
        update_modified=False,
    )
    return paid_percent, threshold


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


def _notify_registrar_payment_dropped(cei_name, paid_percent, threshold):
    """Create a ToDo on the CEI for every Academics User and send a templated
    email summarizing the situation. Triggered when a refund or invoice cancel
    drops a Submitted CEI's paid_percent below threshold."""
    recipients = _academics_user_emails()
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
        "Review whether to file a Course Withdrawal Request or follow up with the student."
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

    try:
        frappe.sendmail(
            recipients=recipients,
            subject=_("Payment threshold dropped: {0}").format(cei_name),
            message=description,
            reference_doctype="Course Enrollment Individual",
            reference_name=cei_name,
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"cei_lifecycle: failed to email registrars for {cei_name}",
        )


def _academics_user_emails():
    """Return distinct enabled User emails who hold the Academics User role."""
    rows = frappe.db.sql(
        """SELECT DISTINCT u.name
           FROM `tabUser` u
           INNER JOIN `tabHas Role` r ON r.parent = u.name
           WHERE u.enabled = 1
             AND r.role = 'Academics User'""",
        as_dict=True,
    )
    return [r.name for r in rows if r.name]
