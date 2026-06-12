# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""First-class scholarships: budget availability, portal application, retention.

Scholarships are a reusable *template* (`Scholarships`) plus a per-enrollment
*award* (`Scholarship Award`). Discounts are computed at invoice time
(``billing.resolve_scholarship``); this module owns everything around the award
lifecycle that is *not* invoice construction: how much budget is left, what the
portal may offer, granting a request, and the daily retention review.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from seminary.seminary.doctype.scholarship_award.scholarship_award import (
    ACTIVE_STATE,
    OCCUPYING_STATES,
    get_active_award,
)


# --------------------------------------------------------------------------
# Budget / availability
# --------------------------------------------------------------------------
def _current_fiscal_year():
    """(name, start_date, end_date) of the fiscal year containing today."""
    from erpnext.accounts.utils import get_fiscal_year

    fy = get_fiscal_year(today())
    return fy[0], fy[1], fy[2]


def _budget_ceiling(cost_center, fy_name):
    """Sum of ERPNext Budget amounts against a cost center for the fiscal year.
    0 means no budget configured = unlimited."""
    if not cost_center:
        return 0
    rows = frappe.get_all(
        "Budget",
        filters={
            "budget_against": "Cost Center",
            "cost_center": cost_center,
            "from_fiscal_year": fy_name,
            "docstatus": ["<", 2],
        },
        pluck="budget_amount",
    )
    return sum(flt(r) for r in rows)


def _given_on_cost_center(cost_center, fy_start, fy_end):
    """Gross forgiveness booked to a cost center this fiscal year. Read from the
    scholarship-customer invoices' gross (base_total) because the forgiveness is
    100%-discounted and nets ~0 in the GL (so ERPNext's own budget-vs-actual
    wouldn't see it)."""
    if not cost_center:
        return 0
    sch_customer = frappe.db.get_single_value("Seminary Settings", "scholarship_cust")
    if not sch_customer:
        return 0
    val = frappe.db.sql(
        """
        SELECT COALESCE(SUM(base_total), 0)
        FROM `tabSales Invoice`
        WHERE customer = %s AND cost_center = %s
          AND docstatus < 2 AND is_return = 0
          AND posting_date BETWEEN %s AND %s
        """,
        (sch_customer, cost_center, fy_start, fy_end),
    )
    return flt(val[0][0]) if val else 0


def _pending_requests_value(scholarship_names, start, end):
    """(value, count) of pending scholarship requests (Submitted / Under Review)
    whose effective_from falls in a period, for templates on a cost center.

    Only Flat award terms can be dollar-valued before invoicing; percent requests
    are counted but contribute no estimated amount (their cost depends on future
    enrolment), so the count surfaces the pipeline even when the value can't."""
    if not scholarship_names:
        return 0, 0
    awards = frappe.get_all(
        "Scholarship Award",
        filters={
            "scholarship": ["in", scholarship_names],
            "workflow_state": ["in", ["Submitted", "Under Review"]],
            "effective_from": ["between", [start, end]],
        },
        pluck="name",
    )
    value = 0
    for name in awards:
        flat = frappe.db.sql(
            """SELECT COALESCE(SUM(value), 0) FROM `tabScholarship Award Term`
               WHERE parent = %s AND mode = 'Flat'""",
            (name,),
        )
        value += flt(flat[0][0]) if flat else 0
    return value, len(awards)


@frappe.whitelist()
def get_scholarship_availability(scholarship):
    """Budget/slot availability for a scholarship template.

    Returns ceiling/given/remaining (currency, per the template's cost center for
    the current fiscal year) and slots_total/slots_used (headcount), plus an
    ``is_open`` flag the portal uses to enable/disable Apply.
    """
    tpl = frappe.db.get_value(
        "Scholarships",
        scholarship,
        ["cost_center", "budget_slots", "is_active"],
        as_dict=True,
    )
    if not tpl:
        frappe.throw(_("Scholarship {0} not found.").format(scholarship))

    cost_center = tpl.cost_center or frappe.db.get_single_value(
        "Seminary Settings", "scholarship_cc"
    )
    fy_name, fy_start, fy_end = _current_fiscal_year()
    ceiling = _budget_ceiling(cost_center, fy_name)
    given = _given_on_cost_center(cost_center, fy_start, fy_end)
    remaining = (ceiling - given) if ceiling else None

    slots_total = int(tpl.budget_slots or 0)
    slots_used = frappe.db.count(
        "Scholarship Award",
        {"scholarship": scholarship, "workflow_state": ACTIVE_STATE},
    )

    slots_ok = slots_total == 0 or slots_used < slots_total
    money_ok = (not ceiling) or remaining > 0
    is_open = bool(tpl.is_active) and slots_ok and money_ok

    return {
        "scholarship": scholarship,
        "cost_center": cost_center,
        "ceiling": ceiling,
        "given": given,
        "remaining": remaining,
        "slots_total": slots_total,
        "slots_used": slots_used,
        "is_open": is_open,
    }


