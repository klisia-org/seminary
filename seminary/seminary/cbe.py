# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Competency-based education: resolution, aggregation and roll-up (ADR 065).

Every question the rest of the app asks about competency-based grading goes
through here — is this section competency-based, who may evaluate this student,
how do several ratings become one, and what is the student's standing on a
competency. Keeping them in one module is what lets the schools' disagreements
(average or sum, mentors only or mentors plus student, one grade per activity or
one per evaluator per dimension) stay configuration rather than branches spread
through the grading engine.

The verdict pipeline is deliberately ordered (ADR 065 section 6a):

    weighted average of the assessments  ->  editable override  ->  rounding

and each stage is stored, so a result can always be explained afterwards.
"""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, now_datetime, nowdate

CBE_SCALE_TYPE = "Competency-based education"

SECTION_SOURCE = "Course Schedule Instructors"
STUDENT_SOURCE = "Program Enrollment Mentor"


# ---------------------------------------------------------------- resolution


def _cache():
    if not hasattr(frappe.local, "cbe_cache"):
        frappe.local.cbe_cache = {}
    return frappe.local.cbe_cache


def is_cbe_scale(grading_scale):
    if not grading_scale:
        return False
    return (
        frappe.db.get_value("Grading Scale", grading_scale, "grscale_type")
        == CBE_SCALE_TYPE
    )


def framework_for(course_schedule):
    """The Competency Framework governing a section, or None.

    Resolution runs scale-first because that is the cheap test: a section whose
    grading scale is not competency-based can never be competency-based, and
    that is the overwhelming majority of sections. Only then do we look for the
    program that supplies the framework, matching on the same scale so a course
    shared between a competency-based and a conventional program resolves to the
    right one.
    """
    if not course_schedule:
        return None
    cache = _cache().setdefault("framework_for", {})
    if course_schedule in cache:
        return cache[course_schedule]

    cs = frappe.db.get_value(
        "Course Schedule", course_schedule, ["course", "gradesc_cs"], as_dict=True
    )
    framework = framework_for_course_and_scale(cs.course, cs.gradesc_cs) if cs else None

    cache[course_schedule] = framework
    return framework


def framework_for_course_and_scale(course, grading_scale):
    """The framework a section on this course and scale would resolve to.

    Split out of framework_for so a Course Schedule can ask the question about
    itself while still unsaved -- validation runs before the row exists, and
    reading it back from the database would always answer None.
    """
    if not is_cbe_scale(grading_scale):
        return None
    candidates = set()
    for row in frappe.get_all(
        "Program Course",
        filters={"course": course, "disabled": 0},
        fields=["parent"],
    ):
        fw = frappe.db.get_value("Program", row.parent, "competency_framework")
        if (
            fw
            and frappe.db.get_value("Competency Framework", fw, "grading_scale")
            == grading_scale
        ):
            candidates.add(fw)
    # Deterministic when a course is shared by two programs on the same
    # framework-compatible scale: they agree on the vocabulary, so either
    # answer is valid, but the same one has to come back every time.
    return sorted(candidates)[0] if candidates else None


def framework_doc(course_schedule):
    name = framework_for(course_schedule)
    return frappe.get_cached_doc("Competency Framework", name) if name else None


def evaluators_for(roster):
    """Who may evaluate this student in this section, and in what capacity.

    Two sources, per ADR 065 section 4. Section instructors evaluate everyone in
    the section. Program mentors are recorded once on the student's enrollment
    and resolved here through their Course Enrollment Individual, which is why
    the registrar never has to add a mentor to a section.

    Returns a list of dicts: instructor, instructor_category, assignment_source,
    grades_activities, gives_competency_verdict, required, weight.
    """
    roster_doc = (
        roster
        if isinstance(roster, frappe.model.document.Document)
        else frappe.get_doc("Scheduled Course Roster", roster)
    )
    framework = framework_doc(roster_doc.course_sc)
    if not framework:
        return []

    section_rows = [
        r for r in framework.evaluators if r.assignment_source == SECTION_SOURCE
    ]
    student_rows = [
        r for r in framework.evaluators if r.assignment_source == STUDENT_SOURCE
    ]

    resolved = []

    if section_rows:
        wanted = {r.instructor_category: r for r in section_rows}
        for si in frappe.get_all(
            "Course Schedule Instructors",
            filters={"parent": roster_doc.course_sc},
            fields=["instructor", "instructor_category"],
        ):
            rule = wanted.get(si.instructor_category)
            if rule:
                resolved.append(_evaluator(si.instructor, rule))

    if student_rows:
        wanted = {r.instructor_category: r for r in student_rows}
        for m in _program_mentors(roster_doc):
            rule = wanted.get(m.instructor_category)
            if rule:
                resolved.append(_evaluator(m.instructor, rule))

    return resolved


def _evaluator(instructor, rule):
    return {
        "instructor": instructor,
        "instructor_category": rule.instructor_category,
        "assignment_source": rule.assignment_source,
        "grades_activities": bool(rule.grades_activities),
        "gives_competency_verdict": bool(rule.gives_competency_verdict),
        "required": bool(rule.required),
        "weight": flt(rule.weight) or 1.0,
    }


def _program_mentors(roster_doc):
    """Active mentor rows on the student's enrollment for this section.

    The enrollment is reached through the student's Course Enrollment
    Individual, which is already the authoritative student-to-section link and
    is workflow-governed (ADR 016). Mentor rows are then filtered by date
    against the section's span so a mentor who has handed over does not keep
    appearing.
    """
    pe = frappe.db.get_value(
        "Course Enrollment Individual",
        {
            "coursesc_ce": roster_doc.course_sc,
            "student_ce": roster_doc.student,
            "docstatus": 1,
        },
        "program_ce",
    )
    if not pe:
        return []

    cs = (
        frappe.db.get_value(
            "Course Schedule",
            roster_doc.course_sc,
            ["c_datestart", "c_dateend"],
            as_dict=True,
        )
        or frappe._dict()
    )
    # getdate on every operand: these come back as date objects from some paths
    # and as strings from others (frappe.utils.today), and comparing the two
    # raises rather than returning a wrong answer.
    span_start = getdate(cs.get("c_datestart")) if cs.get("c_datestart") else None
    # An open-ended section has no end; "now" is the right upper bound for
    # deciding whether a mentor assignment is currently in force.
    span_end = getdate(cs.get("c_dateend")) if cs.get("c_dateend") else getdate()

    mentors = []
    for m in frappe.get_all(
        "Program Enrollment Mentor",
        filters={"parent": pe, "active": 1},
        fields=["instructor", "instructor_category", "from_date", "to_date"],
    ):
        if m.from_date and span_end and getdate(m.from_date) > span_end:
            continue
        if m.to_date and span_start and getdate(m.to_date) < span_start:
            continue
        mentors.append(m)
    return mentors


# ---------------------------------------------------------------- scale helpers


def scale_for(course_schedule):
    return frappe.db.get_value("Course Schedule", course_schedule, "gradesc_cs")


def levels_for(grading_scale):
    """The scale's levels as {grade_code: threshold}, ordered low to high."""
    cache = _cache().setdefault("levels_for", {})
    if grading_scale not in cache:
        cache[grading_scale] = frappe.get_all(
            "Grading Scale Interval",
            filters={"parent": grading_scale},
            fields=["grade_code", "threshold", "grade_pass"],
            order_by="threshold asc",
        )
    return cache[grading_scale]


