import frappe
from frappe.utils import getdate

from seminary.seminary.api import (
    generate_monthly_invoices,
    generate_nat_invoices,
    generate_nay_invoices,
)

# Scheduler hooks — see hooks.py scheduler_events
# Documentation: https://frappeframework.com/docs/user/en/api/background_jobs


@frappe.whitelist()
def daily():
    today = getdate()

    _update_term_flags(today)
    _flag_overdue_milestones(today)
    _process_program_separations()
    _reconcile_loa(today)

    if frappe.db.get_single_value("Seminary Settings", "billing_automation_enabled"):
        _run_nat_for_due_terms(today)
        _run_nay_for_due_years(today)
        if today.day == 1:
            generate_monthly_invoices(today)

    if frappe.db.get_single_value("Seminary Settings", "auto_advance_course_schedule"):
        from seminary.seminary.cs_lifecycle import (
            advance_due_course_schedules,
            nag_late_graders,
        )

        advance_due_course_schedules(today)
        nag_late_graders(today)


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

    Student advancement is NOT done here — that's a manual action in
    api.roll_students, so a registrar can verify grades first."""
    terms = frappe.get_all(
        "Academic Term",
        fields=["name", "term_start_date", "term_end_date", "iscurrent_acterm", "open"],
    )
    had_current = False
    for t in terms:
        if t.term_end_date < today:
            if t.open:
                frappe.db.set_value("Academic Term", t.name, "open", 0)
            if t.iscurrent_acterm:
                frappe.db.set_value("Academic Term", t.name, "iscurrent_acterm", 0)
        elif t.term_start_date <= today <= t.term_end_date:
            if not t.iscurrent_acterm:
                frappe.db.set_value("Academic Term", t.name, "iscurrent_acterm", 1)
            if not t.open:
                frappe.db.set_value("Academic Term", t.name, "open", 1)
            had_current = True

    if not had_current:
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


def _run_nat_for_due_terms(today):
    due = frappe.db.get_all(
        "Academic Term",
        filters={
            "term_start_date": ["<=", today],
            "invoiced_nat_on": ["is", "not set"],
        },
        pluck="name",
    )
    for term in due:
        generate_nat_invoices(term)


def _run_nay_for_due_years(today):
    due = frappe.db.get_all(
        "Academic Year",
        filters={
            "year_start_date": ["<=", today],
            "invoiced_nay_on": ["is", "not set"],
        },
        pluck="name",
    )
    for year in due:
        generate_nay_invoices(year)


def _maybe_warn_need_acadterm(today):
    outgoing_email = frappe.db.get_all("Email Account", {"enable_outgoing": 1}, "name")
    if not outgoing_email:
        return

    future_terms = frappe.db.count("Academic Term", {"term_start_date": [">=", today]})
    if future_terms >= 2:
        return

    user_roles = frappe.db.sql(
        """SELECT DISTINCT parent FROM `tabUserRole` WHERE role = 'Academics User'""",
        as_dict=True,
    )
    usernames = [r["parent"] for r in user_roles]
    if not usernames:
        frappe.log_error(
            "No users found with the Academics User role.", "Need Academic Term"
        )
        return

    users = frappe.db.sql(
        "SELECT email FROM `tabUser` WHERE name IN ({})".format(
            ", ".join(["%s"] * len(usernames))
        ),
        tuple(usernames),
    )
    subject = "Few Academic Terms"
    body = (
        f"There are only {future_terms} academic terms in the pipeline. "
        "Please create more to avoid disruptions."
    )
    for (email,) in users:
        try:
            frappe.sendmail(recipients=email, subject=subject, message=body)
        except Exception as e:
            frappe.log_error(
                f"Failed to send email to {email}: {str(e)}", "Need Academic Term"
            )