# --------------------------------------------------------------------------
# Portal: what a student may see / apply for
# --------------------------------------------------------------------------
def _student_active_enrollments(student):
    return frappe.get_all(
        "Program Enrollment",
        filters={"student": student, "pgmenrol_active": 1},
        fields=["name", "program"],
    )


@frappe.whitelist()
def get_student_scholarship(student):
    """The student's current award(s) with retention info, for the Fees page.

    Each award carries its retention thresholds (min GPA / min credits per term)
    plus the student's current GPA and current-term credits, so the portal can
    show what's needed to keep the award and how the student is tracking. Returns
    a list (the existing Fees.vue shape reads ``[0]``)."""
    awards = frappe.get_all(
        "Scholarship Award",
        filters={"student": student, "workflow_state": ACTIVE_STATE},
        fields=[
            "name",
            "scholarship",
            "scholarship_type",
            "program_enrollment",
            "retention_status",
            "retention_note",
            "effective_from",
            "effective_to",
        ],
        order_by="effective_from desc",
    )
    term = _retention_term()
    for a in awards:
        crit = (
            frappe.db.get_value(
                "Scholarships",
                a.scholarship,
                ["retain_min_credits_per_term", "retain_min_gpa"],
                as_dict=True,
            )
            or frappe._dict()
        )
        a["retain_min_credits_per_term"] = int(crit.retain_min_credits_per_term or 0)
        a["retain_min_gpa"] = flt(crit.retain_min_gpa or 0)
        a["current_gpa"] = flt(
            frappe.db.get_value(
                "Program Enrollment", a.program_enrollment, "current_gpa"
            )
        )
        a["current_term_credits"] = _term_credits(a.program_enrollment, term)
    return awards


@frappe.whitelist()
def get_available_scholarships(student):
    """Scholarships the student could apply for on the portal. Double-gated: the
    global Seminary Settings toggle AND the template's own ``show_on_portal`` must
    both be on, the template must be open (budget/slots), the student must have an
    active enrollment in the template's program, and not already hold/await an award
    on that enrollment.
    """
    if not frappe.db.get_single_value("Seminary Settings", "allow_portal_scholarship"):
        return []

    enrollments = _student_active_enrollments(student)
    if not enrollments:
        return []

    programs = {e.program for e in enrollments if e.program}
    if not programs:
        return []

    # The enrollment slot is taken if any award for it is active or pending.
    taken_programs = set()
    for e in enrollments:
        if frappe.db.exists(
            "Scholarship Award",
            {
                "program_enrollment": e.name,
                "workflow_state": ["in", OCCUPYING_STATES],
            },
        ):
            taken_programs.add(e.program)

    out = []
    templates = frappe.get_all(
        "Scholarships",
        filters={
            "program": ["in", list(programs)],
            "show_on_portal": 1,
            "is_active": 1,
        },
        fields=[
            "name",
            "scholarship",
            "program",
            "scholarship_type",
            "notes",
            "min_gpa",
            "min_credits_total",
            "retain_min_credits_per_term",
            "retain_min_gpa",
        ],
    )
    enr_by_program = {e.program: e.name for e in enrollments}
    for t in templates:
        if t.program in taken_programs:
            continue
        avail = get_scholarship_availability(t.name)
        if not avail["is_open"]:
            continue
        program_enrollment = enr_by_program.get(t.program)
        # Pre-compute eligibility so the portal can disable + label the Apply button
        # instead of letting apply_for_scholarship throw (which surfaces as a console
        # error). Budget figures are intentionally not returned to students.
        reasons = _check_granting_criteria(program_enrollment, t.name)
        out.append(
            {
                **t,
                "program_enrollment": program_enrollment,
                "eligible": not reasons,
                "ineligible_reasons": reasons,
            }
        )
    return out