def level_value(grading_scale, level_code):
    for row in levels_for(grading_scale):
        if row.grade_code == level_code:
            return flt(row.threshold)
    return None


def code_for_value(grading_scale, value):
    """The level a numeric value lands in — the highest whose threshold it meets."""
    from seminary.seminary.api import get_grade

    return get_grade(grading_scale, value)


def dimensions_of(course_competency):
    cache = _cache().setdefault("dimensions_of", {})
    if course_competency not in cache:
        cache[course_competency] = frappe.get_all(
            "Course Competency Dimension",
            filters={"parent": course_competency},
            fields=["dimension_code", "dimension", "weight"],
            order_by="idx asc",
        )
    return cache[course_competency]


# ---------------------------------------------------------------- aggregation


def aggregate(values, method, weights=None, rounding=None):
    """Combine several ratings into one.

    This is the single place the schools' disagreement about combining lives.
    `rounding` is optional and deliberately not applied by the callers that feed
    the verdict pipeline: rounding happens once, at the end, after any override
    (ADR 065 section 6a).
    """
    values = [flt(v) for v in values if v is not None]
    if not values:
        return None

    if method == "Sum":
        result = sum(values)
    elif method == "Highest":
        result = max(values)
    elif method == "Lowest":
        result = min(values)
    elif method == "Weighted average":
        ws = [flt(w) for w in (weights or [])] or [1.0] * len(values)
        ws = (ws + [1.0] * len(values))[: len(values)]
        total = sum(ws)
        result = sum(v * w for v, w in zip(values, ws)) / total if total else None
    else:
        # Average, and the fallback for "Instructor of record decides" once the
        # caller has already narrowed the values to that person's.
        result = sum(values) / len(values)

    return apply_rounding(result, rounding) if rounding else result


def apply_rounding(value, mode):
    import math

    if value is None:
        return None
    if mode == "Down":
        return float(math.floor(value))
    if mode == "Up":
        return float(math.ceil(value))
    if mode == "Nearest":
        return float(round(value))
    return flt(value)


# ---------------------------------------------------------------- weights


def dimension_weights_for(assess_criteria, course_competency=None):
    """An assessment's per-dimension weights, as {dimension_code: weight}.

    An assessment that declares none counts equally toward every dimension of
    its competency, so a school that does not care about this never configures
    it. A weight of zero means the assessment does not measure that dimension
    and is excluded from it rather than pulling it toward the mean.
    """
    rows = frappe.get_all(
        "Assessment Dimension Weight",
        filters={"assess_criteria": assess_criteria},
        fields=["dimension_code", "weight"],
    )
    weights = {r.dimension_code: flt(r.weight) for r in rows if flt(r.weight) > 0}
    if weights:
        return weights

    if not course_competency:
        course_competency = frappe.db.get_value(
            "Scheduled Course Assess Criteria", assess_criteria, "course_competency"
        )
    if not course_competency:
        return {}
    return {d.dimension_code: 1.0 for d in dimensions_of(course_competency)}


# ---------------------------------------------------------------- activity grades


PER_ACTIVITY_MODE = "One grade per activity"
PER_EVALUATOR_MODE = "One grade per evaluator"
PER_DIMENSION_MODE = "One grade per evaluator per dimension"


def grading_shape(assess_criteria, framework=None):
    """How many grades this assessment asks for: the shape before the cells."""
    override = frappe.db.get_value(
        "Scheduled Course Assess Criteria", assess_criteria, "grading_mode_override"
    )
    if override:
        return override
    if framework is None:
        parent = frappe.db.get_value(
            "Scheduled Course Assess Criteria", assess_criteria, "parent"
        )
        framework = framework_doc(parent)
    return framework.activity_grading_mode if framework else PER_ACTIVITY_MODE


