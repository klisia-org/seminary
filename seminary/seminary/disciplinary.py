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
from frappe import _
from frappe.utils import today

TERMINAL_STATUSES = ("Withdrawn", "Dismissed", "Graduated", "Transferred")

# Roles that may report/record disciplinary actions for any course (adjudicators).
PRIVILEGED_ROLES = {"System Manager", "Academics User", "Seminary Manager", "Registrar"}


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


# ---------------------------------------------------------------------------
# Instructor portal reporting (ADR 032)
# ---------------------------------------------------------------------------


def _require_portal_enabled():
    if not frappe.db.get_single_value("Seminary Settings", "portal_disciplinary"):
        frappe.throw(_("Portal disciplinary reporting is disabled."))


def _privileged(user=None):
    return bool(set(frappe.get_roles(user or frappe.session.user)) & PRIVILEGED_ROLES)


def _user_is_course_instructor(user, course_schedule):
    """True when ``user`` is on the Course Schedule's instructor table."""
    if not course_schedule:
        return False
    return bool(
        frappe.db.exists(
            "Course Schedule Instructors",
            {"parent": course_schedule, "parentfield": "instructor1", "user": user},
        )
    )


def _authorize_course_instructor(course_schedule):
    user = frappe.session.user
    if _user_is_course_instructor(user, course_schedule) or _privileged(user):
        return
    frappe.throw(
        _("You are not an instructor for this course."), frappe.PermissionError
    )


def _recommendation(reason, occurrence_number):
    """suggest_actions enriched with each action's instructor/dismissal flags."""
    recommended = []
    for row in suggest_actions(reason, occurrence_number):
        flags = (
            frappe.db.get_value(
                "Disciplinary Action",
                row.recommended_action,
                ["instructor_action", "triggers_dismissal"],
                as_dict=True,
            )
            or {}
        )
        recommended.append(
            {
                "action": row.recommended_action,
                "instructor_action": int(flags.get("instructor_action") or 0),
                "triggers_dismissal": int(flags.get("triggers_dismissal") or 0),
                "note": row.note,
            }
        )
    return recommended


def _apply_actions(incident, actions):
    for action in actions:
        incident.append(
            "applied_actions",
            {
                "action": action,
                "applied_on": today(),
                "applied_by": frappe.session.user,
                "was_suggested": 1,
            },
        )
    incident.save(ignore_permissions=True)


@frappe.whitelist()
def preview_recommendation(reason, cei=None, student=None):
    """Occurrence number + enriched recommendation for the report modal.

    Lets the UI show "Occurrence #N — recommended: X" and decide whether an
    instructor may record the action, before the incident is filed."""
    if not student and cei:
        student = frappe.db.get_value("Course Enrollment Individual", cei, "student_ce")
    occurrence_number = compute_occurrence_number(student, reason) if student else 1
    return {
        "occurrence_number": occurrence_number,
        "recommended": _recommendation(reason, occurrence_number),
    }


@frappe.whitelist()
def report_incident(
    reason,
    cei=None,
    student=None,
    course=None,
    assessment=None,
    evidence=None,
    evidence_attach=None,
    record_action=0,
):
    """File a Disciplinary Incident from the instructor portal.

    Course mode passes ``cei`` directly; assessment mode passes ``student`` +
    ``course`` (+ ``assessment``) and the CEI is resolved here. Returns the new
    incident, its occurrence number, the recommended action(s), and the
    resulting status."""
    _require_portal_enabled()
    if not frappe.db.get_value("Disciplinary Reason", reason, "instructor_portal"):
        frappe.throw(_("This reason is not available for portal reporting."))

    record_action = int(record_action or 0)

    if not cei:
        if not (student and course):
            frappe.throw(
                _("Provide either a course enrollment or a student and course.")
            )
        cei = frappe.db.get_value(
            "Course Enrollment Individual",
            {"student_ce": student, "coursesc_ce": course, "withdrawn": 0},
            "name",
        )
        if not cei:
            frappe.throw(
                _("No active course enrollment found for this student in the course.")
            )

    cei_doc = frappe.db.get_value(
        "Course Enrollment Individual",
        cei,
        ["program_ce", "student_ce", "coursesc_ce"],
        as_dict=True,
    )
    if not cei_doc:
        frappe.throw(_("Course enrollment not found."))

    course_schedule = course or cei_doc.coursesc_ce
    _authorize_course_instructor(course_schedule)

    requires_course = frappe.db.get_value(
        "Disciplinary Reason", reason, "requires_course"
    )
    if requires_course and not assessment:
        frappe.throw(_("This reason requires the assessment involved."))

    incident = frappe.get_doc(
        {
            "doctype": "Disciplinary Incident",
            "pe": cei_doc.program_ce,
            "student": cei_doc.student_ce,
            "cei": cei,
            "reason": reason,
            "assessment": assessment if requires_course else None,
            "evidence": evidence,
            "evidence_attach": evidence_attach,
            "status": "Reported",
            "reported_by": frappe.session.user,
        }
    )
    incident.insert(ignore_permissions=True)

    recommended = _recommendation(reason, incident.occurrence_number)
    all_instructor = bool(recommended) and all(
        r["instructor_action"] and not r["triggers_dismissal"] for r in recommended
    )
    needs_escalation = any(
        (not r["instructor_action"]) or r["triggers_dismissal"] for r in recommended
    )

    status = "Reported"
    if record_action and all_instructor:
        _apply_actions(incident, [r["action"] for r in recommended])
        status = "Action Taken"
    elif needs_escalation:
        status = "Escalated"

    if status != "Reported":
        frappe.db.set_value("Disciplinary Incident", incident.name, "status", status)

    return {
        "incident": incident.name,
        "occurrence_number": incident.occurrence_number,
        "recommended": recommended,
        "status": status,
    }


