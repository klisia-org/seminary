# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""What an instructor is currently carrying (ADR 066 section 7.1).

A mentor going on sabbatical is the case that started this: the registrar had no
way to see what would be left behind, and the memberships would simply stay open
with nobody noticing. Rather than close anything automatically -- who takes a
group over is a pastoral decision, and a membership closed by a job cannot be
told from one closed on purpose -- the commitments are made visible on the
Instructor record, and marking someone inactive says out loud what is still
theirs.

Three kinds of commitment, because they are three different handovers: a section
needs another instructor, a cohort needs another leader, and a culminating
project needs another supervisor.
"""

import frappe
from frappe import _
from frappe.utils import getdate, today


def open_commitments(instructor):
    """Everything still attached to this instructor, grouped by kind."""
    if not instructor:
        return {"sections": [], "cohorts": [], "projects": []}
    return {
        "sections": _open_sections(instructor),
        "cohorts": _led_cohorts(instructor),
        "projects": _supervised_projects(instructor),
    }


def total(commitments):
    return sum(len(v) for v in commitments.values())


def _open_sections(instructor):
    """Course schedules that have not finished, or never end."""
    names = frappe.get_all(
        "Course Schedule Instructors",
        filters={"instructor": instructor},
        pluck="parent",
    )
    if not names:
        return []
    out = []
    for cs in frappe.get_all(
        "Course Schedule",
        filters={"name": ("in", list(set(names)))},
        fields=["name", "title", "course", "c_dateend"],
    ):
        # No end date is an open-ended section (ADR 065 section 5), not a closed
        # one: it is still theirs until somebody says otherwise.
        if cs.c_dateend and getdate(cs.c_dateend) < getdate(today()):
            continue
        out.append(
            {
                "name": cs.name,
                "label": cs.title or cs.course or cs.name,
                "until": cs.c_dateend,
            }
        )
    return out


def _led_cohorts(instructor):
    person = frappe.db.get_value("Instructor", instructor, "person")
    if not person:
        return []
    led = frappe.get_all(
        "Cohort Membership",
        filters={"person": person, "active": 1, "is_leader": 1},
        pluck="cohort",
    )
    if not led:
        return []
    out = []
    for c in frappe.get_all(
        "Cohort",
        filters={"name": ("in", led), "status": "Active"},
        fields=["name", "cohort_name", "cohort_type"],
    ):
        others = frappe.db.count(
            "Cohort Membership",
            {"cohort": c.name, "active": 1, "is_leader": 1, "person": ("!=", person)},
        )
        out.append(
            {
                "name": c.name,
                "label": c.cohort_name or c.name,
                "cohort_type": c.cohort_type,
                "members": frappe.db.count(
                    "Cohort Membership", {"cohort": c.name, "active": 1}
                ),
                # A co-led cohort is not left leaderless by one person stepping
                # back, and saying so is the difference between a warning worth
                # reading and noise.
                "co_led": bool(others),
            }
        )
    return out


# A project in one of these states needs nothing further from its advisor.
FINISHED_PROJECT_STATES = ("Completed", "Rejected", "Withdrawn")


def _supervised_projects(instructor):
    """Culminating projects still in flight under this advisor.

    `second_reader` is deliberately not counted: a second reader is a reviewer,
    not the person a student would be left without.
    """
    return [
        {
            "name": r.name,
            "label": r.project_title or r.name,
            "student": r.student,
            "status": r.workflow_state,
        }
        for r in frappe.get_all(
            "Culminating Project",
            filters={
                "advisor": instructor,
                "docstatus": ("<", 2),
                "workflow_state": ("not in", FINISHED_PROJECT_STATES),
            },
            fields=["name", "project_title", "student", "workflow_state"],
        )
    ]


def commitments_html(instructor):
    """The panel rendered on the Instructor form."""
    data = open_commitments(instructor)
    if not total(data):
        return ""

    def block(title, rows, render):
        if not rows:
            return ""
        items = "".join("<li>%s</li>" % render(r) for r in rows)
        return "<div style='margin-bottom:8px'><b>{0}</b><ul style='margin:4px 0 0 18px'>{1}</ul></div>".format(
            frappe.utils.escape_html(title), items
        )

    html = block(
        _("Open course schedules"),
        data["sections"],
        lambda r: "<a href='/app/course-schedule/{0}'>{1}</a>{2}".format(
            r["name"],
            frappe.utils.escape_html(r["label"]),
            _(" — until {0}").format(r["until"]) if r["until"] else _(" — open-ended"),
        ),
    )
    html += block(
        _("Cohorts led"),
        data["cohorts"],
        lambda r: "<a href='/app/cohort/{0}'>{1}</a> — {2}{3}".format(
            r["name"],
            frappe.utils.escape_html(r["label"]),
            _("{0} members").format(r["members"]),
            _(", co-led") if r["co_led"] else _(", sole leader"),
        ),
    )
    html += block(
        _("Culminating projects supervised"),
        data["projects"],
        lambda r: "<a href='/app/culminating-project/{0}'>{1}</a>{2}".format(
            r["name"],
            frappe.utils.escape_html(r["label"]),
            " — %s" % frappe.utils.escape_html(r["status"]) if r.get("status") else "",
        ),
    )
    return html


@frappe.whitelist()
def instructor_commitments(instructor):
    frappe.has_permission("Instructor", "read", instructor, throw=True)
    return {
        "html": commitments_html(instructor),
        "count": total(open_commitments(instructor)),
    }


def warn_on_deactivation(doc):
    """Say what is being left behind when an instructor is marked inactive.

    A warning, not a refusal. Somebody going on sabbatical is a fact; the
    handover is work that follows it, and blocking the status change would only
    mean the status stops being true.
    """
    if doc.status == "Active":
        return
    before = doc.get_doc_before_save()
    if before and before.status != "Active":
        return

    data = open_commitments(doc.name)
    if not total(data):
        return

    parts = []
    if data["sections"]:
        parts.append(_("{0} open course schedule(s)").format(len(data["sections"])))
    sole = [c for c in data["cohorts"] if not c["co_led"]]
    if data["cohorts"]:
        parts.append(
            _("{0} cohort(s) led, {1} of them with no other leader").format(
                len(data["cohorts"]), len(sole)
            )
        )
    if data["projects"]:
        parts.append(_("{0} culminating project(s)").format(len(data["projects"])))

    frappe.msgprint(
        _(
            "{0} still has {1}. Nothing has been closed — see Open Commitments on "
            "this record, and the Cohorts Needing Attention report."
        ).format(frappe.bold(doc.instructor_name or doc.name), ", ".join(parts)),
        title=_("Open commitments"),
        indicator="orange",
    )
