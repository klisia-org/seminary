# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""The CBE Overview: competency progress across sections, with a student lens
and a mentor lens (privatedocs p012 decision 5).

Every other competency surface is one section or one mentor at a time. This
one answers the chair's question -- who is stalled, and which mentors are
behind -- across a programme, a cohort or a term. The states are the ones the
engine already knows; nothing here is a new rule except "lagging", which is
two existing thresholds and, where aretenic is installed, its pacing.

A mentor gets the same page limited to their own mentees: their caseload.
"""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, getdate, nowdate

from seminary.seminary import cbe, guards

OPEN_STATES = ("Open for Enrollment", "Enrollment Closed", "Grading")
DECIDED = ("Competent", "Not Yet Competent")


def _viewer_scope():
    """(school, sections): school roles read every section; an instructor the
    sections they teach or mentor in; anyone else nothing."""
    if guards.is_school_role():
        return True, None
    if "Instructor" not in frappe.get_roles():
        return False, []
    return False, sorted(
        set(guards.own_course_schedules()) | set(guards.mentored_sections())
    )


def has_overview(user=None):
    """Sidebar flag: a school role, or anyone teaching or mentoring in a
    competency section."""
    if guards.is_school_role(user):
        return True
    if "Instructor" not in frappe.get_roles(user):
        return False
    if guards.mentored_sections(user):
        return True
    return any(cbe.framework_for(cs) for cs in guards.own_course_schedules(user))


def _students_in(program=None, cohort=None):
    """Students matching the programme / cohort filters, or None for no filter."""
    sets = []
    if program:
        sets.append(
            set(
                frappe.get_all(
                    "Program Enrollment",
                    filters={"program": program, "docstatus": 1},
                    pluck="student",
                )
            )
        )
    if cohort:
        persons = frappe.get_all(
            "Cohort Membership",
            filters={"cohort": cohort, "active": 1},
            pluck="person",
        )
        sets.append(
            set(
                frappe.get_all(
                    "Student", filters={"person": ("in", persons or [""])}, pluck="name"
                )
            )
        )
    if not sets:
        return None
    out = sets[0]
    for s in sets[1:]:
        out &= s
    return out


def _expected_days(course):
    """Aretenic's time-to-competency p90 for this course, when installed."""
    for fn in frappe.get_hooks("cbe_expected_days") or []:
        try:
            value = frappe.get_attr(fn)(course)
        except Exception:
            frappe.log_error(title="CBE Overview: expected days hook failed")
            value = None
        if value:
            return value
    return None


def _last_activity(student, course_schedule):
    """The student's most recent submission or self-assessment in the section."""
    sources = [
        (doctype, {"student": student, section_field: course_schedule})
        for doctype, _activity, section_field in cbe._SUBMISSION_FOR.values()
    ]
    sources.append(
        (
            "Competency Assessment",
            {
                "student": student,
                "course_schedule": course_schedule,
                "evaluator_kind": "Self",
            },
        )
    )
    dates = []
    for doctype, filters in sources:
        latest = frappe.get_all(
            doctype,
            filters=filters,
            pluck="modified",
            order_by="modified desc",
            limit=1,
        )
        if latest:
            dates.append(getdate(latest[0]))
    return max(dates) if dates else None


def _activities_done(roster_doc, competency):
    for row in frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": roster_doc.course_sc, "course_competency": competency},
        fields=["name", *cbe._SUBMISSION_FOR],
    ):
        field = next((f for f in cbe._SUBMISSION_FOR if row.get(f)), None)
        if field and not cbe._submitted(
            row, field, roster_doc.student, roster_doc.course_sc
        ):
            return False
    return True


def _any_activity(roster_doc, competency):
    for row in frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": roster_doc.course_sc, "course_competency": competency},
        fields=["name", *cbe._SUBMISSION_FOR],
    ):
        field = next((f for f in cbe._SUBMISSION_FOR if row.get(f)), None)
        if field and cbe._submitted(
            row, field, roster_doc.student, roster_doc.course_sc
        ):
            return True
    return cbe._self_assessment_submitted(
        roster_doc.student, roster_doc.course_sc, competency, stage="Baseline"
    )


