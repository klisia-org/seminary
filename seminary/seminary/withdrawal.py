import frappe
from frappe import _


def on_withdrawal_workflow_update(doc, method=None):
    """Fire withdrawal side effects for 1->1 workflow transitions.

    Registered on ``on_update_after_submit``. The 0->1 fast-path submits (an
    ongoing program going Draft -> Financial Review / Completed) don't reach
    this hook — Frappe fires ``on_submit`` there instead — so the controller's
    on_submit calls :func:`dispatch_withdrawal_effects` for those.
    """
    dispatch_withdrawal_effects(doc)


def dispatch_withdrawal_effects(doc):
    """Apply academic/financial/completion side effects based on the transition
    just taken, derived from (previous state -> current state).

    The Course Withdrawal workflow (5 states) binds effects to the *transition*,
    not the resulting state, because:
      - The academic decision can land in either Financial Review (a refund is
        due) or Completed (the no-refund "Approve Academically & Conclude"
        fast-track), so it can't key on a single state.
      - Completed is reachable three ways: via Financial Review (finance just
        decided -> apply financial), via the academic Conclude (academic not yet
        applied), or via an ongoing-program Draft fast-path (likewise).

    Parents of a program separation carry no single CEI; their children apply
    the per-CEI academic/financial effects, so we only run process_completion
    for them (it is internally gated on every child being Completed).
    """
    before = doc.get_doc_before_save()
    prev_state = before.workflow_state if before else None
    cur = doc.workflow_state
    is_parent = bool(doc.is_parent)

    if cur == "Financial Review":
        # Academic decision applied; finance pending.
        if not is_parent:
            process_academic_approval(doc)
    elif cur == "Completed":
        if prev_state == "Financial Review":
            # Academic already applied on entry to Financial Review; only the
            # financial decision remains. Refunds (credit notes) are owned by the
            # oikonomos bridge; with no bridge installed this is a no-op.
            if not is_parent:
                from seminary.seminary.financial.backend import get_financial_backend

                get_financial_backend().process_withdrawal_refunds(doc)
        else:
            # Concluded without a Financial Review stop (no refund due): the
            # academic effect has not run yet.
            if not is_parent:
                process_academic_approval(doc)
        process_completion(doc)
    # Draft, Academic Review, Rejected: no side effects.


