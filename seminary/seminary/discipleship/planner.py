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


def eligibility_classes(students, mentors, person_rows, filters):
    """Students grouped by *which* mentors may take them.

    A Filter is a predicate over (student, mentor), but when the mentors are
    themselves split by the same attribute it induces a partition over the
    **students**: under gender matching the men and the women are two pools that
    share no mentor, and a group count taken over the total is a count of a set
    that can never be one cohort.

    That was a real defect. Six students at a maximum of six produced one group,
    one seeded mentor, and every student of the other gender unplaced with a
    correct-but-useless reason -- while an eligible mentor sat in the pool.
    """
    classes = {}
    for student in students:
        row = person_rows.get(student["person"], {})
        key = frozenset(
            m["person"]
            for m in mentors
            if _eligible(row, person_rows.get(m["person"], {}), filters)[0]
        )
        classes.setdefault(key, []).append(student)
    return classes


def _class_score(members, mentor, person_rows, rankings):
    """How well one mentor serves one class of students, lowest is best.

    The better half of their sort keys rather than the mean: a mentor who is
    ideal for four students and hopeless for one should beat a mentor who is
    mediocre for all five, because the four will keep them and the fifth can be
    dragged.
    """
    mentor_row = person_rows.get(mentor["person"], {})
    keys = sorted(
        _sort_key(person_rows.get(s["person"], {}), mentor, mentor_row, rankings)
        for s in members
    )
    return keys[: max(1, len(keys) // 2)]


def _greedy_seed(students, mentors, min_size, max_size, person_rows, filters, rankings):
    """Pick the mentors who will lead.

    Per eligibility class, not over the pool as a whole: each class gets the
    number of groups its own size warrants, and mentors already seeded for an
    overlapping class count towards it rather than being seeded twice.

    Which mentors lead is a facility-location problem and this solves it
    greedily, on purpose -- see this module's docstring for why an approximation
    is the right answer here.
    """
    by_person = {m["person"]: m for m in mentors}
    classes = eligibility_classes(students, mentors, person_rows, filters)

    chosen = []
    chosen_keys = set()
    # Largest class first: it has the strongest claim on a mentor that several
    # classes could use.
    for eligible, members in sorted(classes.items(), key=lambda kv: -len(kv[1])):
        if not eligible:
            continue  # nobody can take these students; they end up unplaced
        want = group_count(len(members), min_size, max_size)
        have = sum(1 for person in chosen_keys if person in eligible)
        candidates = [by_person[p] for p in eligible if p not in chosen_keys]
        candidates.sort(key=lambda m: _class_score(members, m, person_rows, rankings))
        for mentor in candidates[: max(0, want - have)]:
            chosen.append(mentor)
            chosen_keys.add(mentor["person"])
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

    leaders = _greedy_seed(
        students, mentors, min_size, max_size, person_rows, filters, rankings
    )
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
        # Ranked over the whole **pool**, not only the seeded leaders: a chair
        # may open a cohort under a mentor the matcher did not choose -- a
        # mentor in the students' own timezone, say -- and the page has to know
        # whether the rules allow that pairing. Which of these are somewhere a
        # student can actually be dragged is a question about the groups now on
        # screen, so the page answers it rather than this.
        shortlists[student["person"]] = [
            m["person"]
            for m in sorted(
                (
                    m
                    for m in mentors
                    if _eligible(
                        student_row, person_rows.get(m["person"], {}), filters
                    )[0]
                ),
                key=lambda m: _sort_key(
                    student_row, m, person_rows.get(m["person"], {}), rankings
                ),
            )
        ]

        if not ranked:
            unplaced.append(
                dict(
                    student,
                    reason=_no_match_reason(student_row, mentors, person_rows, filters),
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

    pair_values, pair_suffix = _pair_values(handlers, students, mentors, person_rows)

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
        "pair_values": pair_values,
        "pair_suffix": pair_suffix,
        "pool": {"students": len(students), "mentors": len(mentors)},
    }


def _pair_values(handlers, students, mentors, person_rows):
    """Per-pair quantities the page re-renders after a drag.

    A moved student's note stops being true the moment they move -- "next
    nearest cohort 34 km" was measured against a cohort they are no longer in.
    The page cannot recompute it, because the coordinates never leave the server
    (ADR 067 section 10), so what leaves is the derived number, already in the
    school's unit, whenever a rule that publishes a quantity is in use.

    Covers **every** mentor in the pool, not only the ones the filters allow.
    How far apart two people live is a fact about them; whether the rules permit
    the pairing is a separate question. Restricting the matrix to eligible pairs
    meant that a chair who had deliberately overridden a filter -- which is the
    entire point of being able to drag -- was looking at a cohort with no
    distances in it.

    Sent as a matrix rather than fetched per drag. A round trip on every move is
    what makes a board of two hundred students unusable, and this is a few
    thousand small numbers.
    """
    handler = next((h for h in handlers if h.pair_suffix()), None)
    if not handler:
        return {}, None

    values = {}
    for student in students:
        student_row = person_rows.get(student["person"], {})
        row = {}
        for mentor in mentors:
            value = handler.pair_value(
                student_row, person_rows.get(mentor["person"], {})
            )
            if value is not None:
                row[mentor["person"]] = value
        if row:
            values[student["person"]] = row
    return values, handler.pair_suffix()


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


def _no_match_reason(student_row, mentors, person_rows, filters):
    """Why this student's pool came out empty -- the first refusal, not a count.

    A chair needs the datum to fix, and "no mentor matched" is not one.

    Asked of the whole **pool**, not of the seeded leaders. Since every
    non-empty eligibility class gets at least one leader, a student with no
    eligible leader has no eligible mentor at all -- and reporting "no mentor
    has capacity" because no group happened to open would name the wrong
    problem while a matching mentor sat free.
    """
    if not mentors:
        return _("No mentor in this unit has capacity.")
    for mentor in mentors:
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
                "reads_label": _(handler.reads_label or handler.requires_field),
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


# ----------------------------------------------------------------- applying


#: What a hand-drag stamps instead of the rules, so the audit can tell a rule
#: the school can change from a judgement one person made.
MANUAL_STAMP = "Moved by hand during planning"


def _drift(cohort_type, unit, groups):
    """What has moved since the proposal was built, as a list of sentences.

    Re-derives nothing from the client's payload -- it re-validates it. Trusting
    a client-computed proposal would make the drag interface a permission bypass:
    the browser could name any Person and any Instructor it liked.
    """
    problems = []
    wired = faculty.wired_instructors(unit, COHORT_MENTORSHIP_ROUTE)
    offered = {s["person"]: s for s in students_needing_placement(cohort_type)}
    _ever, active = _membership_history(cohort_type)

    seen = set()
    for group in groups:
        mentor = group.get("mentor")
        if mentor not in wired:
            problems.append(
                _("{0} is no longer a mentor in this unit.").format(
                    frappe.db.get_value("Instructor", mentor, "instructor_name")
                    or mentor
                )
            )
        for member in group.get("members") or []:
            person = member.get("person")
            if person in active:
                problems.append(
                    _(
                        "{0} has joined a cohort of this type since the plan was "
                        "made."
                    ).format(_person_label(person))
                )
            elif person not in offered:
                problems.append(
                    _(
                        "{0} is no longer in the group of students this plan was "
                        "made for."
                    ).format(_person_label(person))
                )
            elif person in seen:
                problems.append(
                    _("{0} appears in two of these cohorts.").format(
                        _person_label(person)
                    )
                )
            seen.add(person)
    return problems


def _person_label(person):
    return frappe.db.get_value("Person", person, "full_name") or person


@frappe.whitelist()
def create_cohorts(cohort_type, groups):
    """Apply a reviewed plan. All of it, or none of it.

    A half-applied plan is the one outcome nobody can review: some students
    notified, some not, and no record of which decision produced which. So any
    drift refuses the whole thing and says what moved, rather than applying the
    part that still fits.

    Capacity is checked here but is never a veto (ADR 067 sections 3 and 7). A
    mentor's ceiling may be a workload agreement, so going past it is the
    chair's call to make and theirs to confirm with that mentor -- the response
    carries the exceptions back, generated from what was actually written rather
    than from what the browser thought it was sending.
    """
    settings = _planning_settings(cohort_type)
    require_planner(settings.mentor_unit)
    groups = frappe.parse_json(groups) if isinstance(groups, str) else groups
    groups = [g for g in (groups or []) if (g.get("members") or [])]
    if not groups:
        frappe.throw(_("There is nothing to create."))

    # One placement at a time per unit, so two chairs planning the same pool
    # serialise instead of both spending the same last slot. Different units
    # never contend, because the lock is the unit row.
    frappe.db.get_value("Academic Unit", settings.mentor_unit, "name", for_update=True)

    problems = _drift(cohort_type, settings.mentor_unit, groups)
    if problems:
        frappe.throw(
            _("This plan is out of date and nothing has been created:<br>{0}").format(
                "<br>".join(frappe.utils.escape_html(p) for p in problems)
            )
        )

    created = []
    exceptions = []
    for group in groups:
        mentor = group["mentor"]
        person = frappe.db.get_value("Instructor", mentor, "person")
        if not person:
            frappe.throw(
                _("{0} has no Person record, so they cannot lead a cohort.").format(
                    mentor
                )
            )

        cohort = frappe.get_doc(
            {
                "doctype": "Cohort",
                "cohort_name": (group.get("name") or "").strip()
                or "%s — %s" % (cohort_type, _person_label(person)),
                "cohort_type": cohort_type,
                "leader": person,
                "status": "Active",
                "max_size": settings.automation_max_size or 0,
            }
        ).insert(ignore_permissions=True)

        before = faculty.capacity_for(
            settings.mentor_unit, COHORT_MENTORSHIP_ROUTE, mentor
        )
        for member in group["members"]:
            # Active, not Invited: an invite the student must accept leaves the
            # placement in limbo while the mentor's slot is already spent. A
            # reviewed batch is a decision taken, announced rather than proposed.
            frappe.get_doc(
                {
                    "doctype": "Cohort Membership",
                    "cohort": cohort.name,
                    "person": member["person"],
                    "role": "Member",
                    "invite_status": "Active",
                    "placed_by_rule": member.get("placed_by_rule") or MANUAL_STAMP,
                }
            ).insert(ignore_permissions=True)
            faculty.claim_for(settings.mentor_unit, COHORT_MENTORSHIP_ROUTE, mentor)

        after = faculty.capacity_for(
            settings.mentor_unit, COHORT_MENTORSHIP_ROUTE, mentor
        )
        if (
            after
            and after["max_students"]
            and (after["current_students"] > after["max_students"])
        ):
            exceptions.append(
                {
                    "mentor": mentor,
                    "mentor_name": _person_label(person),
                    "current_students": after["current_students"],
                    "max_students": after["max_students"],
                    "was": (before or {}).get("current_students"),
                }
            )
        created.append(
            {
                "cohort": cohort.name,
                "cohort_name": cohort.cohort_name,
                "mentor": mentor,
                "members": len(group["members"]),
            }
        )

    # No commit: this runs inside the request's transaction, so a failure
    # anywhere above leaves no orphan cohort and no half-spent capacity.
    return {"created": created, "over_capacity": exceptions}


#: A gap list is for acting on, not for browsing. Past this many the count is
#: the useful number and the answer is an import, not a form.
READINESS_DETAIL_LIMIT = 200

SIDE_MENTORS = "mentors"
SIDE_STUDENTS = "students"


@frappe.whitelist()
def readiness_detail(cohort_type, criterion, side=SIDE_MENTORS):
    """Who is missing the datum a rule needs.

    The readiness check counts; this names. Finding the same people by hand
    means filtering a list view on "is not set", which is neither obvious nor
    reachable from where the question was asked.

    It names people and never a coordinate (ADR 067 section 10): for the
    distance rule this answers "whose address did we fail to locate", which is
    a list of names, not a list of points.
    """
    settings = _planning_settings(cohort_type)
    require_planner(settings.mentor_unit)

    handler = rules.get(criterion)
    if not handler:
        frappe.throw(_("Unknown matching rule."))
    if side not in (SIDE_MENTORS, SIDE_STUDENTS):
        frappe.throw(_("Unknown group of people."))

    if side == SIDE_MENTORS:
        rows = mentor_pool(settings.mentor_unit)
        # The Person is where the datum lives; the Instructor is how a chair
        # knows them. Both, so the link goes where the fix is.
        role_of = {r["person"]: r["instructor"] for r in rows}
        role_doctype = "Instructor"
    else:
        rows = students_needing_placement(cohort_type)
        role_of = {r["person"]: r["student"] for r in rows}
        role_doctype = "Student"

    person_rows = _person_rows([r["person"] for r in rows])
    missing = [
        {
            "person": r["person"],
            "full_name": person_rows.get(r["person"], {}).get("full_name")
            or r["person"],
            "role": role_of.get(r["person"]),
            "role_doctype": role_doctype,
        }
        for r in rows
        if handler.missing(person_rows.get(r["person"], {}))
    ]
    missing.sort(key=lambda p: (p["full_name"] or "").lower())

    return {
        "criterion": criterion,
        "label": _(handler.label),
        "reads_label": _(handler.reads_label or handler.requires_field),
        "side": side,
        "total": len(missing),
        "people": missing[:READINESS_DETAIL_LIMIT],
        "truncated": len(missing) > READINESS_DETAIL_LIMIT,
        # A Program Chair can plan cohorts and cannot edit a Person, so the
        # dialog has to say who can rather than offering a link that 403s.
        "can_edit_person": bool(frappe.has_permission("Person", "write")),
    }