def grading_matrix_for(assess_criteria):
    """Explicit cell choices for one assessment, as {(category, dim): graded}.

    Only what an instructor actually set. Absence is not "off": it means the
    shape stands, which is why this returns the overrides rather than a filled
    grid (ADR 065 section 11b).
    """
    cache = _cache().setdefault("grading_matrix_for", {})
    if assess_criteria not in cache:
        cache[assess_criteria] = {
            (r.instructor_category, r.dimension_code): bool(cint(r.graded))
            for r in frappe.get_all(
                "Assessment Grading Matrix",
                filters={"assess_criteria": assess_criteria},
                fields=["instructor_category", "dimension_code", "graded"],
            )
        }
    return cache[assess_criteria]


def is_cell_graded(assess_criteria, instructor_category, dimension_code, shape=None):
    """Does this kind of evaluator judge this dimension on this activity?

    An opted-out cell is *not applicable* -- not missing, not zero. Nothing may
    ask for it, wait for it, or average it in.
    """
    shape = shape or grading_shape(assess_criteria)
    # With one grade for the whole activity there are no axes to switch off.
    if shape == PER_ACTIVITY_MODE:
        return True
    matrix = grading_matrix_for(assess_criteria)
    if shape == PER_EVALUATOR_MODE:
        # No dimension axis: a category is on unless every one of its cells is
        # off, which is how "this mentor does not grade this activity" is said.
        cells = [v for (cat, _d), v in matrix.items() if cat == instructor_category]
        return any(cells) if cells else True
    explicit = matrix.get((instructor_category, dimension_code))
    return True if explicit is None else explicit


def graded_dimensions_for(assess_criteria, instructor_category, dimension_codes):
    """The dimensions this evaluator is asked to judge on this assessment."""
    shape = grading_shape(assess_criteria)
    if shape != PER_DIMENSION_MODE:
        return list(dimension_codes)
    return [
        d
        for d in dimension_codes
        if is_cell_graded(assess_criteria, instructor_category, d, shape)
    ]


def _any_evaluator_grades(roster_doc, assess_criteria, dimension_code):
    """Is anyone at all asked to judge this dimension on this assessment?

    A dimension every evaluator has opted out of does not participate in the
    competency's average; the other assessments carry it.
    """
    shape = grading_shape(assess_criteria)
    if shape != PER_DIMENSION_MODE:
        return True
    categories = {
        e["instructor_category"]
        for e in evaluators_for(roster_doc)
        if e["grades_activities"]
    }
    if not categories:
        return True
    return any(
        is_cell_graded(assess_criteria, cat, dimension_code, shape)
        for cat in categories
    )


def _grades_for(roster_name, assess_criteria, dimension_code=None):
    filters = {"roster": roster_name, "assess_criteria": assess_criteria}
    rows = frappe.get_all(
        "Activity Competency Grade",
        filters=filters,
        fields=["instructor", "instructor_category", "dimension_code", "level_value"],
    )
    if dimension_code is None:
        return rows
    specific = [r for r in rows if r.dimension_code == dimension_code]
    if specific:
        return specific
    # A whole-activity grade stands in for every dimension the assessment
    # weights, which is what the coarser grading modes produce.
    return [r for r in rows if not r.dimension_code]


def _evaluator_weights(roster_doc, rows):
    by_instructor = {e["instructor"]: e["weight"] for e in evaluators_for(roster_doc)}
    return [by_instructor.get(r.instructor, 1.0) for r in rows]


def level_for_assessment(roster_doc, assess_criteria, dimension_code, framework):
    """One level for one assessment and one dimension.

    Where more than one evaluator graded, their ratings are combined here by the
    framework's method, so the multi-evaluator rule is applied once and in one
    place (ADR 065 section 6a).
    """
    rows = _grades_for(roster_doc.name, assess_criteria, dimension_code)
    if not rows:
        return None

    if framework.aggregation_method == "Instructor of record decides":
        rows = _instructor_of_record_rows(rows) or rows

    return aggregate(
        [r.level_value for r in rows],
        framework.aggregation_method,
        _evaluator_weights(roster_doc, rows),
    )


def _instructor_of_record_rows(rows):
    keep = []
    for r in rows:
        if r.instructor_category and frappe.db.get_value(
            "Instructor Category", r.instructor_category, "is_instructor_of_record"
        ):
            keep.append(r)
    return keep


def weighted_dimension_value(roster, course_competency, dimension_code):
    """Step 1 of the verdict pipeline: the weighted average across assessments.

    Returned unrounded, so the override and rounding stages can act on it in
    order.
    """
    roster_doc = (
        roster
        if isinstance(roster, frappe.model.document.Document)
        else frappe.get_doc("Scheduled Course Roster", roster)
    )
    framework = framework_doc(roster_doc.course_sc)
    if not framework:
        return None

    criteria = frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={
            "parent": roster_doc.course_sc,
            "course_competency": course_competency,
        },
        fields=["name"],
    )

    numerator = 0.0
    denominator = 0.0
    for c in criteria:
        weight = dimension_weights_for(c.name, course_competency).get(dimension_code, 0)
        if weight <= 0:
            continue
        # Opted out is not zero: the assessment simply does not speak to this
        # dimension, so it leaves the average rather than dragging it down.
        if not _any_evaluator_grades(roster_doc, c.name, dimension_code):
            continue
        level = level_for_assessment(roster_doc, c.name, dimension_code, framework)
        if level is None:
            continue
        numerator += level * weight
        denominator += weight

    return (numerator / denominator) if denominator else None


# ---------------------------------------------------------------- assessments