def process_academic_approval(doc):
    """Apply the withdrawal rule's grade treatment to the academic record.

    Treatments:
      - Clean Drop: delete roster and PEC rows so no transcript record remains.
        The Withdrawal Request is the audit trail.
      - Flat Symbol: write the rule's transcript_symbol (e.g. "W") to the roster
        and PEC. count_in_gpa = 0 (no numeric, not in GPA).
      - Calculated As-Is: run grade_thisstudent + fgrade_this_std (ungraded work
        sums as 0). Use the calculated letter and numeric directly. count_in_gpa = 1.
      - Calculated WP/WF: same calculation, then look up wp_code / wf_code on the
        course's Grading Scale by Pass/Fail. count_in_gpa follows wp_gpa / wf_gpa
        on the scale. The numeric (fscore) is preserved on PEC for transcript truth.
    """
    from seminary.seminary.api import grade_thisstudent, fgrade_this_std
    from seminary.seminary.gpa import recompute_program_enrollment_gpa

    doc.academic_processed_by = frappe.session.user

    # Ongoing programs reach this via the workflow's "Submit & Approve
    # Academically" / "Submit & Conclude" fast-paths. They have no transcript/GPA
    # concept, so short-circuit any grade-treatment work and just mark the CEI
    # withdrawn.
    if doc.is_ongoing:
        _mark_cei_withdrawn(doc.course_enrollment_individual, doc.name)
        return

    cei = doc.course_enrollment_individual
    course_schedule = frappe.db.get_value(
        "Course Enrollment Individual", cei, "coursesc_ce"
    )
    student = frappe.db.get_value("Course Enrollment Individual", cei, "student_ce")

    # No withdrawal rule resolved for this term (none configured, or none
    # applies to the effective date). The institution defined no grade
    # treatment, so fall back to a Clean Drop instead of doing nothing —
    # otherwise a Completed withdrawal would leave the student Submitted and on
    # the roster, never freeing the seat (and never promoting the waitlist).
    if not doc.withdrawal_rule:
        frappe.db.delete(
            "Scheduled Course Roster",
            {"course_sc": course_schedule, "student": student},
        )
        frappe.db.delete(
            "Program Enrollment Course",
            {"course": course_schedule, "parent": doc.program_enrollment},
        )
        _mark_cei_withdrawn(cei, doc.name)
        recompute_program_enrollment_gpa(doc.program_enrollment)
        return

    rule = frappe.get_doc("Withdrawal Rules", doc.withdrawal_rule)
    treatment = rule.grade_treatment

    if treatment == "Clean Drop":
        frappe.db.delete(
            "Scheduled Course Roster",
            {"course_sc": course_schedule, "student": student},
        )
        frappe.db.delete(
            "Program Enrollment Course",
            {"course": course_schedule, "parent": doc.program_enrollment},
        )
        _mark_cei_withdrawn(cei, doc.name)
        recompute_program_enrollment_gpa(doc.program_enrollment)
        return

    roster_name = frappe.db.get_value(
        "Scheduled Course Roster",
        {"course_sc": course_schedule, "student": student},
        "name",
    )
    pec = frappe.db.get_value(
        "Program Enrollment Course",
        {"course": course_schedule, "parent": doc.program_enrollment},
        "name",
    )

    if treatment == "Flat Symbol":
        symbol = rule.transcript_symbol or ""
        if roster_name:
            frappe.db.set_value(
                "Scheduled Course Roster",
                roster_name,
                {
                    "active": 0,
                    "fgrade": symbol,
                    "fgradepass": "Withdrawn",  # nosec B105
                },
            )
        if pec:
            frappe.db.set_value(
                "Program Enrollment Course",
                pec,
                {
                    "pec_finalgradecode": symbol,
                    "status": "Withdrawn",  # nosec B105
                    "count_in_gpa": 0,
                },
            )
        doc.db_set("resulting_grade", symbol, update_modified=False)
        _mark_cei_withdrawn(cei, doc.name)
        recompute_program_enrollment_gpa(doc.program_enrollment)
        return

    # Calculated * — needs a roster to score against.
    if not roster_name:
        return

    grade_thisstudent(roster_name)
    fgrade_this_std(roster_name)
    fscore, calc_grade, fgradepass = frappe.db.get_value(
        "Scheduled Course Roster",
        roster_name,
        ["fscore", "fgrade", "fgradepass"],
    )

    final_code = calc_grade
    count_in_gpa = 1
    if treatment == "Calculated WP/WF":
        gscale_name = frappe.db.get_value(
            "Course Schedule", course_schedule, "gradesc_cs"
        )
        if gscale_name:
            scale = frappe.get_cached_doc("Grading Scale", gscale_name)
            if fgradepass == "Pass" and scale.wp_code:
                final_code = scale.wp_code
                count_in_gpa = 1 if scale.wp_gpa else 0
            elif fgradepass == "Fail" and scale.wf_code:
                final_code = scale.wf_code
                count_in_gpa = 1 if scale.wf_gpa else 0

    frappe.db.set_value(
        "Scheduled Course Roster",
        roster_name,
        {
            "active": 0,
            "fgrade": final_code,
            "fgradepass": "Withdrawn",  # nosec B105
        },
    )
    if pec:
        frappe.db.set_value(
            "Program Enrollment Course",
            pec,
            {
                "pec_finalgradecode": final_code,
                "pec_finalgradenum": fscore,
                "status": "Withdrawn",  # nosec B105
                "count_in_gpa": count_in_gpa,
            },
        )
    doc.db_set("resulting_grade", final_code, update_modified=False)
    _mark_cei_withdrawn(cei, doc.name)
    recompute_program_enrollment_gpa(doc.program_enrollment)


def _mark_cei_withdrawn(cei, withdrawal_request):
    frappe.db.set_value(
        "Course Enrollment Individual",
        cei,
        {
            "withdrawn": 1,
            "withdrawal_request": withdrawal_request,
            "workflow_state": "Withdrawn",
        },
    )
    # A withdrawal frees a seat — refresh the section's caches and auto-promote
    # the next waitlisted student if a seat is now open. (db.set_value above
    # bypasses on_update_after_submit, so the promotion can't ride that hook.)
    from seminary.seminary.waitlist import recount_and_promote

    course_schedule = frappe.db.get_value(
        "Course Enrollment Individual", cei, "coursesc_ce"
    )
    recount_and_promote(course_schedule)


def process_completion(doc):
    """Handle final completion.

    A Full Program Withdrawal flips the Program Enrollment to a terminal status
    once all of its child course withdrawals are Completed. The status change
    goes through the shared spine (set_program_status), which records history,
    keeps pgmenrol_active in sync, and runs the graduation-request cascade.
    """
    # A completing child course withdrawal may be the last piece of a program
    # separation — re-check its parent (handles completing the parent before
    # its children, and vice-versa).
    if doc.has_parent and doc.parent_withdrawal:
        parent = frappe.get_doc("Withdrawal Request", doc.parent_withdrawal)
        if parent.withdrawal_scope == "Full Program Withdrawal" and parent.is_parent:
            finalize_program_separation(parent)
        return

    if doc.withdrawal_scope != "Full Program Withdrawal" or not doc.is_parent:
        return

    # Deferred separations (End of Current Term / Specific Date) must not
    # finalize until the daily scheduler has spawned the children on the
    # effective date. cascade_done==0 means the children don't exist yet.
    timing = getattr(doc, "separation_timing", "Immediate") or "Immediate"
    if timing != "Immediate" and not doc.cascade_done:
        return

    finalize_program_separation(doc)


