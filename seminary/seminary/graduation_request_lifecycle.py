# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Graduation Request lifecycle.

Mirrors the Course Enrollment Individual lifecycle (ADR 016) for the
graduation flow:

    Draft → Awaiting Payment → Approved
                            ↓
                        Cancelled

Sales Invoice generation runs in the controller's `on_submit`. This
module handles the payment-driven advancement: when a payment posts against a
GR's invoice and the aggregate payment hits 100%, the GR auto-transitions from
Awaiting Payment to Academic Review.

Payment-driven advancement is invoked by the financial backend (oikonomos), which
reacts to its own billing documents and calls `react_to_gr_payment(gr_name)` /
`recompute_gr_paid_percent(gr_name)` here. A Frappe-only seminary has no payment
documents, so the GR clears its payment gate as free.

Per `feedback_workflow_conditions` memory, system-driven transitions
bypass `apply_workflow` via direct `db.set_value`. The Workflow doc
still owns user-visible buttons.
"""

import frappe


# 100% payment is required to approve a Graduation Request. Hard-coded
# rather than per-program — the registrar can override workflow_state
# via the Workflow buttons if a partial-payment policy is needed.
APPROVAL_THRESHOLD_PERCENT = 100.0


def react_to_gr_payment(gr_name):
    """Academic entry point for payment-driven GR advancement: recompute
    paid_percent (via the financial backend) and auto-transition Awaiting
    Payment → Academic Review when the threshold is crossed. Called by the
    bridge from its own Sales Invoice / Payment Entry handlers."""
    paid_percent = recompute_gr_paid_percent(gr_name)
    state = frappe.db.get_value("Graduation Request", gr_name, "workflow_state")
    if state == "Awaiting Payment" and paid_percent >= APPROVAL_THRESHOLD_PERCENT:
        _advance_to_academic_review(gr_name)


def recompute_gr_paid_percent(gr_name):
    """Aggregate submitted invoices linked to a Graduation Request via the
    financial backend and stamp paid_percent. With no financial backend this
    reads fully-paid, so the GR clears its payment gate as free."""
    from seminary.seminary.financial.backend import get_financial_backend

    agg = get_financial_backend().payment_status_for_graduation(gr_name)

    frappe.db.set_value(
        "Graduation Request",
        gr_name,
        "paid_percent",
        agg.paid_percent,
        update_modified=False,
    )
    return agg.paid_percent


def _advance_to_academic_review(gr_name):
    """System-driven advance from Awaiting Payment to Academic Review.

    Per memory `feedback_workflow_conditions`, system-driven workflow
    transitions bypass apply_workflow via db.set_value. The Workflow
    doc retains its user-facing 'Mark as Paid' button for the manual
    override path. Academic Review → Financial Review → Approved are
    handled manually by Academics / Accounts staff.
    """
    frappe.db.set_value(
        "Graduation Request",
        gr_name,
        "workflow_state",
        "Academic Review",
        update_modified=False,
    )


# ---------------------------------------------------------------------------
# Cascade cancel on PE inactivation
# ---------------------------------------------------------------------------


def cascade_cancel_graduation_requests(pe_name, exclude=None):
    """Cancel every active Graduation Request bound to this Program Enrollment.

    Triggered when a PE is deactivated (`pgmenrol_active` 1→0) or otherwise
    withdrawn. The fee is non-refundable per the per-program policy, so the
    cancel path on each GR skips Sales Invoice cancellation when the
    `cascade_from_pe_withdrawal` flag is set on the doc.

    ``exclude`` names a Graduation Request to leave untouched — used by the
    graduation terminal transition, where the approved request is the source of
    the status change and must not cancel itself.
    """
    grs = frappe.get_all(
        "Graduation Request",
        filters={
            "program_enrollment": pe_name,
            "docstatus": 1,
            "workflow_state": (
                "in",
                (
                    "Draft",
                    "Awaiting Payment",
                    "Academic Review",
                    "Financial Review",
                    "Approved",
                ),
            ),
        },
        pluck="name",
    )
    for name in grs:
        if name == exclude:
            continue
        try:
            gr = frappe.get_doc("Graduation Request", name)
            gr.flags.cascade_from_pe_withdrawal = 1
            gr.cancel()
        except Exception:
            frappe.log_error(
                title=f"Cascade cancel failed for Graduation Request {name}",
                message=frappe.get_traceback(),
            )