@frappe.whitelist()
def record_incident_action(incident, action):
    """Record an instructor-authorized action on a pending incident (the To-Do)."""
    inc = frappe.get_doc("Disciplinary Incident", incident)
    course_schedule = (
        frappe.db.get_value("Course Enrollment Individual", inc.cei, "coursesc_ce")
        if inc.cei
        else None
    )
    _authorize_course_instructor(course_schedule)
    if not frappe.db.get_value("Disciplinary Action", action, "instructor_action"):
        frappe.throw(_("This action is not available for instructors to record."))

    _apply_actions(inc, [action])
    frappe.db.set_value("Disciplinary Incident", inc.name, "status", "Action Taken")
    return {"incident": inc.name, "status": "Action Taken"}


@frappe.whitelist()
def list_pending_incidents(course):
    """Actionable pending incidents for a Course Schedule (for the To-Do card).

    Only incidents still ``Reported`` whose occurrence recommends an
    instructor-recordable action, visible to a course instructor."""
    user = frappe.session.user
    if not (_user_is_course_instructor(user, course) or _privileged(user)):
        return []

    ceis = frappe.get_all(
        "Course Enrollment Individual", filters={"coursesc_ce": course}, pluck="name"
    )
    if not ceis:
        return []

    incidents = frappe.get_all(
        "Disciplinary Incident",
        filters={"cei": ["in", ceis], "status": "Reported"},
        fields=["name", "student", "reason", "occurrence_number"],
        order_by="creation desc",
    )

    pending = []
    for inc in incidents:
        actions = [
            r["action"]
            for r in _recommendation(inc.reason, inc.occurrence_number)
            if r["instructor_action"] and not r["triggers_dismissal"]
        ]
        if not actions:
            continue
        pending.append(
            {
                "incident": inc.name,
                "student": inc.student,
                "student_name": frappe.db.get_value(
                    "Student", inc.student, "student_name"
                ),
                "reason": inc.reason,
                "reason_label": frappe.db.get_value(
                    "Disciplinary Reason", inc.reason, "reason"
                ),
                "occurrence_number": inc.occurrence_number,
                "recommended_actions": actions,
            }
        )
    return pending


@frappe.whitelist()
def list_course_enrollments(course):
    """Active course enrollments for a course, labelled by student name.

    Powers the course-level report modal's student picker (the CEI name is not
    human-readable)."""
    user = frappe.session.user
    if not (_user_is_course_instructor(user, course) or _privileged(user)):
        return []

    rows = frappe.get_all(
        "Course Enrollment Individual",
        filters={"coursesc_ce": course, "withdrawn": 0},
        fields=["name", "student_ce"],
    )
    student_ids = list({r.student_ce for r in rows if r.student_ce})
    names = {}
    if student_ids:
        for s in frappe.get_all(
            "Student",
            filters={"name": ["in", student_ids]},
            fields=["name", "student_name"],
        ):
            names[s.name] = s.student_name

    options = [
        {"value": r.name, "label": names.get(r.student_ce, r.student_ce)} for r in rows
    ]
    options.sort(key=lambda o: (o["label"] or "").lower())
    return options


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

    # Mark the incident dismissed without re-triggering this on_update hook.
    if doc.get("status") != "Dismissed":
        frappe.db.set_value("Disciplinary Incident", doc.name, "status", "Dismissed")
        doc.status = "Dismissed"

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
