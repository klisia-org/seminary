# Copyright (c) 2026, Murilo R. Melo and contributors
# For license information, please see license.txt
"""Disciplinary subsystem — advisory sanctioning matrix + dismissal trigger.

The progressive-discipline matrix on Disciplinary Reason maps an occurrence
number to recommended action(s); these only pre-fill an incident's applied
actions (advisory — the adjudicator decides). The single automated effect is a
sanction flagged ``triggers_dismissal``, which initiates a program dismissal
through the shared separation spine. See ADR 032.
"""

import frappe

TERMINAL_STATUSES = ("Withdrawn", "Dismissed", "Graduated", "Transferred")


@frappe.whitelist()
def suggest_actions(reason, occurrence_number=1):
    """Recommended Disciplinary Action(s) for a reason at a given occurrence.

    A matrix row applies when occurrence_from <= n <= occurrence_to, treating
    occurrence_to in (0, None) as open-ended ("and above")."""
    try:
        n = int(occurrence_number or 1)
    except (TypeError, ValueError):
        n = 1

    rows = frappe.get_all(
        "Disciplinary Reason Recommended Action",
        filters={"parent": reason, "parentfield": "recommended_actions"},
        fields=["occurrence_from", "occurrence_to", "recommended_action", "note"],
        order_by="idx asc",
    )
    matches = []
    for row in rows:
        lo = row.occurrence_from or 1
        hi = row.occurrence_to or 0
        if n >= lo and (hi == 0 or n <= hi):
            matches.append(row)
    return matches


@frappe.whitelist()
def compute_occurrence_number(student, reason, exclude_name=None):
    """1-based count of incidents for this student + reason (including this one)."""
    if not student or not reason:
        return 1
    filters = {"student": student, "reason": reason}
    if exclude_name:
        filters["name"] = ["!=", exclude_name]
    return frappe.db.count("Disciplinary Incident", filters) + 1


def on_incident_update(doc, method=None):
    """Fire a program dismissal when an applied action triggers it.

    Idempotent and re-entrancy safe: skips if the PE is already terminal or a
    live program-separation request already exists."""
    if not doc.pe or not doc.get("applied_actions"):
        return

    triggers = any(
        frappe.db.get_value("Disciplinary Action", row.action, "triggers_dismissal")
        for row in doc.applied_actions
        if row.action
    )
    if not triggers:
        return

    status = frappe.db.get_value("Program Enrollment", doc.pe, "status")
    if status in TERMINAL_STATUSES:
        return

    existing = frappe.db.exists(
        "Course Withdrawal Request",
        {
            "program_enrollment": doc.pe,
            "withdrawal_scope": "Full Program Withdrawal",
            "is_parent": 1,
            "docstatus": ("<", 2),
        },
    )
    if existing:
        return

    from seminary.seminary.doctype.course_withdrawal_request.course_withdrawal_request import (
        initiate_program_separation,
    )

    reason_label = frappe.db.get_value("Disciplinary Reason", doc.reason, "reason")
    request = initiate_program_separation(
        program_enrollment=doc.pe,
        withdrawal_reason=_dismissal_withdrawal_reason(),
        effective_date=doc.incident_date,
        timing="Immediate",
        separation_status="Dismissed",
        separation_category="Disciplinary",
        comment=f"Disciplinary dismissal — {reason_label} (incident {doc.name})",
    )

    # Place a re-enrollment-blocking hold on the student (Phase 7).
    try:
        from seminary.seminary.student_standing import add_hold

        add_hold(
            doc.student or frappe.db.get_value("Program Enrollment", doc.pe, "student"),
            hold_type="Disciplinary",
            reason=f"Dismissal — {reason_label}",
            source_doctype="Disciplinary Incident",
            source_name=doc.name,
        )
    except ImportError:
        pass

    frappe.msgprint(
        frappe._("Program dismissal initiated: {0}").format(request),
        indicator="orange",
        alert=True,
    )


def _dismissal_withdrawal_reason():
    """A Withdrawal Reasons row to attach to disciplinary separations.

    Disciplinary exits don't use the student-facing reason taxonomy, but the
    Course Withdrawal Request requires a withdrawal_reason; ensure a dedicated
    'Disciplinary Dismissal' reason exists and return it."""
    name = "Disciplinary Dismissal"
    if not frappe.db.exists("Withdrawal Reasons", name):
        frappe.get_doc(
            {
                "doctype": "Withdrawal Reasons",
                "label": name,
                "description": "Involuntary separation resulting from a disciplinary sanction.",
                "category": "Administrative",
            }
        ).insert(ignore_permissions=True)
    return name
