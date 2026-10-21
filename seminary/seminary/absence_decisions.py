# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""What happens to a student over the absence limit when grades are sent (ADR 081).

Send Grades stops while a student being sent is over the limit and nobody has
decided for them. The gradebook asks the instructor, per student, to fail them
for absence, keep the grade (with a reason), or leave it to the registrar. The
choice is stored on the Scheduled Course Roster row. The registrar can still
fail or keep afterwards (ADR 037 addendum).
"""

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

FAIL = "Fail for absence"
KEEP = "Keep the grade"
NO_RECOMMENDATION = "No recommendation"
DECISIONS = (FAIL, KEEP, NO_RECOMMENDATION)


def undecided(course_schedule, rosters=None):
    """Rosters over the limit with no decision yet, in this section."""
    filters = {
        "course_sc": course_schedule,
        "active": 1,
        "audit_bool": 0,
        "attendance_alert_level": [">=", 2],
        "failed_for_absence": 0,
        "absence_decision": ["is", "not set"],
    }
    if rosters is not None:
        filters["name"] = ["in", list(rosters) or [""]]
    return frappe.get_all(
        "Scheduled Course Roster",
        filters=filters,
        fields=[
            "name as roster",
            "student",
            "stuname_roster",
            "effective_absences",
            "absence_limit",
        ],
        order_by="stuname_roster asc",
    )


def assert_decided(course_schedule, rosters=None):
    """Called by send_grades / send_selected_grades before anything is written."""
    pending = undecided(course_schedule, rosters)
    if pending:
        frappe.throw(
            _("Decide first for the students over the absence limit: {0}.").format(
                ", ".join(r.stuname_roster or r.student for r in pending)
            ),
            title=_("Absences over the limit"),
        )


def _parse_rosters(rosters):
    if rosters is None or rosters == "":
        return None
    return json.loads(rosters) if isinstance(rosters, str) else list(rosters)


@frappe.whitelist()
def absence_decisions_needed(course_schedule, rosters=None):
    """The students the Send Grades dialog has to ask about."""
    from seminary.seminary.api import _assert_may_send_grades, _require_send_scope

    _assert_may_send_grades()
    _require_send_scope(course_schedule)
    return undecided(course_schedule, _parse_rosters(rosters))


@frappe.whitelist(methods=["POST"])
def record_absence_decisions(course_schedule, decisions):
    """Store the instructor's choice for each student in the dialog.

    `decisions` is a list of {roster, decision, reason}. Only students still
    waiting for a decision in this section are accepted.
    """
    from seminary.seminary.api import _assert_may_send_grades, _require_send_scope

    _assert_may_send_grades()
    _require_send_scope(course_schedule)
    if isinstance(decisions, str):
        decisions = json.loads(decisions)

    waiting = {r.roster for r in undecided(course_schedule)}
    for d in decisions or []:
        roster, decision = d.get("roster"), d.get("decision")
        reason = (d.get("reason") or "").strip()
        if roster not in waiting:
            frappe.throw(
                _("{0} is not waiting for an absence decision in this section.").format(
                    roster
                )
            )
        if decision not in DECISIONS:
            frappe.throw(_("Choose what happens for every student."))
        if decision == KEEP and not reason:
            frappe.throw(_("Give a reason for keeping the grade."))
        record(roster, decision, reason)
    return {"recorded": len(decisions or [])}


def record(roster, decision, reason=None):
    """Write the decision, and fail the student when that is the decision."""
    frappe.db.set_value(
        "Scheduled Course Roster",
        roster,
        {
            "absence_decision": decision,
            "absence_decision_reason": reason or None,
            "absence_decided_by": frappe.session.user,
            "absence_decided_on": now_datetime(),
        },
        update_modified=False,
    )
    if decision == FAIL:
        from seminary.seminary.api import _fail_for_absence

        _fail_for_absence(roster)


@frappe.whitelist(methods=["POST"])
def keep_grade_despite_absences(name, reason=None):
    """Registrar action: settle a student over the limit by keeping the grade,
    e.g. one an instructor left to the registrar."""
    from seminary.seminary.api import _assert_fa_roles

    _assert_fa_roles()
    if frappe.db.get_value("Scheduled Course Roster", name, "failed_for_absence"):
        frappe.throw(_("Undo the fail for absence instead."))
    record(name, KEEP, reason)
    return {"absence_decision": KEEP}
