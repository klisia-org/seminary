# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Internship subsystem helpers (ADR 054).

One place for the cross-doctype logic shared by Internship Application and
Internship Placement controllers: resolving the open graduation requirement
that gates eligibility, snapshotting requirement templates into instances with
computed due dates (reusing `date_rules.resolve`), and rolling logged hours up
from Hours Log -> Placement -> Application per the type's tracking mode.
"""

import frappe
from frappe.utils import getdate, today

from seminary.seminary import date_rules

OPEN_SGR_STATUSES = ("Not Started", "In Progress")
SUBMITTABLE_LOG = "Submittable Log"
CONFIRM_LOG = "Portal Daily Log with Supervisor Confirmation"

# Snapshot every party-set field from the template onto the instance so the
# instance is self-describing even if the template later changes.
_PARTY_FIELDS = ("label", "submission_type", "instructions")


# --------------------------------------------------------------------------- #
# Eligibility
# --------------------------------------------------------------------------- #
def resolve_open_requirement(student, internship_type):
    """Find the student's active Program Enrollment and an open graduation
    requirement row matching the type's graduation requirement item.

    Returns {"program_enrollment", "student_grad_requirement"} or None. When the
    type maps to no requirement item the internship is ungated -> returns None.
    """
    item = frappe.db.get_value(
        "Internship Type", internship_type, "graduation_requirement_item"
    )
    if not item or not student:
        return None

    enrollments = frappe.get_all(
        "Program Enrollment",
        filters={"student": student, "docstatus": 1, "pgmenrol_active": 1},
        pluck="name",
    )
    for pe in enrollments:
        row = frappe.get_all(
            "Student Graduation Requirement",
            filters={
                "parenttype": "Program Enrollment",
                "parent": pe,
                "grad_requirement_item": item,
                "status": ("in", OPEN_SGR_STATUSES),
            },
            fields=["name"],
            limit=1,
        )
        if row:
            return {"program_enrollment": pe, "student_grad_requirement": row[0].name}
    return None


# --------------------------------------------------------------------------- #
# Due-date context
# --------------------------------------------------------------------------- #
def build_due_context(application, placement=None):
    """Assemble the anchor dict that `date_rules.resolve` reads. 'Previous
    Requirement' is injected per-row while snapshotting."""
    anchors = {"Application Date": getdate(application.creation)}
    term = None

    if application.program_enrollment:
        pe = frappe.db.get_value(
            "Program Enrollment",
            application.program_enrollment,
            ["expected_graduation_date", "academic_term"],
            as_dict=True,
        )
        if pe:
            if pe.expected_graduation_date:
                anchors["Expected Graduation"] = getdate(pe.expected_graduation_date)
            term = pe.academic_term
            if pe.academic_term:
                start = frappe.db.get_value(
                    "Academic Term", pe.academic_term, "term_start_date"
                )
                if start:
                    anchors["Term Start"] = getdate(start)

    if placement:
        if placement.actual_start:
            anchors["Placement Start"] = getdate(placement.actual_start)
        if placement.actual_end:
            anchors["Placement End"] = getdate(placement.actual_end)

    return {"anchors": anchors, "term": term}


def _compute_due(template, context, prev_due):
    ctx = dict(context)
    ctx["anchors"] = dict(context["anchors"])
    if prev_due:
        ctx["anchors"]["Previous Requirement"] = getdate(prev_due)
    if not template.due_anchor:
        return None
    return date_rules.resolve(
        template.due_anchor,
        template.due_offset_value,
        template.due_offset_unit,
        ctx,
    )


# --------------------------------------------------------------------------- #
# Snapshotting templates -> instances
# --------------------------------------------------------------------------- #
def snapshot_application_requirements(application):
    """Instantiate the type's Application-scope templates onto the application
    (idempotent)."""
    _snapshot(application, scope="Application", placement=None)


def snapshot_placement_requirements(placement):
    """Instantiate the type's Placement-scope templates onto a placement
    (idempotent)."""
    application = frappe.get_doc(
        "Internship Application", placement.internship_application
    )
    _snapshot(application, scope="Placement", placement=placement)


def _snapshot(application, scope, placement):
    templates = frappe.get_all(
        "Internship Requirement Template",
        filters={"internship_type": application.internship_type, "scope": scope},
        fields=["*"],
        order_by="sequence asc, creation asc",
    )
    if not templates:
        return

    context = build_due_context(application, placement)
    prev_due = None
    for tmpl in templates:
        filters = {
            "requirement_template": tmpl.name,
            "internship_application": application.name,
        }
        # Placement-scope rows are one-per-placement; scope the idempotency check
        # to this placement so sibling placements each get their own copy.
        if placement:
            filters["internship_placement"] = placement.name
        existing = frappe.db.exists("Internship Requirement", filters)
        due = _compute_due(frappe._dict(tmpl), context, prev_due)
        prev_due = due or prev_due
        if existing:
            continue
        _instantiate(frappe._dict(tmpl), application, placement, due)


