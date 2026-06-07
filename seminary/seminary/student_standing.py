# Copyright (c) 2026, Murilo R. Melo and contributors
# For license information, please see license.txt
"""Student standing & holds.

Holds are the real-SIS "registration hold": a Disciplinary hold blocks
re-enrollment (enforced in Program Enrollment.validate, registrar-overridable).
``student_standing`` is a derived label recomputed from active holds and the
student's program enrollments. See ADR 033.
"""

import frappe
from frappe.utils import today


def add_hold(
    student,
    hold_type,
    reason=None,
    source_doctype=None,
    source_name=None,
    blocks_reenrollment=1,
):
    """Append an active hold to a Student (direct child insert) and recompute
    standing. Skips if an identical active hold from the same source exists."""
    if not student:
        return

    if source_name and frappe.db.exists(
        "Student Hold",
        {
            "parent": student,
            "parentfield": "student_holds",
            "source_doctype": source_doctype,
            "source_name": source_name,
            "is_active": 1,
        },
    ):
        return

    idx = (
        frappe.db.count(
            "Student Hold", {"parent": student, "parentfield": "student_holds"}
        )
        + 1
    )
    frappe.get_doc(
        {
            "doctype": "Student Hold",
            "parent": student,
            "parenttype": "Student",
            "parentfield": "student_holds",
            "idx": idx,
            "hold_type": hold_type,
            "reason": reason,
            "raised_on": today(),
            "raised_by": frappe.session.user,
            "source_doctype": source_doctype,
            "source_name": source_name,
            "is_active": 1,
            "blocks_reenrollment": 1 if blocks_reenrollment else 0,
        }
    ).db_insert()
    recompute_standing(student)


def apply_terminal_standing(pe_doc, to_status, reason, effective_date):
    """Refresh the student's standing after a terminal program transition.

    The blocking Disciplinary hold for a dismissal is placed by the disciplinary
    trigger (disciplinary.on_incident_update); here we only recompute the label."""
    if pe_doc.student:
        recompute_standing(pe_doc.student)


def recompute_standing(student):
    """Derive student_standing from active holds + program enrollment statuses."""
    active_holds = frappe.get_all(
        "Student Hold",
        filters={"parent": student, "parentfield": "student_holds", "is_active": 1},
        pluck="hold_type",
    )
    if "Disciplinary" in active_holds:
        standing = "Dismissed"
    elif "Academic" in active_holds:
        standing = "Suspended"
    else:
        statuses = frappe.get_all(
            "Program Enrollment", filters={"student": student}, pluck="status"
        )
        if any(s in ("Active", "Leave of Absence") for s in statuses):
            standing = "Good Standing"
        elif "Dismissed" in statuses:
            standing = "Dismissed"
        elif any(s in ("Withdrawn", "Transferred") for s in statuses):
            standing = "Withdrawn"
        else:
            standing = "Good Standing"

    frappe.db.set_value(
        "Student", student, "student_standing", standing, update_modified=False
    )


@frappe.whitelist()
def lift_hold(student, hold_row_name):
    """Deactivate a hold and recompute standing."""
    frappe.db.set_value(
        "Student Hold",
        hold_row_name,
        {"is_active": 0, "lifted_on": today(), "lifted_by": frappe.session.user},
        update_modified=False,
    )
    recompute_standing(student)
    return student