def finalize_program_separation(doc):
    """Flip the Program Enrollment to its terminal status once the program
    separation parent AND every child course withdrawal are Completed. Safe to
    call from either the parent or a child completing (idempotent)."""
    if doc.workflow_state != "Completed":
        return

    children = frappe.get_all(
        "Withdrawal Request",
        filters={"parent_withdrawal": doc.name, "docstatus": 1},
        fields=["workflow_state"],
    )
    if not all(c.workflow_state == "Completed" for c in children):
        return

    # Idempotency: do nothing if the PE is already in a terminal status.
    pe_status = frappe.db.get_value(
        "Program Enrollment", doc.program_enrollment, "status"
    )
    if pe_status in ("Withdrawn", "Dismissed", "Graduated", "Transferred"):
        return

    from seminary.seminary.program_status import set_program_status

    to_status, category = _resolve_separation_target(doc)
    notes = _transfer_notes(doc) if to_status == "Transferred" else None
    effective_date = doc.separation_effective_date or doc.withdrawal_effective_date

    set_program_status(
        doc.program_enrollment,
        to_status=to_status,
        category=category,
        reason=doc.withdrawal_reason,
        effective_date=effective_date,
        source_doctype="Withdrawal Request",
        source_name=doc.name,
        notes=notes,
    )


def process_due_separations():
    """Daily: spawn course withdrawals for deferred program separations whose
    effective date has arrived. Idempotent via the cascade_done flag."""
    parents = frappe.get_all(
        "Withdrawal Request",
        filters={
            "withdrawal_scope": "Full Program Withdrawal",
            "is_parent": 1,
            "docstatus": 1,
            "cascade_done": 0,
            "separation_effective_date": ("<=", frappe.utils.today()),
        },
        pluck="name",
    )
    for name in parents:
        doc = frappe.get_doc("Withdrawal Request", name)
        if (doc.separation_timing or "Immediate") == "Immediate":
            continue
        doc.create_child_withdrawal_requests()
        doc.db_set("cascade_done", 1, update_modified=False)
        # If approvals are already complete (and children fast-pathed), finalize.
        if doc.workflow_state == "Completed":
            finalize_program_separation(doc)
    frappe.db.commit()


def _resolve_separation_target(doc):
    """Terminal PE status + history category for a completed program separation.

    Disciplinary dismissals carry an explicit separation_status/category set by
    the initiating path; voluntary/transfer separations derive from the
    withdrawal reason's category (Transfer -> Transferred)."""
    sep_status = getattr(doc, "separation_status", None)
    if sep_status:
        return sep_status, (
            getattr(doc, "separation_category", None) or "Administrative"
        )

    reason_category = (
        frappe.db.get_value("Withdrawal Reasons", doc.withdrawal_reason, "category")
        if doc.withdrawal_reason
        else None
    )
    if reason_category == "Transfer":
        return "Transferred", "Transfer"
    return "Withdrawn", (reason_category or "Voluntary")


def _transfer_notes(doc):
    """Compact snapshot of the transfer destination for the history row."""
    parts = []
    for field, label in (
        ("transfer_to_institution", "Institution"),
        ("transfer_to_program", "Program"),
        ("transfer_to_country", "Country"),
        ("destination_contact", "Contact"),
        ("transcript_sent_on", "Transcript sent"),
    ):
        val = getattr(doc, field, None)
        if val:
            parts.append(f"{label}: {val}")
    return "; ".join(parts) or None


@frappe.whitelist()
def get_withdrawal_rule_for_date(academic_term, effective_date):
    """Find the matching withdrawal rule for a given term and date."""
    term_rule = frappe.db.get_value(
        "Term Withdrawal Rules",
        filters={
            "academic_term": academic_term,
            "applies_until": (">=", effective_date),
        },
        fieldname=["name", "withdrawal_rule"],
        order_by="applies_until asc",
        as_dict=True,
    )
    if term_rule:
        return term_rule.withdrawal_rule
    return None


@frappe.whitelist()
def calculate_dynamic_date(withdrawal_rule, academic_term):
    """Calculate the applies_until date for a Term Withdrawal Rule based on the
    dynamic date fields. Date math runs through the shared `date_rules` resolver
    (ADR 025): days after term start, snapped to the following weekday, nudged
    off holidays, clamped to the term end."""
    from seminary.seminary import date_rules

    rule = frappe.get_doc("Withdrawal Rules", withdrawal_rule)
    term = frappe.get_doc("Academic Term", academic_term)

    if not rule.term_based_date or not rule.days_after_term_start:
        return None

    context = {
        "anchors": {"term_start": term.term_start_date},
        "holidays": _company_holidays(),
    }
    result = date_rules.resolve(
        "term_start",
        rule.days_after_term_start,
        "Days",
        context,
        weekday=rule.day_of_week,
        weekday_strict=True,
        holiday_adjust=rule.adjust_for_holidays,
        clamp_to=term.term_end_date,
    )
    return str(result) if result else None


def _company_holidays():
    """Holiday dates the withdrawal date-rule engine adjusts around. Owned by the
    financial backend (the ERPNext Company holiday list lives in the bridge);
    empty on a Frappe-only seminary."""
    from seminary.seminary.financial.backend import get_financial_backend

    return get_financial_backend().company_holiday_dates()
