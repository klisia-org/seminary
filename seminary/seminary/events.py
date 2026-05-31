# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Events as first-class citizens.

A Frappe Event is an *instance*; an `Event Custom Category` is the reusable
*type* (e.g. Convocation, Chapel, Thesis Defense). Graduation Requirement Items
of type "Event Attendance" and Culminating Project defense milestones point at a
category; this module creates Event instances from a category and reflects their
attendance back onto the Student Graduation Requirement (SGR) snapshot.
"""

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, getdate, today

from seminary.seminary.graduation import _mark_sgr_fulfilled

SGR_DOCTYPE = "Student Graduation Requirement"
_OPEN_SGR_STATUSES = ("Not Started", "In Progress", "Submitted")


def create_event_from_category(
    category,
    starts_on,
    ends_on=None,
    location=None,
    participants=None,
    subject=None,
    extra_description=None,
):
    """Create a Frappe Event from an Event Custom Category.

    `participants` is a list of dicts: {reference_doctype, reference_docname,
    email}. Attendance-tracked requirement events reference the SGR row
    (reference_doctype="Student Graduation Requirement"). Returns the Event name.
    """
    cat = frappe.get_cached_doc("Event Custom Category", category)
    description = "\n\n".join(p for p in (cat.instructions, extra_description) if p)
    event = frappe.get_doc(
        {
            "doctype": "Event",
            "subject": subject or cat.category_name,
            "starts_on": starts_on,
            "ends_on": ends_on,
            "event_type": "Private" if cat.visibility == "Private" else "Public",
            "event_category": "Event",
            "event_custom_category": cat.name,
            "location": location,
            "description": description or None,
            "status": "Open",
        }
    )
    for member in participants or []:
        event.append(
            "event_participants",
            {
                "reference_doctype": member.get("reference_doctype"),
                "reference_docname": member.get("reference_docname"),
                "email": member.get("email"),
            },
        )
    event.insert(ignore_permissions=True)
    return event.name


def reflect_event_attendance(doc, method=None):
    """`on_update` hook on Event. Fulfil the SGR rows an attendance Event covers.

    - Cohort category (per_student=0): when the Event is Completed, fulfil every
      referenced SGR row (one occurrence satisfies the cohort).
    - Per-student category (per_student=1): fulfil each referenced SGR whose
      participant is marked attending == "Yes" (mark them as they show up).

    Mirrors graduation.reflect_linked_doc_status. Cheap short-circuit when the
    Event isn't a category event or carries no SGR participants. Defense events
    carry no SGR participants, so they never fulfil anything here.
    """
    category = doc.get("event_custom_category")
    if not category:
        return
    sgr_participants = [
        p
        for p in (doc.get("event_participants") or [])
        if p.reference_doctype == SGR_DOCTYPE and p.reference_docname
    ]
    if not sgr_participants:
        return

    per_student = frappe.db.get_value("Event Custom Category", category, "per_student")
    completed = doc.status == "Completed"

    for participant in sgr_participants:
        if per_student:
            if (participant.attending or "") != "Yes":
                continue
        elif not completed:
            continue
        _fulfil_sgr(participant.reference_docname)


def _fulfil_sgr(sgr_name):
    info = frappe.db.get_value(
        SGR_DOCTYPE,
        sgr_name,
        ["parent", "parenttype", "status", "waived"],
        as_dict=True,
    )
    if not info or info.waived or info.status in ("Fulfilled", "Waived"):
        return
    _mark_sgr_fulfilled(info.parent, info.parenttype, sgr_name)


# ---------------------------------------------------------------------------
# Entry points: create attendance Events for graduation requirements
# ---------------------------------------------------------------------------


def _sgr_participant(sgr_name, pe_name=None):
    """Build an Event participant referencing an SGR row (student email resolved
    from the parent Program Enrollment's Student)."""
    pe_name = pe_name or frappe.db.get_value(SGR_DOCTYPE, sgr_name, "parent")
    student = frappe.db.get_value("Program Enrollment", pe_name, "student")
    email = (
        frappe.db.get_value("Student", student, "student_email_id") if student else None
    )
    return {
        "reference_doctype": SGR_DOCTYPE,
        "reference_docname": sgr_name,
        "email": email,
    }


def _default_starts_on(due_date):
    """Default an Event start to 09:00 on the due date (or today)."""
    return get_datetime(f"{getdate(due_date) if due_date else today()} 09:00:00")


@frappe.whitelist()
def get_per_student_event_requirements(program_enrollment):
    """Open Event-Attendance requirements on this enrollment whose category is
    per-student (each needs its own Event). Feeds the desk 'Schedule Required
    Event' picker."""
    if not frappe.has_permission("Program Enrollment", "read"):
        frappe.throw(_("Not permitted."), frappe.PermissionError)
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    per_student_cache = {}
    out = []
    for row in pe.graduation_requirements or []:
        if row.requirement_type != "Event Attendance" or not row.event_custom_category:
            continue
        if row.status in ("Fulfilled", "Waived"):
            continue
        cat = row.event_custom_category
        if cat not in per_student_cache:
            per_student_cache[cat] = frappe.db.get_value(
                "Event Custom Category", cat, "per_student"
            )
        if not per_student_cache[cat]:
            continue
        out.append(
            {
                "sgr_name": row.name,
                "requirement_name": row.requirement_name,
                "category": cat,
                "due_date": row.due_date,
            }
        )
    return out


@frappe.whitelist()
def create_requirement_event(program_enrollment, sgr_name, starts_on=None):
    """Per-student (Behavior i): create an attendance Event for one student's
    Event-Attendance requirement, pre-filled from its category. Staff adjusts the
    date on the routed Event. Returns the new Event name."""
    if not frappe.has_permission("Program Enrollment", "write"):
        frappe.throw(
            _("Not permitted to create requirement events."), frappe.PermissionError
        )
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    row = next((r for r in pe.graduation_requirements if r.name == sgr_name), None)
    if not row:
        frappe.throw(
            _("Requirement {0} not found on this enrollment.").format(sgr_name)
        )
    if not row.event_custom_category:
        frappe.throw(
            _("This requirement has no Event Category to create an event from.")
        )
    event = create_event_from_category(
        row.event_custom_category,
        starts_on or _default_starts_on(row.due_date),
        participants=[_sgr_participant(sgr_name, pe.name)],
        subject="{0} — {1}".format(
            row.event_custom_category, pe.student_name or pe.student
        ),
        extra_description=_("For {0} ({1}).").format(
            pe.student_name or pe.student, pe.name
        ),
    )
    return {"event": event}


@frappe.whitelist()
def get_cohort_candidates(
    event_custom_category, program=None, only_candidates=0, within_days=None
):
    """Cohort (Behavior ii): active enrollments with an open Event-Attendance
    requirement of this category, for the bulk create-event modal."""
    if not frappe.has_permission("Program Enrollment", "read"):
        frappe.throw(_("Not permitted."), frappe.PermissionError)

    conditions = [
        "sgr.event_custom_category = %(cat)s",
        "sgr.parenttype = 'Program Enrollment'",
        "sgr.status IN %(open)s",
        "pe.docstatus = 1",
    ]
    params = {"cat": event_custom_category, "open": _OPEN_SGR_STATUSES}
    if program:
        conditions.append("pe.program = %(program)s")
        params["program"] = program
    if int(only_candidates or 0):
        conditions.append("pe.grad_candidate = 1")
    if within_days:
        conditions.append("pe.max_graduation_date <= %(cutoff)s")
        params["cutoff"] = add_days(today(), int(within_days))

    return frappe.db.sql(
        """
        SELECT sgr.name AS sgr_name, sgr.due_date,
               pe.name AS program_enrollment, pe.student_name, pe.program,
               pe.max_graduation_date, pe.grad_candidate,
               st.student_email_id AS email
        FROM `tabStudent Graduation Requirement` sgr
        JOIN `tabProgram Enrollment` pe ON pe.name = sgr.parent
        LEFT JOIN `tabStudent` st ON st.name = pe.student
        WHERE {conditions}
        ORDER BY pe.student_name
        """.format(
            conditions=" AND ".join(conditions)
        ),
        params,
        as_dict=True,
    )


@frappe.whitelist()
def create_cohort_event(
    event_custom_category, sgr_names, starts_on, ends_on=None, location=None
):
    """Cohort (Behavior ii): one Event covering many students' SGR rows. The
    single occurrence fulfils them all when the Event is marked Completed."""
    if not frappe.has_permission("Program Enrollment", "write"):
        frappe.throw(
            _("Not permitted to create cohort events."), frappe.PermissionError
        )
    names = frappe.parse_json(sgr_names) if isinstance(sgr_names, str) else sgr_names
    if not names:
        frappe.throw(_("Select at least one student."))
    participants = [_sgr_participant(n) for n in names]
    event = create_event_from_category(
        event_custom_category,
        starts_on,
        ends_on=ends_on,
        location=location,
        participants=participants,
        subject="{0} — {1}".format(event_custom_category, getdate(starts_on)),
    )
    return {"event": event, "count": len(participants)}