def _check_granting_criteria(program_enrollment, scholarship):
    """Best-effort eligibility check against the template's granting criteria.
    Returns a list of human-readable failures (empty = eligible)."""
    crit = frappe.db.get_value(
        "Scholarships", scholarship, ["min_gpa", "min_credits_total"], as_dict=True
    )
    if not crit:
        return []
    pe = (
        frappe.db.get_value(
            "Program Enrollment",
            program_enrollment,
            ["current_gpa", "totalcredits"],
            as_dict=True,
        )
        or frappe._dict()
    )
    fails = []
    if crit.min_gpa and flt(pe.current_gpa) < flt(crit.min_gpa):
        fails.append(
            _("Minimum GPA {0} required (current {1}).").format(
                crit.min_gpa, flt(pe.current_gpa)
            )
        )
    if crit.min_credits_total and int(pe.totalcredits or 0) < int(
        crit.min_credits_total
    ):
        fails.append(
            _("Minimum {0} total credits required (current {1}).").format(
                crit.min_credits_total, int(pe.totalcredits or 0)
            )
        )
    return fails


@frappe.whitelist()
def apply_for_scholarship(program_enrollment, scholarship, comment=None):
    """Student-facing: create a Scholarship Award request (Draft → Submitted).
    Enforces both portal gates, availability, the one-award-per-enrollment rule,
    and basic granting criteria."""
    if not frappe.db.get_single_value("Seminary Settings", "allow_portal_scholarship"):
        frappe.throw(_("Scholarship applications are not enabled."))

    tpl = frappe.db.get_value(
        "Scholarships",
        scholarship,
        ["show_on_portal", "is_active", "program"],
        as_dict=True,
    )
    if not tpl or not tpl.show_on_portal or not tpl.is_active:
        frappe.throw(_("This scholarship is not available for application."))

    pe = frappe.db.get_value(
        "Program Enrollment",
        program_enrollment,
        ["program", "student", "pgmenrol_active"],
        as_dict=True,
    )
    if not pe or not pe.pgmenrol_active:
        frappe.throw(_("Program Enrollment is not active."))
    if pe.program != tpl.program:
        frappe.throw(_("This scholarship does not apply to your program."))

    if frappe.db.exists(
        "Scholarship Award",
        {
            "program_enrollment": program_enrollment,
            "workflow_state": ["in", OCCUPYING_STATES],
        },
    ):
        frappe.throw(
            _("You already have an active or pending scholarship on this enrollment.")
        )

    if not get_scholarship_availability(scholarship)["is_open"]:
        frappe.throw(_("This scholarship has no remaining budget or slots."))

    fails = _check_granting_criteria(program_enrollment, scholarship)
    if fails:
        frappe.throw(_("You do not meet the requirements: {0}").format(" ".join(fails)))

    award = frappe.new_doc("Scholarship Award")
    award.scholarship = scholarship
    award.program_enrollment = program_enrollment
    award.student_comment = comment
    award.applied_on = frappe.utils.now()
    award.flags.ignore_permissions = True
    # Insert in the default Draft state, then advance to Submitted via db_set —
    # the system files the request on the student's behalf, bypassing
    # apply_workflow's per-user transition gate (ADR 013 system-driven pattern).
    award.insert()
    award.db_set("workflow_state", "Submitted")
    return award.name


# --------------------------------------------------------------------------
# Retention review (daily scheduler)
# --------------------------------------------------------------------------
def _current_academic_term():
    return frappe.db.get_value("Academic Term", {"iscurrent_acterm": 1}, "name")


def _retention_term():
    """Term to measure 'credits this term' against for display/reporting: the
    flagged current term, else the most recently started term (so the figure stays
    meaningful in the gap between terms). The auto-flagging review still uses
    _current_academic_term, so it only acts while a term is genuinely current."""
    cur = _current_academic_term()
    if cur:
        return cur
    recent = frappe.get_all(
        "Academic Term",
        filters={"term_start_date": ["<=", today()]},
        order_by="term_start_date desc",
        limit=1,
        pluck="name",
    )
    return recent[0] if recent else None


def _term_credits(program_enrollment, academic_term):
    """Credit hours the student is currently enrolled in for the term (active,
    non-withdrawn course enrollments)."""
    if not academic_term:
        return 0
    val = frappe.db.sql(
        """
        SELECT COALESCE(SUM(credits), 0)
        FROM `tabCourse Enrollment Individual`
        WHERE program_ce = %s AND academic_term = %s
          AND docstatus = 1 AND IFNULL(withdrawn, 0) = 0
          AND IFNULL(course_cancelled, 0) = 0
        """,
        (program_enrollment, academic_term),
    )
    return int(val[0][0]) if val else 0