def _final_assessment_values(roster_doc, course_competency, dimension_code, framework):
    """Levels from Submitted Final assessments, with their weights.

    Only evaluators the framework says give a verdict are counted, and the
    student's own rating only when the framework includes it.
    """
    assessments = frappe.get_all(
        "Competency Assessment",
        filters={
            "student": roster_doc.student,
            "course_schedule": roster_doc.course_sc,
            "course_competency": course_competency,
            "stage": "Final",
            "status": "Submitted",
        },
        fields=["name", "evaluator_kind", "instructor", "instructor_category"],
    )
    if not assessments:
        return [], []

    verdict_givers = {
        e["instructor"]: e["weight"]
        for e in evaluators_for(roster_doc)
        if e["gives_competency_verdict"]
    }

    values, weights = [], []
    for a in assessments:
        if a.evaluator_kind == "Self":
            if not framework.include_self_in_verdict:
                continue
            weight = flt(framework.self_eval_weight) or 1.0
        else:
            if a.instructor not in verdict_givers:
                continue
            weight = verdict_givers[a.instructor]

        rating = frappe.db.get_value(
            "Competency Assessment Rating",
            {"parent": a.name, "dimension_code": dimension_code},
            "level_value",
        )
        if rating is None:
            continue
        values.append(flt(rating))
        weights.append(weight)

    return values, weights


def baseline_value(roster_doc, course_competency, dimension_code):
    """The student's own starting level — the radar's first series."""
    assessment = frappe.db.get_value(
        "Competency Assessment",
        {
            "student": roster_doc.student,
            "course_schedule": roster_doc.course_sc,
            "course_competency": course_competency,
            "stage": "Baseline",
            "evaluator_kind": "Self",
            "status": "Submitted",
        },
        "name",
    )
    if not assessment:
        return None
    return frappe.db.get_value(
        "Competency Assessment Rating",
        {"parent": assessment, "dimension_code": dimension_code},
        "level_value",
    )


# ---------------------------------------------------------------- roll-ups


def rollup_activity_grades(roster, assess_criteria):
    """Write a competency activity's level into the existing gradebook cell.

    This is the convergence point of ADR 065: Gradebook, cs_lifecycle,
    attendance failure and send_grades keep working on Course Assess Results
    Detail without any competency awareness. The value written is a *level*, not
    a percentage, which is why every consumer that does arithmetic on it is
    gated on the scale type.
    """
    roster_doc = (
        roster
        if isinstance(roster, frappe.model.document.Document)
        else frappe.get_doc("Scheduled Course Roster", roster)
    )
    framework = framework_doc(roster_doc.course_sc)
    if not framework:
        return None

    competency = frappe.db.get_value(
        "Scheduled Course Assess Criteria", assess_criteria, "course_competency"
    )

    if competency:
        weights = dimension_weights_for(assess_criteria, competency)
        values, ws = [], []
        for dimension_code, weight in weights.items():
            level = level_for_assessment(
                roster_doc, assess_criteria, dimension_code, framework
            )
            if level is not None:
                values.append(level)
                ws.append(weight)
        value = aggregate(values, "Weighted average", ws) if values else None
    else:
        rows = _grades_for(roster_doc.name, assess_criteria)
        value = (
            aggregate(
                [r.level_value for r in rows],
                framework.aggregation_method,
                _evaluator_weights(roster_doc, rows),
            )
            if rows
            else None
        )

    card = frappe.db.get_value(
        "Course Assess Results Detail",
        {"parent": roster_doc.name, "assessment_criteria": assess_criteria},
        "name",
    )
    if not card:
        return value
    frappe.db.set_value(
        "Course Assess Results Detail",
        card,
        {"rawscore_card": value, "graded_card": 1 if value is not None else 0},
    )
    return value


def rollup_competency_result(roster, course_competency):
    """Run the section 6a pipeline and persist the result.

    Existing overrides are read back and preserved: recomputing must never
    silently discard a judgement someone recorded, which is the whole reason
    computed and overridden values are stored separately.
    """
    roster_doc = (
        roster
        if isinstance(roster, frappe.model.document.Document)
        else frappe.get_doc("Scheduled Course Roster", roster)
    )
    framework = framework_doc(roster_doc.course_sc)
    if not framework:
        return None

    pe = frappe.db.get_value(
        "Program Enrollment",
        {"student": roster_doc.student, "program": roster_doc.program_std_scr},
        "name",
    )

    existing = frappe.db.get_value(
        "Competency Result",
        {
            "student": roster_doc.student,
            "course_schedule": roster_doc.course_sc,
            "course_competency": course_competency,
        },
        "name",
    )
    doc = (
        frappe.get_doc("Competency Result", existing)
        if existing
        else frappe.new_doc("Competency Result")
    )
    prior = {d.dimension_code: d for d in (doc.get("dimensions") or [])}

    doc.student = roster_doc.student
    doc.program_enrollment = pe
    doc.course_schedule = roster_doc.course_sc
    doc.course_competency = course_competency

    rows = []
    for dim in dimensions_of(course_competency):
        kept = prior.get(dim.dimension_code)
        rows.append(
            {
                "dimension_code": dim.dimension_code,
                "dimension": dim.dimension,
                "baseline_value": baseline_value(
                    roster_doc, course_competency, dim.dimension_code
                ),
                "computed_value": _dimension_computed(
                    roster_doc, course_competency, dim.dimension_code, framework
                ),
                # An override is a judgement someone recorded; recomputing must
                # refresh what it sits on top of, never discard it.
                "override_value": kept.override_value if kept else None,
                "override_reason": kept.override_reason if kept else None,
                "overridden_by": kept.overridden_by if kept else None,
                "overridden_on": kept.overridden_on if kept else None,
            }
        )

    doc.set("dimensions", rows)
    # final_value / final_code / status are derived in validate via
    # recompute_finals, so hand entry and recomputation cannot disagree.
    doc.flags.ignore_permissions = True
    doc.save()
    return doc


