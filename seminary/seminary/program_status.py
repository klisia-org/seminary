# Copyright (c) 2026, Murilo R. Melo and contributors
# For license information, please see license.txt
"""Program Enrollment status lifecycle — the single mutation point.

Every status transition (voluntary withdrawal, leave of absence, dismissal,
graduation, transfer) funnels through :func:`set_program_status`. It writes the
status, appends a Program Enrollment Status History row, and keeps the legacy
``pgmenrol_active`` flag as a derived mirror (1 only while Active).

Writes use ``db_set`` / direct child-row inserts on the (submitted) Program
Enrollment, so they do NOT re-run ``validate()`` or the controller's
``on_update_after_submit``. Because ``db_set`` bypasses that hook, terminal
transitions invoke the graduation-request cascade here directly. See ADR 030.
"""

import frappe
from frappe import _
from frappe.utils import getdate, today

TERMINAL_STATUSES = {"Withdrawn", "Dismissed", "Graduated", "Transferred"}
ACTIVE_STATUS = "Active"
LEAVE_STATUS = "Leave of Absence"

# Statuses under which a student may re-enroll in the SAME program: they left
# without completing it, so a fresh enrollment is legitimate. Any other status
# blocks a duplicate enrollment — including Active / Leave of Absence (still
# enrolled) and Graduated (already completed this program; re-enrolling makes
# no sense). A subset of TERMINAL_STATUSES, minus Graduated. Used only by the
# duplicate-enrollment guards, NOT the status lifecycle.
REENROLLABLE_STATUSES = {"Withdrawn", "Dismissed", "Transferred"}

# Maps a terminal Program Enrollment status to the Student Leaving Record's
# reason_for_leaving Select.
_TERMINAL_REASON = {
    "Graduated": "Graduation",
    "Withdrawn": "Voluntary Withdrawal",
    "Dismissed": "Dismissal",
    "Transferred": "Transfer",
}


def set_program_status(
    pe,
    to_status,
    category,
    reason=None,
    effective_date=None,
    source_doctype=None,
    source_name=None,
    notes=None,
    inactive_until=None,
):
    """Transition a Program Enrollment to ``to_status``.

    Args:
        pe: Program Enrollment name or doc.
        to_status: one of Active / Leave of Absence / Withdrawn / Dismissed /
            Graduated / Transferred.
        category: history category (Voluntary / Transfer / Medical/LOA /
            Academic / Disciplinary / Administrative / System).

    Returns the Program Enrollment doc, or None if the transition was a no-op.
    """
    pe_doc = pe if hasattr(pe, "doctype") else frappe.get_doc("Program Enrollment", pe)
    current = pe_doc.status or ACTIVE_STATUS

    if current in TERMINAL_STATUSES and to_status != current:
        frappe.throw(
            _(
                "Program Enrollment {0} is already {1}; its status cannot change to {2}."
            ).format(pe_doc.name, current, to_status)
        )

    # Repeated Active/terminal sets are no-ops; LOA may be re-applied to extend.
    if to_status == current and to_status != LEAVE_STATUS:
        return None

    effective_date = getdate(effective_date) if effective_date else getdate(today())
    new_active = 1 if to_status == ACTIVE_STATUS else 0

    _append_history(
        pe_doc,
        from_status=current,
        to_status=to_status,
        category=category,
        reason=reason,
        effective_date=effective_date,
        source_doctype=source_doctype,
        source_name=source_name,
        notes=notes,
    )

    pe_doc.db_set("status", to_status, update_modified=True)
    pe_doc.db_set("pgmenrol_active", new_active, update_modified=False)

    if to_status == LEAVE_STATUS:
        pe_doc.db_set("loa_start_date", effective_date, update_modified=False)
        if inactive_until:
            pe_doc.db_set(
                "inactiveuntil", getdate(inactive_until), update_modified=False
            )
        if reason:
            pe_doc.db_set("inactive_motive", reason, update_modified=False)
        _evaluate_billing_suspension(pe_doc)

    if to_status in TERMINAL_STATUSES:
        _on_terminal(
            pe_doc, to_status, reason, effective_date, source_doctype, source_name
        )

    return pe_doc


