# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Advance Students, one program step at a time (ADR 083 §4).

A step is one program's students moving from term index N to N+1 out of one
Academic Term. It is Ready only when every section those students hold an
enrollment in that term is Closed (Send Grades is the only way there), and a
student leaves a given Academic Term once: `Program Enrollment.advanced_from_term`
records it. That marker, not the order steps are run in, is what stops the
students just moved from 1 to 2 being picked up again by the 2 → 3 step.

Only active enrollments move, as before. A student whose intake term starts
after the closing term has not started yet and is left out.
"""

import frappe
from frappe import _
from frappe.utils import formatdate, getdate, today

ADVANCE_ROLES = ["Registrar", "Seminary Manager", "System Manager"]

READY, BLOCKED, DONE, FINAL = "Ready", "Blocked", "Done", "Final"


def default_closing_term():
    """The latest Academic Term that has ended."""
    rows = frappe.get_all(
        "Academic Term",
        filters={"term_end_date": ["<", today()]},
        order_by="term_end_date desc",
        pluck="name",
        limit=1,
    )
    return rows[0] if rows else None


def next_term(academic_term):
    """The Academic Term that starts after `academic_term`, or None."""
    start = frappe.db.get_value("Academic Term", academic_term, "term_start_date")
    if not start:
        return None
    rows = frappe.get_all(
        "Academic Term",
        filters={"term_start_date": [">", start]},
        order_by="term_start_date asc",
        pluck="name",
        limit=1,
    )
    return rows[0] if rows else None


def _enrollments(academic_term, program=None):
    start = frappe.db.get_value("Academic Term", academic_term, "term_start_date")
    conditions = [
        "pe.docstatus = 1",
        "pe.pgmenrol_active = 1",
        "(intake.term_start_date IS NULL OR %(start)s IS NULL"
        " OR intake.term_start_date <= %(start)s)",
    ]
    params = {"start": start, "term": academic_term}
    if program:
        conditions.append("pe.program = %(program)s")
        params["program"] = program
    return frappe.db.sql(
        f"""SELECT pe.name, pe.program, pe.current_std_term, pe.advanced_from_term,
                   pe.advanced_on, p.terms_complete
            FROM `tabProgram Enrollment` pe
            INNER JOIN `tabProgram` p ON p.name = pe.program
            LEFT JOIN `tabAcademic Term` intake ON intake.name = pe.academic_term
            WHERE {" AND ".join(conditions)}
            ORDER BY pe.program, pe.current_std_term""",  # nosec B608 -- clauses are constants from this function
        params,
        as_dict=True,
    )


def _open_sections(pe_names, academic_term):
    """Sections in `academic_term` where these students hold a live enrollment
    and grades have not been sent. Cancelled and open-ended (self-paced) sections
    don't count: they don't follow the term."""
    if not pe_names:
        return []
    return frappe.db.sql(
        """SELECT DISTINCT cs.name
           FROM `tabCourse Enrollment Individual` cei
           INNER JOIN `tabCourse Schedule` cs ON cs.name = cei.coursesc_ce
           WHERE cei.program_ce IN %(pes)s
             AND cei.docstatus = 1
             AND cei.withdrawn = 0
             AND cei.course_cancelled = 0
             AND cs.academic_term = %(term)s
             AND COALESCE(cs.open_ended, 0) = 0
             AND COALESCE(cs.workflow_state, '') NOT IN ('Closed', 'Cancelled')
           ORDER BY cs.name""",
        {"pes": tuple(pe_names), "term": academic_term},
        pluck=True,
    )


def compute_steps(academic_term, program=None):
    """One row per program step, each with its status and students."""
    if not academic_term:
        return []
    groups = {}
    for pe in _enrollments(academic_term, program):
        n = pe.current_std_term or 0
        if pe.advanced_from_term == academic_term:
            # Already moved out of this term: show it under the step it took.
            key = (pe.program, n - 1, DONE)
        elif pe.terms_complete and n >= pe.terms_complete:
            key = (pe.program, n, FINAL)
        else:
            key = (pe.program, n, None)
        groups.setdefault(key, []).append(pe)

    steps = []
    for (prog, n, fixed), pes in groups.items():
        names = [p.name for p in pes]
        step = frappe._dict(
            program=prog,
            from_term=n,
            to_term=n + 1,
            students=len(pes),
            enrollments=names,
            sections=[],
            status=fixed,
            done_on=None,
        )
        if fixed == DONE:
            dates = [getdate(p.advanced_on) for p in pes if p.advanced_on]
            step.done_on = max(dates) if dates else None
        elif fixed is None:
            step.sections = _open_sections(names, academic_term)
            step.status = BLOCKED if step.sections else READY
        steps.append(step)

    order = {READY: 0, BLOCKED: 0, DONE: 1, FINAL: 2}
    steps.sort(key=lambda s: (s.program, order[s.status], s.from_term))
    return steps


def describe(step, advanced=False):
    """The sentence the registrar reads for one step."""
    if advanced:
        return _("Advanced {0} {1} students from term {2} to {3}.").format(
            step.students, step.program, step.from_term, step.to_term
        )
    if step.status == BLOCKED:
        return _(
            "{0} students in term {1} were not advanced: grades for {2} haven't been received."
        ).format(step.program, step.from_term, ", ".join(step.sections))
    if step.status == DONE:
        return _(
            "{0} students were already advanced from term {1} to {2} on {3}."
        ).format(step.program, step.from_term, step.to_term, formatdate(step.done_on))
    if step.status == FINAL:
        return _("{0} students in term {1} are in the program's final term.").format(
            step.program, step.from_term
        )
    return _("{0} students in term {1} were not selected.").format(
        step.program, step.from_term
    )


def _public(step):
    return {
        "program": step.program,
        "from_term": step.from_term,
        "to_term": step.to_term,
        "students": step.students,
        "status": step.status,
        "sections": step.sections,
        "done_on": step.done_on,
    }


@frappe.whitelist()
def get_steps(academic_term=None, program=None):
    """What Advance Students offers for a closing term, before any click."""
    frappe.only_for(ADVANCE_ROLES)
    academic_term = academic_term or default_closing_term()
    return {
        "academic_term": academic_term,
        "next_term": next_term(academic_term) if academic_term else None,
        "steps": [_public(s) for s in compute_steps(academic_term, program or None)],
    }


@frappe.whitelist()
def advance(academic_term, steps, program=None):
    """Advance the chosen steps. `steps` is [{program, from_term}]. Every step is
    checked again here; one that is no longer Ready is skipped with its reason,
    so a stale dialog, a double click or an API call can't move anyone early or
    twice."""
    frappe.only_for(ADVANCE_ROLES)
    if not academic_term or not frappe.db.exists("Academic Term", academic_term):
        frappe.throw(_("Choose the term being closed."))
    wanted = {
        (s["program"], int(s["from_term"])) for s in frappe.parse_json(steps) or []
    }

    messages, advanced = [], []
    for step in compute_steps(academic_term, program or None):
        key = (step.program, step.from_term)
        if step.status == READY and key in wanted:
            moved = _advance_step(step, academic_term)
            step.students = moved
            messages.append({"status": "Advanced", "message": describe(step, True)})
            advanced.append(
                {
                    "program": step.program,
                    "to_term": step.to_term,
                    "time_based": frappe.db.get_value(
                        "Program", step.program, "program_type"
                    )
                    == "Time-based",
                }
            )
        elif step.status == FINAL:
            continue
        elif step.status == DONE and key not in wanted:
            continue
        else:
            messages.append({"status": step.status, "message": describe(step)})
    return {
        "messages": messages,
        "advanced": advanced,
        "next_term": next_term(academic_term),
    }


def _advance_step(step, academic_term):
    moved, on = 0, today()
    for name in step.enrollments:
        # Lock the row and look again: another registrar may have got here first.
        current = frappe.db.get_value(
            "Program Enrollment",
            name,
            ["current_std_term", "advanced_from_term"],
            as_dict=True,
            for_update=True,
        )
        if current.advanced_from_term == academic_term:
            continue
        frappe.db.set_value(
            "Program Enrollment",
            name,
            {
                "current_std_term": (current.current_std_term or 0) + 1,
                "advanced_from_term": academic_term,
                "advanced_on": on,
            },
        )
        moved += 1
    return moved