def recompute_finals(doc):
    """Derive the reported values from computed and override, and round once.

    Split out from the roll-up so that editing an override in Desk produces the
    new result immediately: without this the stored override would sit next to a
    stale final value until something happened to recompute the whole thing.
    """
    framework = framework_doc(doc.course_schedule)
    if not framework:
        return
    scale = scale_for(doc.course_schedule)
    weights = {
        d.dimension_code: (flt(d.weight) or 1.0)
        for d in dimensions_of(doc.course_competency)
    }

    dim_values, dim_weights = [], []
    for row in doc.get("dimensions") or []:
        effective = (
            row.override_value
            if row.override_value not in (None, 0)
            else row.computed_value
        )
        row.final_value = apply_rounding(effective, framework.rounding)
        row.final_code = (
            code_for_value(scale, row.final_value)
            if row.final_value is not None
            else None
        )
        row.delta = (
            flt(row.final_value) - flt(row.baseline_value)
            if row.final_value is not None and row.baseline_value is not None
            else None
        )
        # Dimensions roll up on their pre-rounding values so rounding happens
        # once, at the end, rather than compounding at each level.
        if effective is not None:
            dim_values.append(effective)
            dim_weights.append(weights.get(row.dimension_code, 1.0))

    doc.computed_value = aggregate(
        dim_values, framework.aggregation_method, dim_weights
    )
    effective_overall = (
        doc.override_value
        if doc.override_value not in (None, 0)
        else doc.computed_value
    )
    doc.final_value = apply_rounding(effective_overall, framework.rounding)
    doc.final_code = (
        code_for_value(scale, doc.final_value) if doc.final_value is not None else None
    )
    doc.status = _result_status(scale, doc.final_code, doc.computed_value)


def _dimension_computed(roster_doc, course_competency, dimension_code, framework):
    """The dimension's value before any override, per the framework's sources."""
    values, weights = [], []

    if framework.verdict_source in ("Activity grades only", "Both"):
        activity = weighted_dimension_value(
            roster_doc, course_competency, dimension_code
        )
        if activity is not None:
            values.append(activity)
            weights.append(1.0)

    if framework.verdict_source in ("Final assessments only", "Both"):
        vals, ws = _final_assessment_values(
            roster_doc, course_competency, dimension_code, framework
        )
        values.extend(vals)
        weights.extend(ws)

    return aggregate(values, framework.aggregation_method, weights)


def _result_status(scale, final_code, computed):
    if computed is None and not final_code:
        return "Not Started"
    if not final_code:
        return "In Progress"
    for row in levels_for(scale):
        if row.grade_code == final_code:
            # "Pass" here is a Grading Scale Interval.grade_pass value
            # (Pass/Fail), not a credential — bandit's B105 reads any string
            # compared against a name containing "pass" as a hardcoded secret.
            passed = row.grade_pass == "Pass"  # nosec B105
            return "Competent" if passed else "Not Yet Competent"
    return "In Progress"


def rollup_all_for_roster(roster):
    """Refresh every competency result for a student in a section."""
    roster_doc = (
        roster
        if isinstance(roster, frappe.model.document.Document)
        else frappe.get_doc("Scheduled Course Roster", roster)
    )
    if not framework_for(roster_doc.course_sc):
        return []
    course = frappe.db.get_value("Course Schedule", roster_doc.course_sc, "course")
    results = []
    for c in frappe.get_all(
        "Course Competency", filters={"course": course, "is_active": 1}, fields=["name"]
    ):
        results.append(rollup_competency_result(roster_doc, c.name))
    return results


# ---------------------------------------------------------------- hooks


def on_activity_grade_update(doc, method=None):
    rollup_activity_grades(doc.roster, doc.assess_criteria)
    if doc.course_competency:
        rollup_competency_result(doc.roster, doc.course_competency)


def on_assessment_update(doc, method=None):
    if doc.status != "Submitted":
        return
    roster = frappe.db.get_value(
        "Scheduled Course Roster",
        {"course_sc": doc.course_schedule, "student": doc.student},
        "name",
    )
    if roster:
        rollup_competency_result(roster, doc.course_competency)


# ---------------------------------------------------------------- send_grades support


def missing_required_evaluators(roster):
    """Required evaluators who have not finished this student's activities.

    Returned as readable strings rather than a count: an instructor who is told
    "someone has not graded" has to go looking, which is exactly the delay the
    per-student mentor resolution was meant to remove.
    """
    roster_doc = (
        roster
        if isinstance(roster, frappe.model.document.Document)
        else frappe.get_doc("Scheduled Course Roster", roster)
    )
    framework = framework_doc(roster_doc.course_sc)
    if not framework or not framework.activity_evaluators_required:
        return []

    required = [
        e
        for e in evaluators_for(roster_doc)
        if e["required"] and e["grades_activities"]
    ]
    if not required:
        return []

    criteria = frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": roster_doc.course_sc, "course_competency": ("is", "set")},
        fields=["name", "title"],
    )
    if not criteria:
        return []

    graded = {
        (g.assess_criteria, g.instructor)
        for g in frappe.get_all(
            "Activity Competency Grade",
            filters={"roster": roster_doc.name},
            fields=["assess_criteria", "instructor"],
        )
    }

    dimension_codes = [
        d.dimension_code
        for d in frappe.get_all(
            "Grading Scale Dimensions",
            filters={"parent": scale_for(roster_doc.course_sc)},
            fields=["dimension_code"],
        )
    ]

    missing = []
    for c in criteria:
        for e in required:
            # Nothing is owed where every cell for this evaluator is switched
            # off: they were never asked to judge this activity.
            if not graded_dimensions_for(
                c.name, e["instructor_category"], dimension_codes
            ):
                continue
            if not is_cell_graded(c.name, e["instructor_category"], None):
                continue
            if (c.name, e["instructor"]) not in graded:
                missing.append(
                    _("{0} has not graded {1}").format(e["instructor"], c.title)
                )
    return missing


