# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""The cohort planner's pool queries and matcher (ADR 067 sections 5 and 6).

Nothing here writes. `propose()` is a pure function of the site's data and the
arguments it is given: it can be run, re-run and thrown away, which is what lets
the page treat a proposal as disposable and lets these tests assert on it
without a teardown.

The matcher decides **how many groups** before it places anybody. Walking the
students and giving each one their best mentor -- the shape an on-enrollment
trigger forces -- spreads a small intake across every available mentor and
produces exactly the undersized groups `automation_min_size` exists to prevent.
With the whole set in hand the count is arithmetic instead of an accident.

Choosing *which* mentors lead is a facility-location problem and this solves it
greedily, on purpose: an optimum nobody can explain is worse than a good
arrangement a chair can adjust, and adjusting it is what the page is for.
"""

import frappe
from frappe import _

from seminary.seminary import faculty
from seminary.seminary.discipleship import criteria as rules

COHORT_MENTORSHIP_ROUTE = "Program Cohort Mentorship"


def _json_capacity(remaining):
    """`float("inf")` is not JSON.

    `faculty._remaining` returns infinity for an uncapped capability, which is
    the right value to compare against and an impossible one to send: Python
    serialises it as the bare token `Infinity`, which `JSON.parse` rejects, so
    the whole proposal would arrive at the browser as a parse error. None says
    the same thing -- no ceiling -- in a shape a client can read.
    """
    return None if remaining == float("inf") else remaining


#: Which students to offer. Every scope is a subset of "needs placement" -- a
#: person with an active membership of the type is never in the pool, because
#: placement happens once (ADR 066 section 3).
SCOPE_ALL = "all"
SCOPE_NEVER = "never"
SCOPE_FORMER = "former"
SCOPES = (SCOPE_ALL, SCOPE_NEVER, SCOPE_FORMER)

#: The person columns every rule reads, loaded once per run.
_PERSON_FIELDS = (
    "name",
    "full_name",
    "gender",
    "latitude",
    "longitude",
    "geo_status",
)


# ---------------------------------------------------------------- person rows


def _person_rows(person_names):
    """One dict per person, with `has_point` already decided.

    `geo_status`, not latitude, is the presence signal: Frappe's Float columns
    are NOT NULL DEFAULT 0, so an unresolved coordinate reads as 0.0, 0.0 -- a
    real place in the Gulf of Guinea, and one that would rank as plausibly near
    somebody.

    Read with `frappe.db.get_all`, which does not apply permlevel. That is
    deliberate and it is the only way these fields are read: the planner needs
    the point to compute a distance, and returns the distance, never the point.
    """
    if not person_names:
        return {}
    rows = frappe.db.get_all(
        "Person",
        filters={"name": ["in", list(person_names)]},
        fields=list(_PERSON_FIELDS),
    )
    out = {}
    for row in rows:
        row = dict(row)
        row["has_point"] = row.get("geo_status") == "Resolved"
        out[row["name"]] = row
    return out


# ----------------------------------------------------------------- the pools


def _bound_programs(cohort_type):
    """The programs whose enrolled students this type is about.

    A type binds to a Program or to a Program Level, never both -- `Cohort
    Type.validate_binding` refuses the pair -- so this is one branch, not a
    merge.
    """
    row = frappe.db.get_value(
        "Cohort Type", cohort_type, ["program", "program_level"], as_dict=True
    )
    if not row:
        return []
    if row.program:
        return [row.program]
    if row.program_level:
        return frappe.get_all(
            "Program", filters={"program_level": row.program_level}, pluck="name"
        )
    return []


def _membership_history(cohort_type):
    """(ever, active) person sets for this cohort type.

    One query for the type's cohorts and one for their memberships, rather than
    `active_cohort_of_type` per student: that helper is right for one person at
    a decision point and wrong for a pool of four hundred.
    """
    cohorts = frappe.get_all(
        "Cohort", filters={"cohort_type": cohort_type}, pluck="name"
    )
    if not cohorts:
        return set(), set()
    rows = frappe.get_all(
        "Cohort Membership",
        filters={"cohort": ["in", cohorts]},
        fields=["person", "active"],
    )
    ever = {r.person for r in rows}
    active = {r.person for r in rows if r.active}
    return ever, active


def students_needing_placement(cohort_type, scope=SCOPE_ALL):
    """Students of the type's bound program(s) with no active cohort of it.

    Returns dicts carrying the Person, the Student and the enrollment that put
    them in the pool -- the planner writes memberships against the Person, but a
    chair reading the page thinks in students.
    """
    if scope not in SCOPES:
        frappe.throw(_("Unknown student selection."))

    programs = _bound_programs(cohort_type)
    if not programs:
        return []

    enrollments = frappe.get_all(
        "Program Enrollment",
        filters={
            "program": ["in", programs],
            "docstatus": 1,
            "status": ["in", ("Active", "Leave of Absence")],
        },
        fields=["name", "student", "student_name", "program"],
        order_by="student_name asc",
    )
    if not enrollments:
        return []

    students = {e.student for e in enrollments}
    persons = {
        r.name: r.person
        for r in frappe.get_all(
            "Student",
            filters={"name": ["in", list(students)]},
            fields=["name", "person"],
        )
        if r.person
    }

    ever, active = _membership_history(cohort_type)

    out = []
    seen = set()
    for row in enrollments:
        person = persons.get(row.student)
        # A Student without a Person cannot be placed: a Cohort Membership is
        # keyed on the Person, not the role record. Since ADR 068 `person` is
        # reqd, so this only skips rows predating that.
        if not person or person in seen or person in active:
            continue
        if scope == SCOPE_NEVER and person in ever:
            continue
        if scope == SCOPE_FORMER and person not in ever:
            continue
        seen.add(person)
        out.append(
            {
                "person": person,
                "student": row.student,
                "student_name": row.student_name,
                "program": row.program,
                "program_enrollment": row.name,
            }
        )
    return out


def mentor_pool(unit, exclude=()):
    """Instructors in `unit` wired to the mentorship route with capacity left.

    `faculty.eligible_instructors` already drops anyone at their ceiling and
    returns them most-available first. What it does not do is resolve the
    Person, which is what a Cohort's leader is and what every rule reads.
    """
    exclude = set(exclude or ())
    rows = faculty.eligible_instructors(unit, COHORT_MENTORSHIP_ROUTE)
    if not rows:
        return []

    instructors = [r["instructor"] for r in rows if r["instructor"] not in exclude]
    if not instructors:
        return []
    persons = {
        r.name: r.person
        for r in frappe.get_all(
            "Instructor",
            filters={"name": ["in", instructors]},
            fields=["name", "person"],
        )
        if r.person
    }

    out = []
    for row in rows:
        person = persons.get(row["instructor"])
        if not person:
            continue
        out.append(
            {
                "instructor": row["instructor"],
                "person": person,
                "unit": row["unit"],
                "membership": row["membership"],
                "remaining": row["remaining"],
            }
        )
    return out


# ------------------------------------------------------------------ the rules


def criteria_for(cohort_type):
    """The type's rules, in `idx` order, as (row, handler) pairs.

    A rule whose catalog entry has been retired is dropped rather than run --
    `is_active` is how a school withdraws one, and honouring it only in the
    picker would leave it silently deciding placements.
    """
    rows = frappe.get_all(
        "Cohort Type Criterion",
        filters={"parent": cohort_type, "parenttype": "Cohort Type"},
        fields=["criterion", "idx"],
        order_by="idx asc",
        ignore_permissions=True,
    )
    if not rows:
        return []
    catalog = {
        r.name: r
        for r in frappe.get_all(
            "Cohort Assignment Criterion",
            filters={"name": ["in", [r.criterion for r in rows]]},
            fields=["name", "handler", "is_active"],
        )
    }
    out = []
    for row in rows:
        entry = catalog.get(row.criterion)
        if not entry or not entry.is_active:
            continue
        handler = rules.get(entry.handler)
        if handler:
            out.append(handler)
    return out


def _split(handlers):
    filters = [h for h in handlers if h.kind == rules.FILTER]
    rankings = [h for h in handlers if h.kind == rules.RANKING]
    return filters, rankings


def _eligible(student_row, mentor_row, filters):
    """(ok, reason). The first refusal wins and is the one reported."""
    for handler in filters:
        reason = handler.excludes(student_row, mentor_row)
        if reason:
            return False, reason
    return True, None


def _sort_key(student_row, mentor, mentor_row, rankings):
    """Rankings in `idx` order, then a stable tie-break.

    The tie-break ends in the opaque Person id and never in a name: `full_name`
    is neither unique nor collation-stable, so two mentors called John Smith
    would get a coin flip nobody could reproduce.
    """
    return tuple(h.rank(student_row, mentor_row) for h in rankings) + (
        mentor["person"],
    )


# ---------------------------------------------------------------- group count


def group_count(n_students, min_size, max_size):
    """How many cohorts to open, decided before anybody is placed.

    The ceiling says how few groups the students can fit into; the floor says
    how many groups can still be a decent size. When they disagree the floor
    wins, because an oversized group is a warning and an undersized one is a
    cohort that does not work.

    Either bound may be 0, meaning "unbounded", and a school with three students
    and ten mentors gets one flagged group of three rather than three pairs.
    """
    if n_students <= 0:
        return 0
    upper = -(-n_students // max_size) if max_size else 1
    lower = (n_students // min_size) if min_size else upper
    return max(1, min(upper, lower) if lower else upper)


def _greedy_seed(students, mentors, n_groups, person_rows, filters, rankings):
    """Pick the mentors who will lead, one at a time.

    Each round takes the mentor who is the best available choice for the most
    students still unserved. That is an approximation of a facility-location
    problem and is stated as one -- see this module's docstring for why an
    approximation is the right answer here.
    """
    chosen = []
    remaining = list(mentors)
    unserved = list(students)

    while remaining and len(chosen) < n_groups and unserved:
        best = None
        for mentor in remaining:
            mentor_row = person_rows.get(mentor["person"], {})
            score = []
            for student in unserved:
                student_row = person_rows.get(student["person"], {})
                ok, _reason = _eligible(student_row, mentor_row, filters)
                if ok:
                    score.append(_sort_key(student_row, mentor, mentor_row, rankings))
            if not score:
                continue
            # Serves the most people, and among equals the one whose people are
            # best served -- otherwise a mentor eligible for everyone but far
            # from all of them would win every round.
            key = (-len(score), sorted(score)[: max(1, len(score) // 2)])
            if best is None or key < best[0]:
                best = (key, mentor, score)
        if best is None:
            break
        chosen.append(best[1])
        remaining.remove(best[1])
        served = {
            s["person"]
            for s in unserved
            if _eligible(
                person_rows.get(s["person"], {}),
                person_rows.get(best[1]["person"], {}),
                filters,
            )[0]
        }
        unserved = [s for s in unserved if s["person"] not in served]

    # Every student is covered, or nobody left can cover them; if groups remain
    # to be opened, fill them with the most-available mentors so the ceiling is
    # honoured rather than the seeding stopping early.
    for mentor in remaining:
        if len(chosen) >= n_groups:
            break
        chosen.append(mentor)
    return chosen


# ------------------------------------------------------------------- proposal


def _planning_settings(cohort_type):
    row = frappe.db.get_value(
        "Cohort Type",
        cohort_type,
        [
            "name",
            "plannable",
            "mentor_unit",
            "automation_min_size",
            "automation_max_size",
        ],
        as_dict=True,
    )
    if not row:
        frappe.throw(_("{0} is not a Cohort Type.").format(cohort_type))
    if not row.plannable:
        frappe.throw(
            _("{0} is not set up for bulk planning.").format(frappe.bold(cohort_type))
        )
    if not row.mentor_unit:
        frappe.throw(
            _(
                "{0} has no Mentor Unit, so there is no pool to draw mentors "
                "from. Set one on the Cohort Type."
            ).format(frappe.bold(cohort_type))
        )
    return row


def require_planner(unit):
    """Staff who may write a Cohort, or the mentoring unit's own chair.

    The chair is named on the unit as an Instructor; the planner is the one
    place they act on their own department without needing a site-wide role.
    """
    if faculty.has_full_access():
        return
    chair = frappe.db.get_value("Academic Unit", unit, "chair")
    if chair and chair == faculty.current_instructor():
        return
    frappe.throw(
        _("Only staff or the mentoring unit's chair may plan cohorts."),
        frappe.PermissionError,
    )


def distance_unit():
    return frappe.db.get_single_value("Seminary Settings", "distance_unit") or rules.KM


def propose(cohort_type, scope=SCOPE_ALL, exclude_mentors=(), handlers=None):
    """Build a set of cohorts-to-create. Writes nothing.

    `handlers` overrides the type's configured rules for this run only. A chair
    trying the intake with and without gender matching is running an experiment,
    not amending policy, so the deviation never reaches the Cohort Type.
    """
    settings = _planning_settings(cohort_type)
    require_planner(settings.mentor_unit)
    rules.using_unit(distance_unit())

    if handlers is None:
        handlers = criteria_for(cohort_type)
    filters, rankings = _split(handlers)

    students = students_needing_placement(cohort_type, scope)
    mentors = mentor_pool(settings.mentor_unit, exclude=exclude_mentors)
    person_rows = _person_rows(
        [s["person"] for s in students] + [m["person"] for m in mentors]
    )
    for row in students + mentors:
        row["full_name"] = person_rows.get(row["person"], {}).get("full_name")

    min_size = settings.automation_min_size or 0
    max_size = settings.automation_max_size or 0
    n_groups = group_count(len(students), min_size, max_size)

    leaders = _greedy_seed(students, mentors, n_groups, person_rows, filters, rankings)
    groups = {
        m["person"]: {
            "key": m["person"],
            "mentor": m["instructor"],
            "mentor_person": m["person"],
            "mentor_name": person_rows.get(m["person"], {}).get("full_name"),
            "remaining": _json_capacity(m["remaining"]),
            "suggested_name": "%s — %s"
            % (cohort_type, person_rows.get(m["person"], {}).get("full_name") or ""),
            "members": [],
        }
        for m in leaders
    }

    # Most-constrained first: a student with one eligible mentor must not lose
    # the last seat to a student who had ten choices.
    def _options(student):
        student_row = person_rows.get(student["person"], {})
        return [
            m
            for m in leaders
            if _eligible(student_row, person_rows.get(m["person"], {}), filters)[0]
        ]

    ordered = sorted(
        students, key=lambda s: (len(_options(s)), s["student_name"] or "")
    )

    unplaced = []
    shortlists = {}
    for student in ordered:
        student_row = person_rows.get(student["person"], {})
        ranked = sorted(
            _options(student),
            key=lambda m: _sort_key(
                student_row, m, person_rows.get(m["person"], {}), rankings
            ),
        )
        shortlists[student["person"]] = [m["person"] for m in ranked]

        if not ranked:
            unplaced.append(
                dict(
                    student,
                    reason=_no_match_reason(student_row, leaders, person_rows, filters),
                )
            )
            continue

        seated = None
        for mentor in ranked:
            group = groups[mentor["person"]]
            if max_size and len(group["members"]) >= max_size:
                continue
            if len(group["members"]) >= mentor["remaining"]:
                continue
            seated = mentor
            break
        if seated is None:
            unplaced.append(
                dict(
                    student,
                    reason=_("Every mentor who could take this student is full."),
                )
            )
            continue

        group = groups[seated["person"]]
        alternatives = [
            person_rows.get(m["person"], {}) for m in ranked if m is not seated
        ]
        notes = [
            n
            for n in (
                h.note(student_row, person_rows.get(seated["person"], {}), alternatives)
                for h in handlers
            )
            if n
        ]
        group["members"].append(
            dict(
                student,
                notes=notes,
                placed_by_rule=_rule_stamp(handlers),
            )
        )

    ordered_groups = [groups[m["person"]] for m in leaders]
    for group in ordered_groups:
        group["below_minimum"] = bool(min_size and 0 < len(group["members"]) < min_size)
        group["size"] = len(group["members"])

    return {
        "cohort_type": cohort_type,
        "unit": settings.mentor_unit,
        "scope": scope,
        "min_size": min_size,
        "max_size": max_size,
        "distance_unit": distance_unit(),
        "criteria": [h.handler for h in handlers],
        "groups": [g for g in ordered_groups if g["members"]],
        "empty_groups": [g for g in ordered_groups if not g["members"]],
        "unplaced": unplaced,
        "shortlists": shortlists,
        "pool": {"students": len(students), "mentors": len(mentors)},
    }


def _rule_stamp(handlers):
    """What chose this pairing, for the membership's audit stamp.

    A hand-drag replaces it, which is the whole point of recording it: the
    difference between a rule the school can change and a judgement one person
    made.
    """
    if not handlers:
        return _("Proposed by the planner (no matching rules configured).")
    return _("Proposed by the planner: {0}.").format(
        ", ".join(str(h.label) for h in handlers)
    )


def _no_match_reason(student_row, leaders, person_rows, filters):
    """Why this student's pool came out empty -- the first refusal, not a count.

    A chair needs the datum to fix, and "no mentor matched" is not one.
    """
    if not leaders:
        return _("No mentor in this unit has capacity.")
    for mentor in leaders:
        ok, reason = _eligible(
            student_row, person_rows.get(mentor["person"], {}), filters
        )
        if not ok:
            return reason
    return _("No mentor matched.")


# --------------------------------------------------------------------- api


@frappe.whitelist()
def planner_setup(cohort_type):
    """Everything the planner's first screen needs, before any matching.

    Includes the readiness counts (ADR 067 section 11): a mentor pool missing a
    datum makes a rule inoperable, while one student missing it makes that one
    student unplaced -- so mentor gaps and student gaps are reported separately
    rather than summed into a single scary number.
    """
    settings = _planning_settings(cohort_type)
    require_planner(settings.mentor_unit)

    mentors = mentor_pool(settings.mentor_unit)
    handlers = criteria_for(cohort_type)
    counts = {}
    for scope in SCOPES:
        counts[scope] = len(students_needing_placement(cohort_type, scope))

    students = students_needing_placement(cohort_type, SCOPE_ALL)
    person_rows = _person_rows(
        [s["person"] for s in students] + [m["person"] for m in mentors]
    )
    readiness = []
    for handler in handlers:
        readiness.append(
            {
                "criterion": handler.handler,
                "label": handler.label,
                "reads": handler.requires_field,
                "mentors_missing": sum(
                    1
                    for m in mentors
                    if handler.missing(person_rows.get(m["person"], {}))
                ),
                "mentors_total": len(mentors),
                "students_missing": sum(
                    1
                    for s in students
                    if handler.missing(person_rows.get(s["person"], {}))
                ),
                "students_total": len(students),
            }
        )

    return {
        "cohort_type": cohort_type,
        "unit": settings.mentor_unit,
        "unit_name": frappe.db.get_value(
            "Academic Unit", settings.mentor_unit, "unit_name"
        ),
        "min_size": settings.automation_min_size or 0,
        "max_size": settings.automation_max_size or 0,
        "distance_unit": distance_unit(),
        "scopes": counts,
        "criteria": [
            {"handler": h.handler, "label": h.label, "kind": h.kind} for h in handlers
        ],
        "mentors": [
            {
                "instructor": m["instructor"],
                "person": m["person"],
                "full_name": person_rows.get(m["person"], {}).get("full_name"),
                "remaining": _json_capacity(m["remaining"]),
            }
            for m in mentors
        ],
        "readiness": readiness,
    }


@frappe.whitelist()
def plannable_types():
    """Cohort Types the planner will accept, for the first picker."""
    rows = frappe.get_all(
        "Cohort Type",
        filters={"plannable": 1, "is_active": 1},
        fields=["name", "category", "program", "program_level", "mentor_unit"],
        order_by="name asc",
    )
    return [r for r in rows if r.mentor_unit]


@frappe.whitelist()
def build_proposal(cohort_type, scope=SCOPE_ALL, exclude_mentors=None, criteria=None):
    """Whitelisted `propose`. Writes nothing, so it is safe to re-run.

    `criteria`, when given, overrides the type's configured rules for this run.
    It is validated against the registry rather than trusted: a whitelisted
    method takes whatever a client sends.
    """
    exclude_mentors = frappe.parse_json(exclude_mentors) if exclude_mentors else []
    handlers = None
    if criteria is not None:
        wanted = frappe.parse_json(criteria) if isinstance(criteria, str) else criteria
        handlers = []
        for handler in wanted or []:
            known = rules.get(handler)
            if not known:
                frappe.throw(_("Unknown matching rule."))
            handlers.append(known)
    return propose(
        cohort_type,
        scope=scope,
        exclude_mentors=exclude_mentors,
        handlers=handlers,
    )