def _cell(roster_doc, competency, framework, verdict_evaluators, names, result):
    """One competency's state for one student, in the engine's own terms."""
    if result and result.status in DECIDED:
        return {"state": "decided", "label": result.final_code or _(result.status)}
    if cbe.mentor_assessment_due(roster_doc, competency, framework):
        submitted = set(
            frappe.get_all(
                "Competency Assessment",
                filters={
                    "student": roster_doc.student,
                    "course_schedule": roster_doc.course_sc,
                    "course_competency": competency,
                    "evaluator_kind": "Mentor",
                    "stage": "Final",
                    "status": "Submitted",
                },
                pluck="instructor",
            )
        )
        owed = [e for e in verdict_evaluators if e not in submitted]
        if owed:
            return {
                "state": "awaiting_mentor",
                "label": ", ".join(names.get(e, e) for e in owed),
                "owed": owed,
            }
        return {"state": "awaiting_result", "label": ""}
    if (
        cbe.final_self_eval_required(framework)
        and _activities_done(roster_doc, competency)
        and not cbe._self_assessment_submitted(
            roster_doc.student, roster_doc.course_sc, competency
        )
    ):
        return {"state": "awaiting_self", "label": ""}
    if _any_activity(roster_doc, competency):
        return {"state": "working", "label": ""}
    return {"state": "not_started", "label": ""}


@frappe.whitelist()
def get_cbe_overview(
    program=None,
    cohort=None,
    academic_term=None,
    course_schedule=None,
    include_closed=0,
):
    school, scope = _viewer_scope()
    if not school and not scope:
        frappe.throw(
            _("This page is for academic staff and mentors."), frappe.PermissionError
        )

    states = list(OPEN_STATES) + (["Closed"] if cint(include_closed) else [])
    filters = {"workflow_state": ("in", states)}
    if academic_term:
        filters["academic_term"] = academic_term
    if course_schedule:
        filters["name"] = course_schedule
    if scope is not None:
        filters["name"] = (
            ("in", [course_schedule] if course_schedule in scope else [""])
            if course_schedule
            else ("in", scope or [""])
        )
    sections = [
        cs
        for cs in frappe.get_all(
            "Course Schedule",
            filters=filters,
            fields=[
                "name",
                "course",
                "academic_term",
                "c_dateend",
                "open_ended",
                "workflow_state",
            ],
            order_by="course asc, name asc",
        )
        if cbe.framework_for(cs.name)
    ]
    wanted = _students_in(program, cohort)
    today = nowdate()

    groups, mentors = [], {}
    names_cache = {}
    for cs in sections:
        framework = cbe.framework_doc(cs.name)
        visible = cbe.visible_students(cs.name) if not school else None
        competencies = frappe.get_all(
            "Course Competency",
            filters={"course": cs.course, "is_active": 1},
            fields=["name", "competency_name", "competency_code"],
            order_by="sequence asc",
        )
        expected = _expected_days(cs.course) if cint(cs.open_ended) else None
        stall = cint(framework.stall_escalation_days)
        rows = []
        for r in frappe.get_all(
            "Scheduled Course Roster",
            filters={"course_sc": cs.name, "audit_bool": 0},
            fields=["name", "student", "stuname_roster", "active", "creation"],
            order_by="stuname_roster asc",
        ):
            if visible is not None and r.student not in visible:
                continue
            if wanted is not None and r.student not in wanted:
                continue
            roster_doc = frappe.get_doc("Scheduled Course Roster", r.name)
            evaluators = cbe.evaluators_for(roster_doc)
            for e in evaluators:
                if e["instructor"] not in names_cache:
                    names_cache[e["instructor"]] = (
                        frappe.db.get_value(
                            "Instructor", e["instructor"], "instructor_name"
                        )
                        or e["instructor"]
                    )
            verdict = [
                e["instructor"] for e in evaluators if e["gives_competency_verdict"]
            ]
            results = {
                x.course_competency: x
                for x in frappe.get_all(
                    "Competency Result",
                    filters={"student": r.student, "course_schedule": cs.name},
                    fields=["course_competency", "status", "final_code"],
                )
            }
            cells = [
                {
                    "competency": c.name,
                    **_cell(
                        roster_doc,
                        c.name,
                        framework,
                        verdict,
                        names_cache,
                        results.get(c.name),
                    ),
                }
                for c in competencies
            ]
            undecided = any(c["state"] != "decided" for c in cells)
            last = _last_activity(r.student, cs.name)

            lagging = []
            if r.active and undecided:
                idle_since = last or getdate(r.creation)
                idle = date_diff(today, idle_since)
                if stall and idle > stall:
                    lagging.append(
                        {
                            "reason": "stalled",
                            "label": _("No activity for {0} days").format(idle),
                        }
                    )
                if (
                    not cint(cs.open_ended)
                    and cs.c_dateend
                    and getdate(cs.c_dateend) < getdate(today)
                ):
                    lagging.append(
                        {
                            "reason": "ended",
                            "label": _("Course ended with competencies undecided"),
                        }
                    )
                if expected:
                    enrolled = date_diff(today, getdate(r.creation))
                    if enrolled > expected:
                        lagging.append(
                            {
                                "reason": "pace",
                                "label": _(
                                    "{0} days in; most students finish within {1}"
                                ).format(enrolled, expected),
                            }
                        )

            rows.append(
                {
                    "roster": r.name,
                    "student": r.student,
                    "student_name": r.stuname_roster,
                    "finalized": not r.active,
                    "last_activity": last,
                    "cells": cells,
                    "lagging": lagging,
                }
            )

            # The mentor lens, built from the same rows.
            for e in evaluators:
                if not e["gives_competency_verdict"]:
                    continue
                m = mentors.setdefault(
                    e["instructor"],
                    {
                        "instructor": e["instructor"],
                        "instructor_name": names_cache[e["instructor"]],
                        "categories": set(),
                        "mentees": set(),
                        "due": 0,
                        "oldest_due_days": None,
                        "plans_to_review": 0,
                    },
                )
                m["categories"].add(e["instructor_category"])
                m["mentees"].add(r.student)
                for c in cells:
                    if c["state"] == "awaiting_mentor" and e["instructor"] in c.get(
                        "owed", []
                    ):
                        m["due"] += 1
                        age = date_diff(today, last) if last else None
                        if age is not None and (
                            m["oldest_due_days"] is None or age > m["oldest_due_days"]
                        ):
                            m["oldest_due_days"] = age
                if frappe.db.exists(
                    "Personal Development Plan",
                    {"roster": r.name, "status": "Submitted"},
                ):
                    m["plans_to_review"] += 1

        if rows:
            groups.append(
                {
                    "course_schedule": cs.name,
                    "course": cs.course,
                    "academic_term": cs.academic_term,
                    "open_ended": cint(cs.open_ended),
                    "competencies": competencies,
                    "rows": rows,
                }
            )

    for c in groups:
        for r in c["rows"]:
            for cell in r["cells"]:
                cell.pop("owed", None)

    mentor_rows = sorted(
        (
            {
                **m,
                "categories": sorted(m["categories"]),
                "mentees": len(m["mentees"]),
            }
            for m in mentors.values()
        ),
        key=lambda m: (-m["due"], -(m["oldest_due_days"] or 0), m["instructor_name"]),
    )
    return {
        "school": school,
        "sections": groups,
        "mentors": mentor_rows if school else [],
        "filters": _filter_options(scope),
    }