def stamp_override(doc, method=None):
    """Record who replaced a computed value, and refuse a silent replacement.

    An override without a reason is the failure mode this is guarding against:
    a number nobody can account for later is worse than no override at all.
    """
    for row in doc.get("dimensions") or []:
        if row.override_value in (None, 0):
            continue
        if not row.override_reason:
            frappe.throw(
                _(
                    "Dimension {0}: give a reason for replacing the computed value."
                ).format(row.dimension or row.dimension_code)
            )
        if not row.overridden_by:
            row.overridden_by = frappe.session.user
            row.overridden_on = now_datetime()

    if doc.override_value not in (None, 0):
        if not doc.override_reason:
            frappe.throw(
                _("Give a reason for replacing the computed value for this competency.")
            )
        if not doc.overridden_by:
            doc.overridden_by = frappe.session.user
            doc.overridden_on = now_datetime()


# ---------------------------------------------------------------- content release

PER_ACTIVITY = "Per activity (current rules)"
CHAPTER_GATED = "Chapter unlocks after previous competency self-assessed"
ACTIVITIES_GATED = (
    "Content open, activities locked until previous competency self-assessed"
)


def _mapped_chapters(course_schedule):
    """Chapters that deliver a competency, in outline order.

    Order comes from Course Schedule Chapter Reference rather than the chapter
    records themselves: the outline is what the student walks through, and it is
    reorderable independently of when chapters were created.
    """
    refs = frappe.get_all(
        "Course Schedule Chapter Reference",
        filters={"parent": course_schedule, "parenttype": "Course Schedule"},
        fields=["chapter", "idx"],
        order_by="idx asc",
    )
    out = []
    for ref in refs:
        row = frappe.db.get_value(
            "Course Schedule Chapter",
            ref.chapter,
            ["name", "chapter_title", "course_competency"],
            as_dict=True,
        )
        if row:
            row["idx"] = ref.idx
            out.append(row)
    return out


def _self_assessment_submitted(student, course_schedule, competency, stage="Final"):
    return bool(
        frappe.db.exists(
            "Competency Assessment",
            {
                "student": student,
                "course_schedule": course_schedule,
                "course_competency": competency,
                "evaluator_kind": "Self",
                "stage": stage,
                "status": "Submitted",
            },
        )
    )


def content_release_mode(course_schedule, framework=None):
    """The release mode actually in force for a section.

    A section may override the framework's mode only where the framework says
    so (`override_contentrelease`). Resolution honours the flag rather than
    trusting the stored value, because a school that turns the permission off
    means it from that moment on — leaving old overrides in force would make the
    flag a suggestion. The Course Schedule controller refuses new overrides in
    that state, so the two agree; this is the side that has to hold.
    """
    framework = framework or framework_doc(course_schedule)
    if not framework:
        return PER_ACTIVITY
    if not cint(framework.override_contentrelease):
        return framework.content_release_mode
    override = frappe.db.get_value(
        "Course Schedule", course_schedule, "content_release_override"
    )
    return override or framework.content_release_mode


def visible_outline(roster):
    """Which chapters and activities are open to this student, and why not.

    Gating is decided here rather than in the page: a locked activity has to
    refuse a submission too, and a rule enforced only in the Vue layer is not a
    rule. The reason travels with the lock because a lock the student cannot
    explain is worse than no lock at all.

    Falls back to no gating whenever the course has not mapped competencies onto
    chapters, since there would be nothing to gate on.
    """
    roster_doc = (
        roster
        if isinstance(roster, frappe.model.document.Document)
        else frappe.get_doc("Scheduled Course Roster", roster)
    )
    framework = framework_doc(roster_doc.course_sc)
    mode = content_release_mode(roster_doc.course_sc, framework)
    chapters = _mapped_chapters(roster_doc.course_sc)
    mapped = [c for c in chapters if c.course_competency]

    result = {"mode": mode, "gated": False, "chapters": {}}
    for c in chapters:
        result["chapters"][c.name] = {
            "chapter_title": c.chapter_title,
            "competency": c.course_competency,
            "locked": False,
            "activities_locked": False,
            "reason": None,
            "unlock_competency": None,
        }

    if mode == PER_ACTIVITY or not mapped:
        return result

    result["gated"] = True
    previous = None
    for c in mapped:
        # The first mapped chapter is always open: there is no prior competency
        # to have reflected on.
        if previous is not None and not _self_assessment_submitted(
            roster_doc.student, roster_doc.course_sc, previous.course_competency
        ):
            entry = result["chapters"][c.name]
            entry["unlock_competency"] = previous.course_competency
            entry["reason"] = _(
                "Opens once you have submitted your self-assessment for {0}."
            ).format(
                frappe.db.get_value(
                    "Course Competency", previous.course_competency, "competency_name"
                )
                or previous.chapter_title
            )
            if mode == CHAPTER_GATED:
                entry["locked"] = True
                entry["activities_locked"] = True
            else:
                entry["activities_locked"] = True
        previous = c
    return result


def _chapter_for_competency(course_schedule, competency):
    return frappe.db.get_value(
        "Course Schedule Chapter",
        {"coursesc": course_schedule, "course_competency": competency},
        "name",
    )


def assert_activity_unlocked(doc, method=None):
    """Refuse a submission for an activity the student has not unlocked.

    Hooked onto every submission doctype. Without it the gate would live only in
    the outline, and a direct call would walk straight past it.
    """
    course_schedule = getattr(doc, "coursesc", None) or getattr(doc, "course", None)
    criteria = getattr(doc, "course_assess", None)
    student = getattr(doc, "student", None)
    if not (course_schedule and criteria and student):
        return
    if not framework_for(course_schedule):
        return

    competency = frappe.db.get_value(
        "Scheduled Course Assess Criteria", criteria, "course_competency"
    )
    if not competency:
        return
    chapter = _chapter_for_competency(course_schedule, competency)
    if not chapter:
        return

    roster = frappe.db.get_value(
        "Scheduled Course Roster",
        {"course_sc": course_schedule, "student": student},
        "name",
    )
    if not roster:
        return

    state = visible_outline(roster)["chapters"].get(chapter) or {}
    if state.get("activities_locked"):
        frappe.throw(
            _("This activity is not open yet. {0}").format(state.get("reason") or ""),
            frappe.PermissionError,
        )