def return_from_leave(pe, effective_date=None):
    """Bring a Program Enrollment back from Leave of Absence to Active.

    Clears the inactive gate and billing suspension; fires a readmission fee
    when the Program Level is configured to charge one (see Phase 6)."""
    pe_doc = pe if hasattr(pe, "doctype") else frappe.get_doc("Program Enrollment", pe)
    if pe_doc.status != LEAVE_STATUS:
        frappe.throw(
            _("Program Enrollment {0} is not on Leave of Absence.").format(pe_doc.name)
        )

    set_program_status(
        pe_doc,
        ACTIVE_STATUS,
        category="System",
        reason="Returned from leave",
        effective_date=effective_date,
    )
    pe_doc.db_set("inactiveuntil", None, update_modified=False)
    pe_doc.db_set("inactive_motive", None, update_modified=False)
    pe_doc.db_set("billing_suspended", 0, update_modified=False)

    # Returning to Active makes the student billable again. The spine writes via
    # db_set, so get_payers (which syncs pf_active on a full save) never runs —
    # reactivate the payers here so recurring billing and the readmission fee fire.
    _set_payers_active(pe_doc.name, 1)
    _maybe_charge_readmission(pe_doc, effective_date)
    return pe_doc


def _set_payers_active(pe_name, active):
    """Keep the PE's Payers Fee Category PE.pf_active in sync with billability.
    The spine uses db_set, so get_payers' save-time sync does not run."""
    pfc = frappe.db.get_value("Payers Fee Category PE", {"pf_pe": pe_name}, "name")
    if pfc:
        frappe.db.set_value(
            "Payers Fee Category PE",
            pfc,
            "pf_active",
            1 if active else 0,
            update_modified=False,
        )


@frappe.whitelist()
def place_on_leave(
    program_enrollment,
    effective_date=None,
    expected_return=None,
    max_return=None,
    reason=None,
):
    """Form-facing wrapper: put a Program Enrollment on Leave of Absence."""
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    set_program_status(
        pe,
        LEAVE_STATUS,
        category="Medical/LOA",
        reason=reason,
        effective_date=effective_date,
        inactive_until=expected_return,
    )
    if expected_return:
        pe.db_set(
            "loa_expected_return", getdate(expected_return), update_modified=False
        )
    if max_return:
        pe.db_set("loa_max_return_date", getdate(max_return), update_modified=False)
    return pe.name


@frappe.whitelist()
def return_from_leave_action(program_enrollment, effective_date=None):
    """Form-facing wrapper: bring a Program Enrollment back from leave."""
    return_from_leave(program_enrollment, effective_date)
    return program_enrollment


def _append_history(
    pe_doc,
    from_status,
    to_status,
    category,
    reason,
    effective_date,
    source_doctype,
    source_name,
    notes,
):
    """Insert a status-history child row directly (submitted-doc safe)."""
    idx = (
        frappe.db.count(
            "Program Enrollment Status History",
            {"parent": pe_doc.name, "parentfield": "status_history"},
        )
        + 1
    )
    row = frappe.get_doc(
        {
            "doctype": "Program Enrollment Status History",
            "parent": pe_doc.name,
            "parenttype": "Program Enrollment",
            "parentfield": "status_history",
            "idx": idx,
            "effective_date": effective_date,
            "from_status": from_status,
            "to_status": to_status,
            "category": category,
            "reason": reason,
            "actor": frappe.session.user,
            "source_doctype": source_doctype,
            "source_name": source_name,
            "notes": notes,
        }
    )
    row.db_insert()


def _on_terminal(
    pe_doc, to_status, reason, effective_date, source_doctype=None, source_name=None
):
    """Side-effects shared by all terminal separations."""
    from seminary.seminary.graduation_request_lifecycle import (
        cascade_cancel_graduation_requests,
    )

    cascade_cancel_graduation_requests(pe_doc.name)

    # A terminal separation stops recurring billing for this enrollment.
    _set_payers_active(pe_doc.name, 0)

    # Record the student's leaving record for this program enrollment.
    if pe_doc.student:
        _upsert_leaving_record(
            pe_doc, to_status, effective_date, source_doctype, source_name
        )

    # Student standing / holds are applied in Phase 7 (see student_standing.py).
    try:
        from seminary.seminary.student_standing import apply_terminal_standing

        apply_terminal_standing(pe_doc, to_status, reason, effective_date)
    except ImportError:
        pass


