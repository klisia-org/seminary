# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Graduation Request lifecycle.

Mirrors the Course Enrollment Individual lifecycle (ADR 016) for the
graduation flow:

    Draft → Awaiting Payment → Approved
                            ↓
                        Cancelled

Sales Invoice generation runs in the controller's `on_submit`. This
module handles the payment-driven advancement: when a Payment Entry
posts against a GR's invoice and the aggregate payment hits 100%, the
GR auto-transitions from Awaiting Payment to Approved.

Per `feedback_workflow_conditions` memory, system-driven transitions
bypass `apply_workflow` via direct `db.set_value`. The Workflow doc
still owns user-visible buttons.
"""

import frappe
from frappe.utils import flt


# 100% payment is required to approve a Graduation Request. Hard-coded
# rather than per-program — the registrar can override workflow_state
# via the Workflow buttons if a partial-payment policy is needed.
APPROVAL_THRESHOLD_PERCENT = 100.0


def on_payment_entry_submit(doc, method=None):
    """Payment Entry hook. For each linked SI that traces back to a GR,
    recompute paid_percent and auto-transition Awaiting Payment → Approved
    when the threshold is crossed.
    """
    for gr_name in _grs_from_payment_entry(doc):
        _recompute_and_react(gr_name)


def on_payment_entry_cancel(doc, method=None):
    """Payment Entry on_cancel — recompute on refund/reversal. We do NOT
    auto-rollback an Approved GR if payment drops; registrar handles
    refunds explicitly.
    """
    for gr_name in _grs_from_payment_entry(doc):
        _recompute_paid_percent(gr_name)


def on_si_submit(doc, method=None):
    """Sales Invoice on_submit — recompute paid_percent for any linked GR.
    Covers the case where SIs are created already-submitted (auto-submit
    in Seminary Settings)."""
    gr = getattr(doc, "custom_graduation_request", None)
    if not gr:
        return
    _recompute_and_react(gr)


def on_si_update_after_submit(doc, method=None):
    """Sales Invoice on_update_after_submit — fires on outstanding_amount
    changes via the form (rare; ERPNext typically uses db.set_value which
    bypasses this). Idempotent recompute either way."""
    gr = getattr(doc, "custom_graduation_request", None)
    if not gr:
        return
    _recompute_and_react(gr)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _grs_from_payment_entry(pe_doc):
    """Distinct GR names traced from this Payment Entry's references via
    Sales Invoice.custom_graduation_request."""
    gr_names = set()
    for ref in pe_doc.references or []:
        if ref.reference_doctype != "Sales Invoice" or not ref.reference_name:
            continue
        gr = frappe.db.get_value(
            "Sales Invoice", ref.reference_name, "custom_graduation_request"
        )
        if gr:
            gr_names.add(gr)
    return gr_names


def _recompute_and_react(gr_name):
    paid_percent = _recompute_paid_percent(gr_name)
    state = frappe.db.get_value("Graduation Request", gr_name, "workflow_state")
    if state == "Awaiting Payment" and paid_percent >= APPROVAL_THRESHOLD_PERCENT:
        _advance_to_academic_review(gr_name)


def _recompute_paid_percent(gr_name):
    rows = frappe.db.sql(
        """SELECT COALESCE(SUM(grand_total), 0) AS invoiced,
                  COALESCE(SUM(grand_total - outstanding_amount), 0) AS paid,
                  COUNT(*) AS si_count
           FROM `tabSales Invoice`
           WHERE custom_graduation_request = %s
             AND docstatus = 1
             AND is_return = 0""",
        (gr_name,),
        as_dict=True,
    )
    invoiced = flt(rows[0].invoiced) if rows else 0.0
    paid = flt(rows[0].paid) if rows else 0.0
    si_count = int(rows[0].si_count) if rows else 0

    if invoiced > 0:
        paid_percent = paid / invoiced * 100.0
    elif si_count > 0:
        paid_percent = 100.0  # all-zero invoices (full scholarship)
    else:
        paid_percent = 0.0

    frappe.db.set_value(
        "Graduation Request",
        gr_name,
        "paid_percent",
        paid_percent,
        update_modified=False,
    )
    return paid_percent


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


def cascade_cancel_graduation_requests(pe_name):
    """Cancel every active Graduation Request bound to this Program Enrollment.

    Triggered when a PE is deactivated (`pgmenrol_active` 1→0) or otherwise
    withdrawn. The fee is non-refundable per the per-program policy, so the
    cancel path on each GR skips Sales Invoice cancellation when the
    `cascade_from_pe_withdrawal` flag is set on the doc.
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
        try:
            gr = frappe.get_doc("Graduation Request", name)
            gr.flags.cascade_from_pe_withdrawal = 1
            gr.cancel()
        except Exception:
            frappe.log_error(
                title=f"Cascade cancel failed for Graduation Request {name}",
                message=frappe.get_traceback(),
            )