# ---------------------------------------------------------------- escalation


def _stall_clock_start(roster_doc, mapped, index):
    """When the clock started for the self-assessment at `index`.

    Measured from the previous competency's self-assessment, because that is
    the moment the student could first have written this one. For the first
    competency there is no such moment, so the section's start date stands in.
    """
    if index == 0:
        return frappe.db.get_value(
            "Course Schedule", roster_doc.course_sc, "c_datestart"
        )
    previous = mapped[index - 1].course_competency
    return frappe.db.get_value(
        "Competency Assessment",
        {
            "student": roster_doc.student,
            "course_schedule": roster_doc.course_sc,
            "course_competency": previous,
            "evaluator_kind": "Self",
            "stage": "Final",
            "status": "Submitted",
        },
        "submitted_on",
    )


def stalled_self_assessments(course_schedule=None):
    """Students sitting on an unsubmitted self-assessment past the framework's
    patience. Returns the findings without sending anything, so the same
    calculation backs both the job and any report of it."""
    filters = {"active": 1, "audit_bool": 0}
    if course_schedule:
        filters["course_sc"] = course_schedule

    findings = []
    for r in frappe.get_all(
        "Scheduled Course Roster",
        filters=filters,
        fields=["name", "student", "stuname_roster", "course_sc"],
        limit=5000,
    ):
        framework = framework_doc(r.course_sc)
        if not framework or not cint(framework.stall_escalation_days):
            continue
        if frappe.db.get_value("Course Schedule", r.course_sc, "workflow_state") in (
            "Closed",
            "Cancelled",
            "Draft",
        ):
            continue

        mapped = [c for c in _mapped_chapters(r.course_sc) if c.course_competency]
        if not mapped:
            continue

        roster_doc = frappe.get_doc("Scheduled Course Roster", r.name)
        for index, chapter in enumerate(mapped):
            if _self_assessment_submitted(
                r.student, r.course_sc, chapter.course_competency
            ):
                continue
            started = _stall_clock_start(roster_doc, mapped, index)
            if not started:
                break  # the student has not reached this competency yet
            overdue = date_diff(nowdate(), getdate(started))
            if overdue > cint(framework.stall_escalation_days):
                findings.append(
                    {
                        "roster": r.name,
                        "student": r.student,
                        "student_name": r.stuname_roster,
                        "course_schedule": r.course_sc,
                        "competency": chapter.course_competency,
                        "chapter": chapter.name,
                        "days_overdue": overdue,
                    }
                )
            # Only the first outstanding competency matters: everything after it
            # is blocked behind this one, and naming them all would bury it.
            break
    return findings


def notify_stalled_self_assessments():
    """Daily job: tell mentors when a student has stopped reflecting.

    Content gating means a student who stops submitting self-assessments locks
    themselves out of the course, and nothing else would surface that. Messages
    are deduplicated per student, competency and day so a long stall produces
    one note a day rather than a growing pile.
    """
    from seminary.seminary import comms

    for item in stalled_self_assessments():
        competency_name = (
            frappe.db.get_value(
                "Course Competency", item["competency"], "competency_name"
            )
            or item["competency"]
        )
        subject = _("{0} has not submitted a self-assessment").format(
            item["student_name"]
        )
        message = _(
            "{0} has not submitted their self-assessment for {1} in {2}. It has "
            "been {3} days. Until they do, the rest of the course stays closed to "
            "them."
        ).format(
            item["student_name"],
            competency_name,
            item["course_schedule"],
            item["days_overdue"],
        )
        for evaluator in evaluators_for(item["roster"]):
            person = frappe.db.get_value(
                "Instructor", evaluator["instructor"], "person"
            )
            if not person:
                continue
            try:
                comms.send_message(
                    channel="In-App",
                    subject=subject,
                    message=message,
                    person=person,
                    category="Academic",
                    reference_doctype="Scheduled Course Roster",
                    reference_name=item["roster"],
                    dedupe_key=(
                        f"cbe-stall-{item['roster']}-{item['competency']}-{nowdate()}"
                    ),
                )
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(), "CBE stall notification failed"
                )


# ---------------------------------------------------------------- mentor scope


def mentors_of_student(student):
    """Every instructor who is currently a mentor to this student.

    The same two sources as `evaluators_for`, composed at student scope instead
    of section scope, because a development note need not belong to any course
    (ADR 065 section 8a). Resolved live rather than stored: a mentor's access
    ends when their row closes, and a stored grant would outlive the
    relationship it was standing in for.
    """
    if not student:
        return set()

    today = getdate()
    out = set()

    enrollments = frappe.get_all(
        "Program Enrollment",
        filters={"student": student, "docstatus": 1},
        fields=["name", "program"],
    )
    for pe in enrollments:
        if not frappe.db.get_value("Program", pe.program, "competency_framework"):
            continue
        for m in frappe.get_all(
            "Program Enrollment Mentor",
            filters={"parent": pe.name, "active": 1},
            fields=["instructor", "from_date", "to_date"],
        ):
            if m.from_date and getdate(m.from_date) > today:
                continue
            if m.to_date and getdate(m.to_date) < today:
                continue
            out.add(m.instructor)

    # Section instructors count only while the student is still active in the
    # section: a professor who taught them two years ago is not a mentor now.
    for r in frappe.get_all(
        "Scheduled Course Roster",
        filters={"student": student, "active": 1, "audit_bool": 0},
        fields=["name", "course_sc"],
    ):
        if not framework_for(r.course_sc):
            continue
        for e in evaluators_for(r.name):
            out.add(e["instructor"])

    out.discard(None)
    return out