def _upsert_leaving_record(
    pe_doc, to_status, effective_date, source_doctype, source_name
):
    """Create or update the Student Leaving Record for this Program Enrollment.

    One row per enrollment, keyed by program_enrollment. Written directly (no
    full Student save) so a terminal transition does not re-run the Student
    controller's customer sync. Mirrors the submitted-doc-safe child writes in
    ``_append_history`` and ``student_standing.add_hold``."""
    reason = _TERMINAL_REASON.get(to_status)
    withdrawal_request = source_name if source_doctype == "Withdrawal Request" else None

    existing = frappe.db.get_value(
        "Student Leaving Record",
        {
            "parent": pe_doc.student,
            "parentfield": "leaving_records",
            "program_enrollment": pe_doc.name,
        },
        "name",
    )
    if existing:
        frappe.db.set_value(
            "Student Leaving Record",
            existing,
            {
                "reason_for_leaving": reason,
                "date_of_leaving": effective_date,
                "withdrawal_request": withdrawal_request,
            },
            update_modified=False,
        )
        return

    idx = (
        frappe.db.count(
            "Student Leaving Record",
            {"parent": pe_doc.student, "parentfield": "leaving_records"},
        )
        + 1
    )
    frappe.get_doc(
        {
            "doctype": "Student Leaving Record",
            "parent": pe_doc.student,
            "parenttype": "Student",
            "parentfield": "leaving_records",
            "idx": idx,
            "program_enrollment": pe_doc.name,
            "program": pe_doc.program,
            "reason_for_leaving": reason,
            "date_of_leaving": effective_date,
            "withdrawal_request": withdrawal_request,
        }
    ).db_insert()


def _leave_policy(program):
    """Leave & readmission policy for a program's Program Level (or None)."""
    program_level = frappe.db.get_value("Program", program, "program_level")
    if not program_level:
        return None
    return frappe.db.get_value(
        "Program Level",
        program_level,
        [
            "loa_billing_suspension_days",
            "charges_readmission_fee",
            "readmission_fee_category",
        ],
        as_dict=True,
    )


def _evaluate_billing_suspension(pe_doc):
    """Set billing_suspended when a leave's known length exceeds the Program
    Level threshold. Open-ended leaves (no expected return) stay billed until
    the daily reconcile (reconcile_loa_billing) trips the threshold."""
    from frappe.utils import date_diff

    policy = _leave_policy(pe_doc.program)
    threshold = (policy or {}).get("loa_billing_suspension_days") or 0
    suspend = 0
    if threshold > 0 and pe_doc.inactiveuntil and pe_doc.loa_start_date:
        if date_diff(pe_doc.inactiveuntil, pe_doc.loa_start_date) > threshold:
            suspend = 1
    pe_doc.db_set("billing_suspended", suspend, update_modified=False)


def reconcile_loa_billing(today=None):
    """Daily: flip billing_suspended on leaves that have crossed the Program
    Level threshold (handles open-ended / extended leaves)."""
    from frappe.utils import date_diff

    today = getdate(today) if today else getdate()
    leaves = frappe.get_all(
        "Program Enrollment",
        filters={
            "status": LEAVE_STATUS,
            "billing_suspended": 0,
            "loa_start_date": ("is", "set"),
        },
        fields=["name", "program", "loa_start_date"],
    )
    for pe in leaves:
        policy = _leave_policy(pe.program)
        threshold = (policy or {}).get("loa_billing_suspension_days") or 0
        if threshold > 0 and date_diff(today, pe.loa_start_date) > threshold:
            frappe.db.set_value(
                "Program Enrollment",
                pe.name,
                "billing_suspended",
                1,
                update_modified=False,
            )
    frappe.db.commit()


def _maybe_charge_readmission(pe_doc, effective_date):
    """Fire a Readmission fee on return from leave when the Program Level is
    configured to charge one."""
    policy = _leave_policy(pe_doc.program)
    if not policy or not policy.get("charges_readmission_fee"):
        return
    fee_category = policy.get("readmission_fee_category")
    if not fee_category:
        return
    from seminary.seminary.api import generate_readmission_invoice

    generate_readmission_invoice(pe_doc.name, fee_category, effective_date)
