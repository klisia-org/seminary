import frappe
from frappe.utils import getdate

# Scheduler hooks — see hooks.py scheduler_events
# Documentation: https://frappeframework.com/docs/user/en/api/background_jobs


@frappe.whitelist()
def daily():
    today = getdate()

    _update_term_flags(today)
    _flag_overdue_milestones(today)
    _process_program_separations()
    _reconcile_loa(today)

    from seminary.seminary.attendance import recompute_all

    recompute_all()

    # Automatic billing (NAT / NAY / monthly invoices) is driven by the oikonomos
    # bridge's own daily scheduler task (oikonomos.financial.invoicing.
    # run_billing_automation); seminary's scheduler stays purely academic.

    if frappe.db.get_single_value("Seminary Settings", "auto_advance_course_schedule"):
        from seminary.seminary.cs_lifecycle import (
            advance_due_course_schedules,
            nag_late_graders,
        )

        advance_due_course_schedules(today)
        nag_late_graders(today)

    from seminary.seminary.comms import process_follow_ups

    process_follow_ups()

    # Scholarship retention review is an oikonomos (financial) concern — it runs
    # from the bridge's own daily scheduler task
    # (oikonomos.financial.scholarship.review_scholarship_retention).


@frappe.whitelist()
def hourly():
    from seminary.seminary.doctype.seminary_announcement.seminary_announcement import (
        process_scheduled_announcements,
    )

    process_scheduled_announcements()


def refresh_term_flags_on_save(doc, method=None):
    _update_term_flags(getdate())


def _update_term_flags(today):
    """Flip Academic Term.iscurrent_acterm / open based on today's date.

    `iscurrent_acterm` names *the* current term, singular — one app-wide answer
    that everything else reads. So this sets it exclusively: it picks the one
    term covering today and clears the flag on every other term, rather than
    setting the winner and hoping the losers get cleared by some other branch.
    The old version only cleared a term whose end date had passed, which left a
    flag on a *future* term untouched for as long as it stayed future.

    Student advancement is NOT done here — that's a manual action in
    api.roll_students, so a registrar can verify grades first."""
    terms = frappe.get_all(
        "Academic Term",
        fields=["name", "term_start_date", "term_end_date", "iscurrent_acterm", "open"],
        order_by="term_start_date asc",
    )

    # Overlapping term dates are a data error, not a case to model: if two cover
    # today the earlier one wins, deterministically, so the answer does not
    # depend on row order.
    current = next(
        (
            t.name
            for t in terms
            if t.term_start_date
            and t.term_end_date
            and t.term_start_date <= today <= t.term_end_date
        ),
        None,
    )

    for t in terms:
        should_be_current = 1 if t.name == current else 0
        if int(t.iscurrent_acterm or 0) != should_be_current:
            frappe.db.set_value(
                "Academic Term", t.name, "iscurrent_acterm", should_be_current
            )

        # `open` is a separate question: a term that has ended is closed, one
        # that is running is open, and a future term's enrollment window is the
        # registrar's to decide.
        if t.term_end_date and t.term_end_date < today:
            if t.open:
                frappe.db.set_value("Academic Term", t.name, "open", 0)
        elif t.name == current and not t.open:
            frappe.db.set_value("Academic Term", t.name, "open", 1)

    if not current:
        _maybe_warn_need_acadterm(today)


def _flag_overdue_milestones(today):
    """Mark culminating-project milestones past their due date as Overdue.

    Only open milestones move (Approved / Waived / already-Overdue are left
    alone). The milestones table is allow_on_submit, so a direct update is safe."""
    frappe.db.sql(
        """UPDATE `tabCulminating Project Milestone`
           SET status = 'Overdue'
           WHERE status IN ('Not Started', 'In Progress', 'Submitted')
             AND due_date IS NOT NULL
             AND due_date < %s""",
        (today,),
    )


def _process_program_separations():
    """Spawn course withdrawals for deferred program separations now due."""
    from seminary.seminary.withdrawal import process_due_separations

    process_due_separations()


def _reconcile_loa(today):
    """Flip billing_suspended on leaves that have crossed the Program Level
    suspension threshold (see Phase 6 / ADR 033)."""
    from seminary.seminary.program_status import reconcile_loa_billing

    reconcile_loa_billing(today)


def _maybe_warn_need_acadterm(today):
    from seminary.seminary import comms

    future_terms = frappe.db.count("Academic Term", {"term_start_date": [">=", today]})
    if future_terms >= 2:
        return

    # One nag per (term-count, registrar): the dedupe key keeps the daily task
    # from re-mailing every day while the count stays the same, but a further
    # drop (or a registrar fixing it and it dropping again later) re-fires.
    comms.send_to_role(
        "Registrar",
        "few-academic-terms",
        context={"count": future_terms},
        triggered_by="need-academic-term",
        dedupe_prefix=f"few-academic-terms::{future_terms}",
    )