def _filter_options(scope):
    programs = frappe.get_all(
        "Program",
        filters={"competency_framework": ("is", "set")},
        pluck="name",
        order_by="name asc",
    )
    cs_filters = {
        "workflow_state": ("in", list(OPEN_STATES) + ["Closed"]),
    }
    if scope is not None:
        cs_filters["name"] = ("in", scope or [""])
    sections = [
        cs
        for cs in frappe.get_all(
            "Course Schedule",
            filters=cs_filters,
            fields=["name", "course", "academic_term"],
            order_by="name asc",
        )
        if cbe.framework_for(cs.name)
    ]
    terms = sorted({s.academic_term for s in sections if s.academic_term})
    cohort_types = set()
    for p in programs:
        fw = frappe.db.get_value("Program", p, "competency_framework")
        if fw:
            cohort_types |= {
                r.cohort_type
                for r in cbe.cohort_evaluator_rows(
                    frappe.get_cached_doc("Competency Framework", fw)
                )
            }
    cohorts = (
        frappe.get_all(
            "Cohort",
            filters={"cohort_type": ("in", list(cohort_types)), "status": "Active"},
            fields=["name", "cohort_name"],
            order_by="cohort_name asc",
        )
        if cohort_types
        else []
    )
    return {
        "programs": programs,
        "terms": terms,
        "sections": [
            {"value": s.name, "label": f"{s.course} · {s.name}"} for s in sections
        ],
        "cohorts": [
            {"value": c.name, "label": c.cohort_name or c.name} for c in cohorts
        ],
    }
