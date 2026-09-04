# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Cohorts Needing Attention (ADR 066 §7.1, §7.2).

Two situations the system deliberately does not resolve on its own, because
resolving them means knowing something the records do not say.

A **cohort with no active leader** — a mentor on sabbatical, resigned, or
deceased — is not closed automatically. Who takes a group over is a pastoral
decision, and a system that silently reassigned it would be making that decision
badly. Nothing is auto-closed either: a membership closed by a job cannot be
told from one closed on purpose. So the gap is surfaced, dated, and left to a
person.

A **member on leave of absence** is the same shape of problem from the other
direction. Their membership stays open — a `Throughout Program` cohort runs to
graduation, and a leave is neither an ending nor a continuation — because
closing it would lose the cohort they are coming back to. What each school does
about the interval varies, so this says who is in that state and stops there.
"""

import frappe
from frappe import _
from frappe.utils import getdate, today

NO_LEADER = "no_leader"
INACTIVE_LEADER = "inactive_leader"
MEMBER_ON_LEAVE = "member_on_leave"


def execute(filters=None):
    filters = filters or {}
    rows = []
    wanted = filters.get("issue")

    if wanted in (None, "", NO_LEADER, INACTIVE_LEADER):
        rows.extend(leaderless_rows(filters, wanted))
    if wanted in (None, "", MEMBER_ON_LEAVE):
        rows.extend(on_leave_rows(filters))
    return columns(), rows


def columns():
    return [
        {
            "label": _("Cohort"),
            "fieldname": "cohort",
            "fieldtype": "Link",
            "options": "Cohort",
            "width": 200,
        },
        {
            "label": _("Cohort Type"),
            "fieldname": "cohort_type",
            "fieldtype": "Link",
            "options": "Cohort Type",
            "width": 160,
        },
        {"label": _("Issue"), "fieldname": "issue", "fieldtype": "Data", "width": 220},
        {
            "label": _("Person"),
            "fieldname": "person",
            "fieldtype": "Link",
            "options": "Person",
            "width": 130,
        },
        {
            "label": _("Name"),
            "fieldname": "person_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Detail"),
            "fieldname": "detail",
            "fieldtype": "Data",
            "width": 260,
        },
        {
            "label": _("Members"),
            "fieldname": "member_count",
            "fieldtype": "Int",
            "width": 80,
        },
        {"label": _("Since"), "fieldname": "since", "fieldtype": "Date", "width": 100},
    ]


def _cohort_filters(filters):
    cf = {"status": "Active"}
    if filters.get("cohort_type"):
        cf["cohort_type"] = filters["cohort_type"]
    return cf


def _active_cohorts(filters):
    return frappe.get_all(
        "Cohort",
        filters=_cohort_filters(filters),
        fields=["name", "cohort_name", "cohort_type", "leader"],
        order_by="cohort_name asc",
    )


def leaderless_rows(filters, wanted=None):
    """Cohorts whose leadership has gone quiet, and how it went quiet.

    Two distinct states, kept apart because they need different actions: nobody
    holds the seat at all, versus somebody holds it who is no longer an active
    instructor. The second is the sabbatical case, and it is the one that
    otherwise looks fine from every listing.
    """
    cohorts = _active_cohorts(filters)
    if not cohorts:
        return []

    leaders = frappe.get_all(
        "Cohort Membership",
        filters={
            "cohort": ("in", [c.name for c in cohorts]),
            "active": 1,
            "is_leader": 1,
        },
        fields=["cohort", "person", "joined_on"],
    )
    by_cohort = {}
    for row in leaders:
        by_cohort.setdefault(row.cohort, []).append(row)

    counts = _member_counts([c.name for c in cohorts])
    rows = []
    for c in cohorts:
        held = by_cohort.get(c.name) or []
        if not held:
            if wanted in (None, "", NO_LEADER):
                rows.append(
                    _row(
                        c,
                        _("No active leader"),
                        None,
                        None,
                        _("Nobody currently holds leadership of this cohort."),
                        counts.get(c.name, 0),
                        None,
                    )
                )
            continue

        if wanted == NO_LEADER:
            continue
        for row in held:
            instructor = frappe.db.get_value(
                "Instructor",
                {"person": row.person},
                ["name", "status"],
                as_dict=True,
            )
            # A leader who is not an instructor at all is not a problem: peer
            # leadership is ordinary (ADR 066 §5). Only a *lapsed* instructor is.
            if not instructor or instructor.status == "Active":
                continue
            rows.append(
                _row(
                    c,
                    _("Leader is no longer an active instructor"),
                    row.person,
                    _person_name(row.person),
                    _("Instructor {0} is {1}.").format(
                        instructor.name, instructor.status
                    ),
                    counts.get(c.name, 0),
                    row.joined_on,
                )
            )
    return rows


def on_leave_rows(filters):
    """Members whose program enrollment is on Leave of Absence."""
    cohorts = _active_cohorts(filters)
    if not cohorts:
        return []
    by_name = {c.name: c for c in cohorts}

    members = frappe.get_all(
        "Cohort Membership",
        filters={"cohort": ("in", list(by_name)), "active": 1},
        fields=["cohort", "person", "joined_on"],
    )
    if not members:
        return []

    # One query for every person on leave, rather than one per membership: a
    # cohort listing is read far more often than a leave is granted.
    on_leave = {
        r.person: r
        for r in frappe.db.sql(
            """select s.person, pe.program, pe.loa_start_date, pe.inactiveuntil
               from `tabProgram Enrollment` pe
               join `tabStudent` s on s.name = pe.student
               where pe.status = 'Leave of Absence' and pe.docstatus = 1
                 and s.person is not null""",
            as_dict=True,
        )
    }
    if not on_leave:
        return []

    counts = _member_counts(list(by_name))
    rows = []
    for m in members:
        leave = on_leave.get(m.person)
        if not leave:
            continue
        until = leave.get("inactiveuntil")
        detail = _("On leave from {0}").format(leave.get("program"))
        if until:
            overdue = getdate(until) < getdate(today())
            detail += _(", due back {0}{1}").format(
                until, _(" — overdue") if overdue else ""
            )
        rows.append(
            _row(
                by_name[m.cohort],
                _("Member on leave of absence"),
                m.person,
                _person_name(m.person),
                detail,
                counts.get(m.cohort, 0),
                leave.get("loa_start_date"),
            )
        )
    return rows


def _row(cohort, issue, person, person_name, detail, member_count, since):
    return {
        "cohort": cohort.name,
        "cohort_type": cohort.cohort_type,
        "issue": issue,
        "person": person,
        "person_name": person_name,
        "detail": detail,
        "member_count": member_count,
        "since": since,
    }


def _member_counts(cohorts):
    if not cohorts:
        return {}
    # One grouped query rather than one per cohort: this report exists to be
    # scanned, and a per-row count would make scanning it the expensive part.
    rows = frappe.db.sql(
        """select cohort, count(name) as n from `tabCohort Membership`
           where active = 1 and cohort in %(cohorts)s group by cohort""",
        {"cohorts": tuple(cohorts)},
        as_dict=True,
    )
    return {r.cohort: r.n for r in rows}


def _person_name(person):
    return frappe.db.get_value("Person", person, "full_name") or person