def _instantiate(tmpl, application, placement, due):
    row = {
        "doctype": "Internship Requirement",
        "internship_application": application.name,
        "internship_placement": placement.name if placement else None,
        "requirement_template": tmpl.name,
        "internship_type": application.internship_type,
        "title": tmpl.title,
        "scope": tmpl.scope,
        "mandatory": tmpl.mandatory,
        "is_hour_log": tmpl.is_hour_log,
        "submit_template": tmpl.submit_template,
        "due_date": due,
        "status": "Not Started",
    }
    for party in ("student", "seminary", "partner"):
        row[f"{party}_submits"] = tmpl.get(f"{party}_submits")
        for f in _PARTY_FIELDS:
            row[f"{party}_{f}"] = tmpl.get(f"{party}_{f}")
    row["seminary_signs_complete"] = tmpl.seminary_signs_complete
    row["partner_signs_complete"] = tmpl.partner_signs_complete
    frappe.get_doc(row).insert(ignore_permissions=True)


# --------------------------------------------------------------------------- #
# Hours roll-up
# --------------------------------------------------------------------------- #
def _counts_toward_total(log, tracking, hour_log_complete):
    """Whether a Hours Log row counts toward the total, per the type's mode."""
    if tracking == CONFIRM_LOG:
        return bool(log.supervisor_verified)
    if tracking == SUBMITTABLE_LOG:
        return bool(hour_log_complete)
    return True  # Portal Daily Log: counts immediately


def recompute_placement_hours(placement_name):
    placement = frappe.db.get_value(
        "Internship Placement",
        placement_name,
        ["internship_application", "name"],
        as_dict=True,
    )
    if not placement:
        return
    itype = frappe.db.get_value(
        "Internship Application",
        placement.internship_application,
        "internship_type",
    )
    tracking = (
        frappe.db.get_value("Internship Type", itype, "hours_tracking")
        if itype
        else None
    )

    hour_log_complete = False
    if tracking == SUBMITTABLE_LOG:
        hour_log_complete = bool(
            frappe.db.exists(
                "Internship Requirement",
                {
                    "internship_placement": placement_name,
                    "is_hour_log": 1,
                    "status": "Completed",
                },
            )
        )

    logs = frappe.get_all(
        "Internship Hours Log",
        filters={"internship_placement": placement_name},
        fields=["hours", "supervisor_verified"],
    )
    total = sum(
        (log.hours or 0)
        for log in logs
        if _counts_toward_total(log, tracking, hour_log_complete)
    )
    frappe.db.set_value("Internship Placement", placement_name, "hours_logged", total)
    maybe_advance_placement_status(placement_name)
    recompute_application_hours(placement.internship_application)


def maybe_advance_placement_status(placement_name):
    """System-driven placement lifecycle (ADR 054) — partners never set status:

    - Proposed -> Active when the start date has arrived (or the first hours are
      logged).
    - -> Completed only when the allocated hours are met AND the site-supervisor
      evaluation is submitted.

    Terminated and Completed are terminal and never auto-changed (early
    termination is an explicit partner action)."""
    p = frappe.db.get_value(
        "Internship Placement",
        placement_name,
        ["placement_status", "hours_allocated", "hours_logged", "actual_start"],
        as_dict=True,
    )
    if not p or p.placement_status in ("Completed", "Terminated"):
        return

    allocated = p.hours_allocated or 0
    hours_met = allocated > 0 and (p.hours_logged or 0) >= allocated
    eval_done = bool(
        frappe.db.exists(
            "Internship Supervisor Evaluation",
            {"internship_placement": placement_name, "docstatus": 1},
        )
    )

    new_status = None
    if hours_met and eval_done:
        new_status = "Completed"
    elif p.placement_status == "Proposed" and (
        (p.actual_start and getdate(p.actual_start) <= getdate(today()))
        or (p.hours_logged or 0) > 0
    ):
        new_status = "Active"

    if new_status and new_status != p.placement_status:
        frappe.db.set_value(
            "Internship Placement", placement_name, "placement_status", new_status
        )


def activate_due_placements():
    """Daily: flip Proposed placements to Active once their start date arrives,
    even with no other activity that day."""
    due = frappe.get_all(
        "Internship Placement",
        filters={"placement_status": "Proposed", "actual_start": ["<=", today()]},
        pluck="name",
    )
    for name in due:
        frappe.db.set_value("Internship Placement", name, "placement_status", "Active")
    if due:
        frappe.db.commit()


def recompute_application_hours(application_name):
    rows = frappe.get_all(
        "Internship Placement",
        filters={"internship_application": application_name},
        pluck="hours_logged",
    )
    total = sum(r or 0 for r in rows)
    frappe.db.set_value(
        "Internship Application", application_name, "total_hours_logged", total
    )