def is_mentor_of(instructor, student):
    if not instructor or not student:
        return False
    return instructor in mentors_of_student(student)


def mentees_of(instructor):
    """The students an instructor currently mentors.

    The inversion of `mentors_of_student`, and the same resolution behind the
    competency worklist: a mentor is never added to a section, so this is the
    only thing that can tell them whose formation they are following.
    """
    if not instructor:
        return []

    students = set()
    for m in frappe.get_all(
        "Program Enrollment Mentor",
        filters={"instructor": instructor, "active": 1},
        fields=["parent", "from_date", "to_date"],
    ):
        today = getdate()
        if m.from_date and getdate(m.from_date) > today:
            continue
        if m.to_date and getdate(m.to_date) < today:
            continue
        pe = frappe.db.get_value(
            "Program Enrollment",
            m.parent,
            ["student", "program", "docstatus"],
            as_dict=True,
        )
        if not pe or pe.docstatus != 1:
            continue
        if not frappe.db.get_value("Program", pe.program, "competency_framework"):
            continue
        students.add(pe.student)

    sections = frappe.get_all(
        "Course Schedule Instructors",
        filters={"instructor": instructor},
        pluck="parent",
    )
    for cs in set(sections):
        if not framework_for(cs):
            continue
        for r in frappe.get_all(
            "Scheduled Course Roster",
            filters={"course_sc": cs, "active": 1, "audit_bool": 0},
            fields=["name", "student"],
        ):
            if any(e["instructor"] == instructor for e in evaluators_for(r.name)):
                students.add(r.student)

    return sorted(students)


# ---------------------------------------------------------------- prompt timing


START_OF_COURSE = "Start of course"
END_OF_COURSE = "End of course"
END_OF_EACH_COMPETENCY = "End of each competency"


def self_assessment_prompts(roster):
    """When to actually ask this student to assess themselves.

    `course_self_eval_points` has always distinguished start of course, end of
    course and end of each competency, but the outline offered the prompt on
    every mapped chapter regardless -- so a school set to "start of course and
    end of each competency" was greeted at the *beginning* of each competency
    and never at the start (ADR 065 section 11e).

    Returns {"baseline": bool, "chapters": {chapter: competency}, "final_all":
    bool}: whether the opening baseline is due, which chapters have finished and
    so are ready for their competency's final self-assessment, and whether the
    end-of-course prompt is due.
    """
    roster_doc = (
        roster
        if isinstance(roster, frappe.model.document.Document)
        else frappe.get_doc("Scheduled Course Roster", roster)
    )
    framework = framework_doc(roster_doc.course_sc)
    empty = {"baseline": False, "chapters": {}, "final_all": False, "points": None}
    if not framework or not cint(framework.course_self_eval):
        return empty

    when = framework.course_self_eval_points or ""
    out = dict(empty, points=when)
    # Matched case-insensitively on purpose: the Select reads "Start of course
    # and end of each competency", so a capitalised constant matches the option
    # that starts with it and silently misses the one that does not.
    phrase = when.lower()

    mapped = [c for c in _mapped_chapters(roster_doc.course_sc) if c.course_competency]

    if "start" in phrase:
        # Due until it is done: the baseline is the first thing asked and the
        # last thing a student thinks to go back for.
        out["baseline"] = any(
            not _self_assessment_submitted(
                roster_doc.student,
                roster_doc.course_sc,
                c.course_competency,
                "Baseline",
            )
            for c in mapped
        )

    complete = _completed_chapters(roster_doc)

    if END_OF_EACH_COMPETENCY.lower() in phrase:
        for c in mapped:
            if c.name in complete and not _self_assessment_submitted(
                roster_doc.student, roster_doc.course_sc, c.course_competency, "Final"
            ):
                out["chapters"][c.name] = c.course_competency

    if END_OF_COURSE.lower() in phrase and END_OF_EACH_COMPETENCY.lower() not in phrase:
        # The whole outline, not just the mapped part: an intro chapter is still
        # work the student has to finish before the course is over.
        chapters = _mapped_chapters(roster_doc.course_sc)
        out["final_all"] = bool(chapters) and all(c.name in complete for c in chapters)

    return out


def _completed_chapters(roster_doc):
    """Chapters whose lessons this student has all finished.

    Read from the same Course Schedule Progress rows the outline already uses,
    so "end of a competency" needs no new state to mean something.
    """
    chapters = [c.name for c in _mapped_chapters(roster_doc.course_sc)]
    if not chapters:
        return set()

    lessons_by_chapter = {}
    for ref in frappe.get_all(
        "Course Schedule Lesson Reference",
        filters={"parenttype": "Course Schedule Chapter", "parent": ("in", chapters)},
        fields=["parent", "lesson"],
    ):
        lessons_by_chapter.setdefault(ref.parent, []).append(ref.lesson)

    done = {
        p.lesson
        for p in frappe.get_all(
            "Course Schedule Progress",
            filters={
                "course": roster_doc.course_sc,
                "member": frappe.db.get_value("Student", roster_doc.student, "user"),
                "status": "Complete",
            },
            fields=["lesson"],
        )
    }

    complete = set()
    for chapter, lessons in lessons_by_chapter.items():
        # A chapter with no lessons is not "finished" -- there was nothing to do,
        # so there is nothing to reflect on either.
        if lessons and all(lesson in done for lesson in lessons):
            complete.add(chapter)
    return complete