def _notify_registrars(award, message):
    """Drop a Notification Log to every Registrar so an at-risk award gets a human
    review (retention never auto-revokes)."""
    users = frappe.get_all(
        "Has Role",
        filters={"role": "Registrar", "parenttype": "User"},
        pluck="parent",
    )
    for user in set(users):
        if user in ("Administrator", "Guest"):
            continue
        try:
            frappe.get_doc(
                {
                    "doctype": "Notification Log",
                    "subject": _("Scholarship at risk: {0}").format(award),
                    "email_content": message,
                    "for_user": user,
                    "type": "Alert",
                    "document_type": "Scholarship Award",
                    "document_name": award,
                }
            ).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "scholarship retention notify")


def review_scholarship_retention(review_date=None):
    """Daily: flag (never revoke) active awards that fail their retention criteria.

    Checks min credits per term and min GPA from the template, plus active
    employment for Work-Study awards when HRMS is enabled. Sets retention_status to
    'At Risk' and notifies registrars; clears back to 'OK' when criteria are met
    again (unless a human set it to 'Under Review').
    """
    review_date = getdate(review_date or today())
    hrms_enabled = frappe.db.get_single_value("Seminary Settings", "hrms_enable")
    term = _current_academic_term()

    awards = frappe.get_all(
        "Scholarship Award",
        filters={"workflow_state": ACTIVE_STATE},
        fields=[
            "name",
            "scholarship",
            "scholarship_type",
            "program_enrollment",
            "employee",
            "retention_status",
        ],
    )
    for a in awards:
        crit = (
            frappe.db.get_value(
                "Scholarships",
                a.scholarship,
                ["retain_min_credits_per_term", "retain_min_gpa"],
                as_dict=True,
            )
            or frappe._dict()
        )
        reasons = []

        min_credits = int(crit.retain_min_credits_per_term or 0)
        if min_credits and term:
            credits = _term_credits(a.program_enrollment, term)
            if credits < min_credits:
                reasons.append(
                    _("Enrolled in {0} credits this term; {1} required.").format(
                        credits, min_credits
                    )
                )

        min_gpa = flt(crit.retain_min_gpa)
        if min_gpa:
            gpa = flt(
                frappe.db.get_value(
                    "Program Enrollment", a.program_enrollment, "current_gpa"
                )
            )
            if gpa < min_gpa:
                reasons.append(
                    _("GPA {0} below the {1} required.").format(gpa, min_gpa)
                )

        if hrms_enabled and a.scholarship_type == "Work-Study" and a.employee:
            emp_status = frappe.db.get_value("Employee", a.employee, "status")
            if emp_status and emp_status != "Active":
                reasons.append(
                    _("Employee {0} is {1} (not Active).").format(
                        a.employee, emp_status
                    )
                )

        _apply_retention_result(a, reasons, review_date)


def _apply_retention_result(award_row, reasons, review_date):
    note = " ".join(reasons)
    if reasons:
        if award_row.retention_status != "At Risk":
            frappe.db.set_value(
                "Scholarship Award",
                award_row.name,
                {
                    "retention_status": "At Risk",
                    "retention_note": note,
                    "last_reviewed_on": review_date,
                },
            )
            doc = frappe.get_doc("Scholarship Award", award_row.name)
            doc.add_comment("Comment", _("Retention at risk: {0}").format(note))
            _notify_registrars(award_row.name, note)
        else:
            frappe.db.set_value(
                "Scholarship Award",
                award_row.name,
                {"retention_note": note, "last_reviewed_on": review_date},
                update_modified=False,
            )
    else:
        # Criteria met. Clear an automatic 'At Risk' back to OK, but don't override a
        # registrar-set 'Under Review'.
        if award_row.retention_status == "At Risk":
            frappe.db.set_value(
                "Scholarship Award",
                award_row.name,
                {
                    "retention_status": "OK",
                    "retention_note": "",
                    "last_reviewed_on": review_date,
                },
            )
        else:
            frappe.db.set_value(
                "Scholarship Award",
                award_row.name,
                "last_reviewed_on",
                review_date,
                update_modified=False,
            )
