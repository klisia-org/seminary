# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Portal endpoints for competency-based education (ADR 065).

Every endpoint here answers to the portal, so each one re-derives who is asking
rather than trusting what it was handed. The competency model deliberately puts
a student's own account of their formation next to a mentor's judgement of it,
and those two audiences must never see each other's view by accident.

The read shape is split deliberately: a light roster for the left pane and a
full detail for the selected student, because a section's worth of competencies
x dimensions x evaluators is far too much to send for every student at once.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from seminary.seminary import cbe

STAFF_ROLES = {
    "Instructor",
    "Program Chair",
    "Seminary Manager",
    "Registrar",
    "System Manager",
}


# ---------------------------------------------------------------- identity


def _is_staff(user=None):
    return bool(STAFF_ROLES & set(frappe.get_roles(user or frappe.session.user)))


def _current_instructor():
    return frappe.db.get_value("Instructor", {"user": frappe.session.user}, "name")


def _current_student():
    return frappe.db.get_value("Student", {"user": frappe.session.user}, "name")


def _assert_staff():
    if not _is_staff():
        frappe.throw(_("This view is for teaching staff."), frappe.PermissionError)


def _roster_for(course_schedule, student):
    return frappe.db.get_value(
        "Scheduled Course Roster",
        {"course_sc": course_schedule, "student": student},
        "name",
    )


def _assert_own_roster(roster):
    """A student may only ever act on their own roster row."""
    student = frappe.db.get_value("Scheduled Course Roster", roster, "student")
    if _is_staff():
        return student
    mine = _current_student()
    if not mine or mine != student:
        frappe.throw(_("Not permitted."), frappe.PermissionError)
    return student


def _select_options(doctype, fieldname):
    """A Select field's choices, read off the doctype.

    Sent to the portal rather than typed into the page so the two can never
    disagree about what the modes are.
    """
    options = frappe.get_meta(doctype).get_field(fieldname).options or ""
    return [o for o in options.split("\n") if o]


# ---------------------------------------------------------------- context


@frappe.whitelist()
def get_competency_context(course_schedule):
    """Everything a competency screen needs to render before it has any data.

    Returns is_cbe False for an ordinary section so callers can mount the
    competency surfaces optimistically and fall back without a second request.
    """
    framework = cbe.framework_doc(course_schedule)
    if not framework:
        return {"is_cbe": False}

    cs = frappe.db.get_value(
        "Course Schedule",
        course_schedule,
        [
            "course",
            "gradesc_cs",
            "workflow_state",
            "open_ended",
            "c_dateend",
            "content_release_override",
        ],
        as_dict=True,
    )
    scale = cs.gradesc_cs

    dimensions = frappe.get_all(
        "Grading Scale Dimensions",
        filters={"parent": scale},
        fields=["dimension_code", "dimension", "description", "dimension_icon"],
        order_by="sequence asc, idx asc",
    )

    chapter_by_competency = {
        c.course_competency: c.name
        for c in frappe.get_all(
            "Course Schedule Chapter",
            filters={"coursesc": course_schedule, "course_competency": ("is", "set")},
            fields=["name", "course_competency"],
        )
    }

    competencies = []
    for c in frappe.get_all(
        "Course Competency",
        filters={"course": cs.course, "is_active": 1},
        fields=["name", "competency_code", "competency_name", "sequence", "statement"],
        order_by="sequence asc, competency_name asc",
    ):
        c["dimensions"] = frappe.get_all(
            "Course Competency Dimension",
            filters={"parent": c.name},
            fields=["dimension_code", "dimension", "demonstrated_by", "weight"],
            order_by="idx asc",
        )
        c["chapter"] = chapter_by_competency.get(c.name)
        competencies.append(c)

    # The competency a chapter forces on its assessments, resolved through the
    # same lesson index the Course Schedule controller validates against, so the
    # picker greys out exactly what the server would refuse (ADR 065 11b).
    from seminary.seminary.utils import (
        _build_lesson_index_for_course,
        _scac_activity_key,
    )

    lesson_index = _build_lesson_index_for_course(course_schedule)

    def _chapter_competency(row):
        lesson = lesson_index.get(_scac_activity_key(row))
        if not lesson:
            return None
        chapter = frappe.db.get_value("Course Lesson", lesson, "chapter")
        if not chapter:
            return None
        return frappe.db.get_value(
            "Course Schedule Chapter", chapter, "course_competency"
        )

    assessments = []
    for a in frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": course_schedule},
        fields=[
            "name",
            "title",
            "course_competency",
            "grading_mode_override",
            "due_date",
            "type",
            "quiz",
            "assignment",
            "exam",
            "discussion",
        ],
        order_by="idx asc",
    ):
        a["chapter_competency"] = _chapter_competency(a)
        a["weights"] = cbe.dimension_weights_for(a.name, a.course_competency)
        a["grading_mode"] = cbe.grading_shape(a.name, framework)
        # The instructor's explicit cell choices, as a flat list the grid can
        # render; absence still means "follow the shape" (ADR 065 section 11b).
        a["matrix"] = [
            {
                "instructor_category": cat,
                "dimension_code": dim,
                "graded": graded,
            }
            for (cat, dim), graded in cbe.grading_matrix_for(a.name).items()
        ]
        assessments.append(a)

    return {
        "is_cbe": True,
        "course_schedule": course_schedule,
        "workflow_state": cs.workflow_state,
        "open_ended": bool(cs.open_ended),
        "grading_scale": scale,
        "content_release_override": cs.content_release_override,
        "effective_content_release": cbe.content_release_mode(
            course_schedule, framework
        ),
        "levels": cbe.levels_for(scale),
        "dimensions": dimensions,
        "competencies": competencies,
        "assessments": assessments,
        "grading_categories": [
            {
                "instructor_category": e.instructor_category,
                "assignment_source": e.assignment_source,
                "required": cint(e.required),
            }
            for e in framework.evaluators
            if cint(e.grades_activities)
        ],
        "verdict_categories": [
            e.instructor_category
            for e in framework.evaluators
            if cint(e.gives_competency_verdict)
        ],
        "framework": {
            "name": framework.name,
            "activity_grading_mode": framework.activity_grading_mode,
            "verdict_source": framework.verdict_source,
            "aggregation_method": framework.aggregation_method,
            "rounding": framework.rounding,
            "report_basis": framework.report_basis,
            "report_max": framework.report_max,
            "course_self_eval": cint(framework.course_self_eval),
            "course_self_eval_points": framework.course_self_eval_points,
            "mentor_sees_self_eval": framework.mentor_sees_self_eval,
            # The framework's own setting, whether sections may depart from it,
            # and what is actually in force here. The dialog that explains the
            # mapping reads the effective mode; the form that offers the choice
            # reads the flag.
            "content_release_mode": framework.content_release_mode,
            "override_contentrelease": cint(framework.override_contentrelease),
            "content_release_options": _select_options(
                "Competency Framework", "content_release_mode"
            ),
            "require_pdp": cint(framework.require_pdp),
        },
        "viewer": {
            "is_staff": _is_staff(),
            "instructor": _current_instructor(),
            "student": _current_student(),
        },
    }


# ---------------------------------------------------------------- staff reads


@frappe.whitelist()
def get_competency_roster(course_schedule):
    """The left pane: one row per student with enough to show progress.

    Deliberately light — the per-student competency detail is a separate call,
    because a section's competencies times dimensions times evaluators is far
    more than a roster list needs.
    """
    _assert_staff()
    if not cbe.framework_for(course_schedule):
        return []

    rows = frappe.get_all(
        "Scheduled Course Roster",
        filters={"course_sc": course_schedule},
        fields=[
            "name",
            "student",
            "stuname_roster",
            "stuimage",
            "active",
            "audit_bool",
            "fgrade",
            "fscore",
        ],
        order_by="stuname_roster asc",
    )

    competencies = frappe.get_all(
        "Course Competency",
        filters={
            "course": frappe.db.get_value("Course Schedule", course_schedule, "course"),
            "is_active": 1,
        },
        pluck="name",
    )
    total = len(competencies) or 1

    for r in rows:
        results = frappe.get_all(
            "Competency Result",
            filters={"student": r.student, "course_schedule": course_schedule},
            fields=["course_competency", "status", "final_code", "final_value"],
        )
        decided = [x for x in results if x.status in ("Competent", "Not Yet Competent")]
        r["results"] = results
        r["progress"] = round(100.0 * len(decided) / total)
        # `active` doubles as "not yet finalized" once grades have been sent for
        # this student, which is the only record of a partial send (ADR 065 7a).
        r["finalized"] = not r.active and not r.audit_bool
    return rows


@frappe.whitelist()
def get_student_competency_detail(roster):
    """The right pane: one student's competencies, dimensions and evaluators."""
    _assert_staff()
    roster_doc = frappe.get_doc("Scheduled Course Roster", roster)
    framework = cbe.framework_doc(roster_doc.course_sc)
    if not framework:
        return {}

    evaluators = cbe.evaluators_for(roster_doc)
    course = frappe.db.get_value("Course Schedule", roster_doc.course_sc, "course")

    grades = frappe.get_all(
        "Activity Competency Grade",
        filters={"roster": roster},
        fields=[
            "name",
            "assess_criteria",
            "instructor",
            "dimension_code",
            "level_code",
            "level_value",
            "narrative",
        ],
    )
    grade_index = {}
    for g in grades:
        grade_index.setdefault(g.assess_criteria, {}).setdefault(g.instructor, {})[
            g.dimension_code or ""
        ] = g

    show_self = framework.mentor_sees_self_eval
    competencies = []
    for c in frappe.get_all(
        "Course Competency",
        filters={"course": course, "is_active": 1},
        fields=["name", "competency_name", "sequence", "statement"],
        order_by="sequence asc",
    ):
        result = frappe.db.get_value(
            "Competency Result",
            {
                "student": roster_doc.student,
                "course_schedule": roster_doc.course_sc,
                "course_competency": c.name,
            },
            [
                "name",
                "status",
                "computed_value",
                "override_value",
                "final_value",
                "final_code",
            ],
            as_dict=True,
        )
        c["result"] = result
        c["dimensions"] = frappe.get_all(
            "Course Competency Dimension",
            filters={"parent": c.name},
            fields=["dimension_code", "dimension", "demonstrated_by"],
            order_by="idx asc",
        )
        if result:
            c["result_dimensions"] = frappe.get_all(
                "Competency Result Dimension",
                filters={"parent": result.name},
                fields=[
                    "dimension_code",
                    "baseline_value",
                    "computed_value",
                    "override_value",
                    "override_reason",
                    "final_value",
                    "final_code",
                ],
            )
        c["assessments"] = frappe.get_all(
            "Scheduled Course Assess Criteria",
            filters={"parent": roster_doc.course_sc, "course_competency": c.name},
            fields=["name", "title", "grading_mode_override", "due_date"],
            order_by="idx asc",
        )
        dimension_codes = [d.dimension_code for d in c["dimensions"]]
        for a in c["assessments"]:
            a["grades"] = grade_index.get(a.name, {})
            a["weights"] = cbe.dimension_weights_for(a.name, c.name)
            a["grading_mode"] = cbe.grading_shape(a.name, framework)
            # Which (evaluator, dimension) cells this assessment actually asks
            # for. An opted-out cell must not render a picker: it is not
            # applicable, not merely unfilled (ADR 065 section 11b).
            a["graded_cells"] = _graded_cells(a, evaluators, dimension_codes)
        c["assessments_by_mentor"] = _mentor_assessments(roster_doc, c.name, show_self)
        competencies.append(c)

    return {
        "roster": roster,
        "student": roster_doc.student,
        "student_name": roster_doc.stuname_roster,
        "active": roster_doc.active,
        "finalized": not roster_doc.active and not roster_doc.audit_bool,
        "evaluators": evaluators,
        "competencies": competencies,
        "missing_evaluators": cbe.missing_required_evaluators(roster_doc),
    }


def _graded_cells(assessment, evaluators, dimension_codes):
    """{"<category>|<dimension_code>": True} for the cells that are asked for."""
    shape = assessment["grading_mode"]
    cells = {}
    for e in evaluators:
        if not e["grades_activities"]:
            continue
        category = e["instructor_category"]
        if not cbe.is_cell_graded(assessment["name"], category, None, shape):
            continue
        if shape == cbe.PER_DIMENSION_MODE:
            for code in cbe.graded_dimensions_for(
                assessment["name"], category, dimension_codes
            ):
                cells["{0}|{1}".format(category, code)] = True
        else:
            for code in dimension_codes:
                cells["{0}|{1}".format(category, code)] = True
    return cells


def _mentor_assessments(roster_doc, competency, show_self):
    """Final assessments on a competency, with the self-assessment gated.

    `mentor_sees_self_eval` exists so a school can stop a mentor anchoring on
    what the student said before forming their own view; honouring it has to
    happen here rather than in the page, or the answer is still in the payload.
    """
    rows = frappe.get_all(
        "Competency Assessment",
        filters={
            "student": roster_doc.student,
            "course_schedule": roster_doc.course_sc,
            "course_competency": competency,
        },
        fields=[
            "name",
            "stage",
            "evaluator_kind",
            "instructor",
            "status",
            "narrative",
            "submitted_on",
        ],
    )
    viewer_instructor = _current_instructor()
    out = []
    for r in rows:
        if r.evaluator_kind == "Self":
            if show_self == "Never":
                continue
            if show_self == "After mentor submits":
                submitted = frappe.db.exists(
                    "Competency Assessment",
                    {
                        "student": roster_doc.student,
                        "course_schedule": roster_doc.course_sc,
                        "course_competency": competency,
                        "evaluator_kind": "Mentor",
                        "instructor": viewer_instructor,
                        "status": "Submitted",
                    },
                )
                if not submitted:
                    r["withheld"] = True
                    r["narrative"] = None
                    out.append(r)
                    continue
        r["ratings"] = frappe.get_all(
            "Competency Assessment Rating",
            filters={"parent": r.name},
            fields=["dimension_code", "level_code", "level_value", "narrative"],
        )
        out.append(r)
    return out


# ------------------------------------------------- the submission surfaces (11c)

# Every submission doctype names the criteria row it was graded under and the
# student who sat it, so one panel serves all four surfaces rather than four
# near-copies drifting apart. The value is the field naming the Course Schedule,
# which is the only thing they spell differently.
SUBMISSION_DOCTYPES = {
    "Quiz Submission": "course",
    "Exam Submission": "course",
    "Assignment Submission": "course",
    "Discussion Submission": "coursesc",
}


@frappe.whitelist()
def get_activity_grading_panel(submission_doctype, submission):
    """The level pickers one activity offers for one student (ADR 065 11c).

    A competency section grades an activity in levels per dimension, not in
    points, so the four submission pages ask here what to render instead of
    each deciding for itself. `is_cbe` False means "keep your numeric box".
    """
    _assert_staff()
    schedule_field = SUBMISSION_DOCTYPES.get(submission_doctype)
    if not schedule_field:
        frappe.throw(_("{0} is not a graded submission.").format(submission_doctype))

    sub = frappe.db.get_value(
        submission_doctype,
        submission,
        [schedule_field, "student", "course_assess"],
        as_dict=True,
    )
    if not sub:
        frappe.throw(_("That submission no longer exists."))
    course_schedule = sub.get(schedule_field)

    framework = cbe.framework_doc(course_schedule)
    if not framework:
        return {"is_cbe": False}
    if not sub.course_assess:
        # A competency section grades through its criteria row; a submission
        # that is not tied to one has nothing to record a level against.
        return {
            "is_cbe": True,
            "unmapped": True,
            "course_schedule": course_schedule,
        }

    roster = _roster_for(course_schedule, sub.student)
    if not roster:
        return {
            "is_cbe": True,
            "unmapped": True,
            "course_schedule": course_schedule,
        }
    return _grading_panel(roster, sub.course_assess, framework)


def _grading_panel(roster, assess_criteria, framework):
    """What one evaluator may record on one activity for one student."""
    roster_doc = frappe.get_doc("Scheduled Course Roster", roster)
    course_schedule = roster_doc.course_sc
    criteria = frappe.db.get_value(
        "Scheduled Course Assess Criteria",
        assess_criteria,
        ["name", "title", "course_competency"],
        as_dict=True,
    )
    competency = criteria.course_competency
    if not competency:
        return {
            "is_cbe": True,
            "unmapped": True,
            "course_schedule": course_schedule,
            "assessment_title": criteria.title,
        }

    comp = frappe.db.get_value(
        "Course Competency", competency, ["competency_name", "statement"], as_dict=True
    )
    dimensions = frappe.get_all(
        "Course Competency Dimension",
        filters={"parent": competency},
        fields=["dimension_code", "dimension", "demonstrated_by"],
        order_by="idx asc",
    )
    # A dimension this assessment does not measure is not graded here; that is
    # the same "Not measured here" the per-student panel already shows.
    weights = cbe.dimension_weights_for(assess_criteria, competency)
    dimensions = [d for d in dimensions if flt(weights.get(d.dimension_code)) > 0]

    shape = cbe.grading_shape(assess_criteria, framework)
    grades = {}
    for g in frappe.get_all(
        "Activity Competency Grade",
        filters={"roster": roster, "assess_criteria": assess_criteria},
        fields=[
            "instructor",
            "dimension_code",
            "level_code",
            "level_value",
            "narrative",
        ],
    ):
        grades[(g.instructor, g.dimension_code or "")] = g

    me = _current_instructor()
    is_manager = bool(
        {"Seminary Manager", "System Manager", "Program Chair"}
        & set(frappe.get_roles())
    )
    evaluators = [e for e in cbe.evaluators_for(roster_doc) if e["grades_activities"]]
    names = _instructor_names({e["instructor"] for e in evaluators})

    rows = []
    for e in evaluators:
        # With one grade for the whole activity there is no evaluator axis, so
        # only the person grading it is offered a picker.
        if shape == cbe.PER_ACTIVITY_MODE and e["instructor"] != me and not is_manager:
            continue
        if not cbe.is_cell_graded(
            assess_criteria, e["instructor_category"], None, shape
        ):
            continue
        if shape == cbe.PER_DIMENSION_MODE:
            codes = cbe.graded_dimensions_for(
                assess_criteria,
                e["instructor_category"],
                [d.dimension_code for d in dimensions],
            )
            cells = [
                {
                    "dimension_code": d.dimension_code,
                    "dimension": d.dimension,
                    "demonstrated_by": d.demonstrated_by,
                    "grade": grades.get((e["instructor"], d.dimension_code)),
                }
                for d in dimensions
                if d.dimension_code in codes
            ]
        else:
            cells = [
                {
                    "dimension_code": None,
                    "dimension": _("Overall"),
                    "demonstrated_by": None,
                    "grade": grades.get((e["instructor"], "")),
                }
            ]
        if not cells:
            continue
        rows.append(
            {
                "instructor": e["instructor"],
                "instructor_name": names.get(e["instructor"], e["instructor"]),
                "instructor_category": e["instructor_category"],
                "can_grade": is_manager or e["instructor"] == me,
                "cells": cells,
            }
        )

    workflow_state = frappe.db.get_value(
        "Course Schedule", course_schedule, "workflow_state"
    )
    return {
        "is_cbe": True,
        "course_schedule": course_schedule,
        "roster": roster,
        "student": roster_doc.student,
        "student_name": roster_doc.stuname_roster,
        "assess_criteria": assess_criteria,
        "assessment_title": criteria.title,
        "course_competency": competency,
        "competency_name": comp.competency_name if comp else competency,
        "statement": comp.statement if comp else None,
        "grading_mode": shape,
        "levels": cbe.levels_for(cbe.scale_for(course_schedule)),
        "read_only": workflow_state in ("Closed", "Cancelled")
        or bool(not roster_doc.active and not roster_doc.audit_bool),
        "rows": rows,
    }


# ------------------------------------------------- the bird's-eye gradebook (11d)


@frappe.whitelist()
def get_cbe_gradebook(course_schedule):
    """Students x competency x assessment x evaluator x dimension (ADR 065 11d).

    The whole-course view. Levels, not scores: a competency section has no
    weighted total to put in a numeric grid, and the grid it currently gets is
    meaningless. Read-only by design -- grading happens on the activity or in
    the per-student panel, where the evaluator can see what they are judging.
    """
    _assert_staff()
    framework = cbe.framework_doc(course_schedule)
    if not framework:
        return {"is_cbe": False}

    course = frappe.db.get_value("Course Schedule", course_schedule, "course")
    grading_categories = [
        e.instructor_category for e in framework.evaluators if cint(e.grades_activities)
    ]

    criteria = frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": course_schedule, "course_competency": ("is", "set")},
        fields=["name", "title", "course_competency"],
        order_by="idx asc",
    )
    by_competency = {}
    for c in criteria:
        by_competency.setdefault(c.course_competency, []).append(c)

    groups = []
    shapes = {}
    for comp in frappe.get_all(
        "Course Competency",
        filters={"course": course, "is_active": 1},
        fields=["name", "competency_name", "sequence"],
        order_by="sequence asc, competency_name asc",
    ):
        dimensions = frappe.get_all(
            "Course Competency Dimension",
            filters={"parent": comp.name},
            fields=["dimension_code", "dimension"],
            order_by="idx asc",
        )
        assessments = []
        for c in by_competency.get(comp.name, []):
            shape = cbe.grading_shape(c.name, framework)
            shapes[c.name] = shape
            weights = cbe.dimension_weights_for(c.name, comp.name)
            leaves = []
            # One grade for the whole activity has neither axis, so it is a
            # single column and whoever recorded it lands in it.
            if shape == cbe.PER_ACTIVITY_MODE:
                leaves.append(
                    {
                        "key": "{0}||".format(c.name),
                        "instructor_category": None,
                        "dimension_code": None,
                        "label": _("Grade"),
                    }
                )
            per_evaluator = [] if shape == cbe.PER_ACTIVITY_MODE else grading_categories
            for cat in per_evaluator:
                if not cbe.is_cell_graded(c.name, cat, None, shape):
                    continue
                if shape == cbe.PER_DIMENSION_MODE:
                    codes = cbe.graded_dimensions_for(
                        c.name,
                        cat,
                        [
                            d.dimension_code
                            for d in dimensions
                            if flt(weights.get(d.dimension_code)) > 0
                        ],
                    )
                    for d in dimensions:
                        if d.dimension_code not in codes:
                            continue
                        leaves.append(
                            {
                                "key": "{0}|{1}|{2}".format(
                                    c.name, cat, d.dimension_code
                                ),
                                "instructor_category": cat,
                                "dimension_code": d.dimension_code,
                                "label": d.dimension,
                            }
                        )
                else:
                    leaves.append(
                        {
                            "key": "{0}|{1}|".format(c.name, cat),
                            "instructor_category": cat,
                            "dimension_code": None,
                            "label": _("Overall"),
                        }
                    )
            if not leaves:
                continue
            assessments.append(
                {
                    "name": c.name,
                    "title": c.title,
                    "grading_mode": shape,
                    "leaves": leaves,
                }
            )
        groups.append(
            {
                "course_competency": comp.name,
                "competency_name": comp.competency_name,
                "assessments": assessments,
                "span": sum(len(a["leaves"]) for a in assessments),
            }
        )

    students = []
    for r in frappe.get_all(
        "Scheduled Course Roster",
        filters={"course_sc": course_schedule},
        fields=["name", "student", "stuname_roster", "active", "audit_bool"],
        order_by="stuname_roster asc",
    ):
        students.append(_gradebook_row(r, course_schedule, shapes))

    return {
        "is_cbe": True,
        "course_schedule": course_schedule,
        "groups": groups,
        "students": students,
        "verdict_categories": [
            e.instructor_category
            for e in framework.evaluators
            if cint(e.gives_competency_verdict)
        ],
    }


def _gradebook_row(roster, course_schedule, shapes):
    """One student's line: their levels, their mentors, their verdicts."""
    evaluators = cbe.evaluators_for(roster.name)
    names = _instructor_names({e["instructor"] for e in evaluators})
    # Who fills a category is resolved per student, not per section -- that is
    # the whole point of a mentor recorded on the enrollment (ADR 065 4).
    category_of = {e["instructor"]: e["instructor_category"] for e in evaluators}

    cells = {}
    for g in frappe.get_all(
        "Activity Competency Grade",
        filters={"roster": roster.name},
        fields=["assess_criteria", "instructor", "dimension_code", "level_code"],
    ):
        if shapes.get(g.assess_criteria) == cbe.PER_ACTIVITY_MODE:
            key = "{0}||".format(g.assess_criteria)
        else:
            category = category_of.get(g.instructor)
            if not category:
                continue
            key = "{0}|{1}|{2}".format(
                g.assess_criteria, category, g.dimension_code or ""
            )
        cells[key] = {
            "level_code": g.level_code,
            "instructor": names.get(g.instructor, g.instructor),
        }

    verdicts = {}
    for res in frappe.get_all(
        "Competency Result",
        filters={"student": roster.student, "course_schedule": course_schedule},
        fields=["course_competency", "status", "final_code", "final_value"],
    ):
        verdicts[res.course_competency] = res

    return {
        "roster": roster.name,
        "student": roster.student,
        "student_name": roster.stuname_roster,
        "finalized": bool(not roster.active and not roster.audit_bool),
        # Named rather than counted: an instructor looking at a level someone
        # else recorded needs to know who to ask about it.
        "mentors": [
            {
                "instructor_name": names.get(e["instructor"], e["instructor"]),
                "instructor_category": e["instructor_category"],
            }
            for e in evaluators
            if e["assignment_source"] == cbe.COHORT_SOURCE
        ],
        "cells": cells,
        "verdicts": verdicts,
    }


# ---------------------------------------------------------------- staff writes


@frappe.whitelist()
def save_activity_grade(
    roster,
    assess_criteria,
    level_code,
    dimension_code=None,
    narrative=None,
    instructor=None,
):
    """Record or update this evaluator's level on one activity.

    The evaluator is the caller's own Instructor record unless a manager names
    someone else, so an instructor cannot record a grade under a colleague's
    name by editing the request.
    """
    _assert_staff()
    me = _current_instructor()
    if instructor and instructor != me:
        if not (
            {"Seminary Manager", "System Manager", "Program Chair"}
            & set(frappe.get_roles())
        ):
            frappe.throw(
                _("You can only record your own assessment."), frappe.PermissionError
            )
    else:
        instructor = me
    if not instructor:
        frappe.throw(_("Your user account is not linked to an instructor record."))

    existing = frappe.db.get_value(
        "Activity Competency Grade",
        {
            "roster": roster,
            "assess_criteria": assess_criteria,
            "instructor": instructor,
            "dimension_code": dimension_code if dimension_code else ("in", ["", None]),
        },
        "name",
    )
    doc = (
        frappe.get_doc("Activity Competency Grade", existing)
        if existing
        else frappe.new_doc("Activity Competency Grade")
    )
    doc.update(
        {
            "roster": roster,
            "assess_criteria": assess_criteria,
            "instructor": instructor,
            "dimension_code": dimension_code or None,
            "level_code": level_code,
            "narrative": narrative,
        }
    )
    doc.save()
    return {"name": doc.name, "level_value": doc.level_value}


@frappe.whitelist()
def save_mentor_assessment(
    roster, course_competency, ratings, narrative=None, submit=0
):
    """A mentor's final assessment of a competency."""
    _assert_staff()
    instructor = _current_instructor()
    if not instructor:
        frappe.throw(_("Your user account is not linked to an instructor record."))
    roster_doc = frappe.get_doc("Scheduled Course Roster", roster)
    return _save_assessment(
        roster_doc,
        course_competency,
        "Final",
        "Mentor",
        ratings,
        narrative,
        submit,
        instructor,
    )


@frappe.whitelist()
def set_result_override(result, dimension_code, override_value, override_reason):
    """Replace a computed value, on the record, with a reason attached."""
    _assert_staff()
    doc = frappe.get_doc("Competency Result", result)
    if dimension_code:
        for row in doc.dimensions:
            if row.dimension_code == dimension_code:
                row.override_value = flt(override_value) or None
                row.override_reason = override_reason
                row.overridden_by = None  # re-stamped by the controller
                row.overridden_on = None
                break
        else:
            frappe.throw(
                _("Dimension {0} is not on this result.").format(dimension_code)
            )
    else:
        doc.override_value = flt(override_value) or None
        doc.override_reason = override_reason
        doc.overridden_by = None
        doc.overridden_on = None
    doc.save()
    return {"final_value": doc.final_value, "final_code": doc.final_code}


# ---------------------------------------------------------------- student


@frappe.whitelist()
def get_self_assessment(course_schedule, course_competency, stage="Final"):
    """The student's own assessment of one competency, with its guidance.

    Returns the descriptors alongside any saved answer, so the form can explain
    what each dimension means in this competency rather than asking for a number
    in the abstract.
    """
    student = _current_student()
    if not student:
        frappe.throw(_("This page is for students."), frappe.PermissionError)

    scale = cbe.scale_for(course_schedule)
    competency = frappe.get_doc("Course Competency", course_competency)
    existing = frappe.db.get_value(
        "Competency Assessment",
        {
            "student": student,
            "course_schedule": course_schedule,
            "course_competency": course_competency,
            "stage": stage,
            "evaluator_kind": "Self",
        },
        "name",
    )
    doc = frappe.get_doc("Competency Assessment", existing) if existing else None

    saved = {r.dimension_code: r for r in (doc.ratings if doc else [])}
    dimensions = []
    for d in competency.dimensions:
        row = saved.get(d.dimension_code)
        dimensions.append(
            {
                "dimension_code": d.dimension_code,
                "dimension": d.dimension,
                "demonstrated_by": d.demonstrated_by,
                "level_code": row.level_code if row else None,
                "narrative": row.narrative if row else None,
            }
        )

    return {
        "name": doc.name if doc else None,
        "status": doc.status if doc else "Draft",
        "stage": stage,
        "narrative": doc.narrative if doc else None,
        "submitted_on": doc.submitted_on if doc else None,
        "competency_name": competency.competency_name,
        "statement": competency.statement,
        "dimensions": dimensions,
        "levels": cbe.levels_for(scale),
    }


@frappe.whitelist()
def save_self_assessment(
    course_schedule,
    course_competency,
    ratings,
    narrative=None,
    stage="Final",
    submit=0,
):
    student = _current_student()
    if not student:
        frappe.throw(_("This page is for students."), frappe.PermissionError)
    roster = _roster_for(course_schedule, student)
    if not roster:
        frappe.throw(_("You are not enrolled in this section."), frappe.PermissionError)
    roster_doc = frappe.get_doc("Scheduled Course Roster", roster)
    return _save_assessment(
        roster_doc, course_competency, stage, "Self", ratings, narrative, submit, None
    )


def _save_assessment(
    roster_doc, course_competency, stage, kind, ratings, narrative, submit, instructor
):
    if isinstance(ratings, str):
        ratings = json.loads(ratings)

    filters = {
        "student": roster_doc.student,
        "course_schedule": roster_doc.course_sc,
        "course_competency": course_competency,
        "stage": stage,
        "evaluator_kind": kind,
    }
    if kind == "Mentor":
        filters["instructor"] = instructor
    existing = frappe.db.get_value("Competency Assessment", filters, "name")

    if existing:
        doc = frappe.get_doc("Competency Assessment", existing)
        if doc.status == "Submitted":
            frappe.throw(
                _(
                    "This assessment has already been submitted and cannot be "
                    "changed."
                )
            )
    else:
        doc = frappe.new_doc("Competency Assessment")
        doc.update(filters)
        doc.program_enrollment = frappe.db.get_value(
            "Program Enrollment",
            {"student": roster_doc.student, "program": roster_doc.program_std_scr},
            "name",
        )

    doc.narrative = narrative
    doc.set("ratings", [])
    for r in ratings or []:
        if not r.get("level_code"):
            continue
        doc.append(
            "ratings",
            {
                "dimension_code": r.get("dimension_code"),
                "level_code": r.get("level_code"),
                "narrative": r.get("narrative"),
            },
        )
    doc.status = "Submitted" if cint(submit) else "Draft"
    doc.flags.ignore_permissions = True
    doc.save()
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def get_student_competency_overview(course_schedule):
    """What a student sees for a course: each competency, its guidance, and
    where their own assessments stand."""
    student = _current_student()
    if not student:
        frappe.throw(_("This page is for students."), frappe.PermissionError)

    course = frappe.db.get_value("Course Schedule", course_schedule, "course")
    roster = frappe.db.get_value(
        "Scheduled Course Roster",
        {"course_sc": course_schedule, "student": student},
        ["active", "audit_bool"],
        as_dict=True,
    )
    # `active` is cleared when a student's grades are sent, which is the only
    # record of a partial send on an open-ended section (ADR 065 section 7a).
    finalized = bool(roster) and not roster.active and not roster.audit_bool
    chapters = {
        c.course_competency: c.name
        for c in frappe.get_all(
            "Course Schedule Chapter",
            filters={"coursesc": course_schedule, "course_competency": ("is", "set")},
            fields=["name", "course_competency"],
        )
    }

    out = []
    for c in frappe.get_all(
        "Course Competency",
        filters={"course": course, "is_active": 1},
        fields=["name", "competency_name", "sequence", "statement"],
        order_by="sequence asc",
    ):
        c["dimensions"] = frappe.get_all(
            "Course Competency Dimension",
            filters={"parent": c.name},
            fields=["dimension_code", "dimension", "demonstrated_by"],
            order_by="idx asc",
        )
        c["chapter"] = chapters.get(c.name)
        c["self_assessments"] = frappe.get_all(
            "Competency Assessment",
            filters={
                "student": student,
                "course_schedule": course_schedule,
                "course_competency": c.name,
                "evaluator_kind": "Self",
            },
            fields=["name", "stage", "status", "submitted_on"],
        )
        # A result reaches "Competent" as soon as one activity is graded, but
        # that is a working number: mentors may still be grading and the value
        # can move. The student sees it only once their grades have actually
        # been sent, so a provisional average is never read as a verdict.
        c["result"] = (
            frappe.db.get_value(
                "Competency Result",
                {
                    "student": student,
                    "course_schedule": course_schedule,
                    "course_competency": c.name,
                },
                ["status", "final_code", "final_value"],
                as_dict=True,
            )
            if finalized
            else None
        )
        out.append(c)
    return out


# ---------------------------------------------------------------- worklist


@frappe.whitelist()
def get_competency_worklist():
    """A mentor's outstanding competency work, across every section.

    This is the same resolution as evaluators_for, inverted: because mentors are
    never added to a section, this list is the only place a Personal Mentor
    finds out they have grading to do.
    """
    instructor = _current_instructor()
    if not instructor:
        return []

    open_states = ("Grading", "Enrollment Closed", "Open for Enrollment")
    rosters = frappe.get_all(
        "Scheduled Course Roster",
        filters={"active": 1, "audit_bool": 0},
        fields=["name", "student", "stuname_roster", "course_sc"],
        limit=2000,
    )

    items = []
    for r in rosters:
        state = frappe.db.get_value("Course Schedule", r.course_sc, "workflow_state")
        if state not in open_states:
            continue
        if not cbe.framework_for(r.course_sc):
            continue
        mine = [e for e in cbe.evaluators_for(r.name) if e["instructor"] == instructor]
        if not mine:
            continue
        outstanding = cbe.missing_required_evaluators(r.name)
        mine_outstanding = [m for m in outstanding if instructor in m]
        pending_verdicts = _pending_verdicts(r, instructor, mine)
        if not mine_outstanding and not pending_verdicts:
            continue
        items.append(
            {
                "roster": r.name,
                "student": r.student,
                "student_name": r.stuname_roster,
                "course_schedule": r.course_sc,
                "activities": mine_outstanding,
                "verdicts": pending_verdicts,
            }
        )
    return items


def _pending_verdicts(roster_row, instructor, my_roles):
    if not any(m["gives_competency_verdict"] for m in my_roles):
        return []
    course = frappe.db.get_value("Course Schedule", roster_row.course_sc, "course")
    pending = []
    for c in frappe.get_all(
        "Course Competency",
        filters={"course": course, "is_active": 1},
        fields=["name", "competency_name"],
        order_by="sequence asc",
    ):
        done = frappe.db.exists(
            "Competency Assessment",
            {
                "student": roster_row.student,
                "course_schedule": roster_row.course_sc,
                "course_competency": c.name,
                "evaluator_kind": "Mentor",
                "instructor": instructor,
                "status": "Submitted",
            },
        )
        if not done:
            pending.append({"competency": c.name, "label": c.competency_name})
    return pending


# ---------------------------------------------------------------- outline


@frappe.whitelist()
def get_outline_competencies(course_schedule):
    """Per-chapter competency guidance and lock state for the course outline.

    One call rather than two: the panel and the lock are the same mapping seen
    from different angles, and splitting them would let the outline render a
    competency's descriptors above a chapter it has already decided is closed.

    Staff see the competency panels with nothing locked -- gating is about a
    student's own progress, and an instructor looking at the outline is not
    walking through it.
    """
    framework = cbe.framework_doc(course_schedule)
    if not framework:
        return {"is_cbe": False, "chapters": {}}

    chapters = frappe.get_all(
        "Course Schedule Chapter",
        filters={"coursesc": course_schedule, "course_competency": ("is", "set")},
        fields=["name", "course_competency"],
    )

    student = _current_student()
    gating = {
        "mode": cbe.content_release_mode(course_schedule, framework),
        "gated": False,
        "chapters": {},
    }
    prompts = {"baseline": False, "chapters": {}, "final_all": False, "points": None}
    if student and not _is_staff():
        roster = _roster_for(course_schedule, student)
        if roster:
            gating = cbe.visible_outline(roster)
            # When to *ask*, as against what to show: the outline used to offer
            # the prompt on every mapped chapter regardless of the framework's
            # timing or the student's progress (ADR 065 section 11e).
            prompts = cbe.self_assessment_prompts(roster)

    out = {}
    for ch in chapters:
        competency = frappe.get_doc("Course Competency", ch.course_competency)
        submitted = (
            {
                a.stage
                for a in frappe.get_all(
                    "Competency Assessment",
                    filters={
                        "student": student,
                        "course_schedule": course_schedule,
                        "course_competency": ch.course_competency,
                        "evaluator_kind": "Self",
                        "status": "Submitted",
                    },
                    fields=["stage"],
                )
            }
            if student
            else set()
        )
        state = gating["chapters"].get(ch.name, {})
        out[ch.name] = {
            "competency": ch.course_competency,
            "competency_name": competency.competency_name,
            "statement": competency.statement,
            "dimensions": [
                {
                    "dimension_code": d.dimension_code,
                    "dimension": d.dimension,
                    "demonstrated_by": d.demonstrated_by,
                }
                for d in competency.dimensions
            ],
            "self_assessment_submitted": sorted(submitted),
            "final_due": ch.name in prompts["chapters"],
            "locked": bool(state.get("locked")),
            "activities_locked": bool(state.get("activities_locked")),
            "reason": state.get("reason"),
            "unlock_competency": state.get("unlock_competency"),
        }

    return {
        "is_cbe": True,
        "mode": gating.get("mode"),
        "gated": gating.get("gated", False),
        "self_eval_enabled": cint(framework.course_self_eval),
        "self_eval_points": framework.course_self_eval_points,
        "baseline_due": prompts["baseline"],
        "final_all_due": prompts["final_all"],
        "chapters": out,
    }


# ---------------------------------------------------------------- profile


def _assert_own_enrollment(program_enrollment):
    student = frappe.db.get_value("Program Enrollment", program_enrollment, "student")
    if not student:
        frappe.throw(_("Enrollment not found."))
    if not _is_staff():
        mine = _current_student()
        if not mine or mine != student:
            frappe.throw(_("Not permitted."), frappe.PermissionError)
    return student


def _cbe_enrollments(student):
    """The student's enrollments whose programme runs on a framework."""
    out = []
    for pe in frappe.get_all(
        "Program Enrollment",
        filters={"student": student, "docstatus": 1},
        fields=["name", "program", "status", "pgmenrol_active"],
        order_by="pgmenrol_active desc, creation desc",
    ):
        framework = frappe.db.get_value("Program", pe.program, "competency_framework")
        if not framework:
            continue
        pe["framework"] = framework
        out.append(pe)
    return out


def _instructor_names(instructors):
    if not instructors:
        return {}
    return {
        r.name: r.instructor_name
        for r in frappe.get_all(
            "Instructor",
            filters={"name": ("in", list(instructors))},
            fields=["name", "instructor_name"],
        )
    }


def _profile_assessments(student, course_schedule, competency):
    """Every submitted assessment of one competency, split by who gave it.

    Drafts never surface: an unsubmitted rating is a thought in progress, and
    the whole point of the radar is to compare positions people have taken.
    """
    rows = frappe.get_all(
        "Competency Assessment",
        filters={
            "student": student,
            "course_schedule": course_schedule,
            "course_competency": competency,
            "status": "Submitted",
        },
        fields=[
            "name",
            "stage",
            "evaluator_kind",
            "instructor",
            "instructor_category",
            "narrative",
            "submitted_on",
        ],
        order_by="submitted_on asc",
    )
    if not rows:
        return rows, {}
    ratings = {}
    for r in frappe.get_all(
        "Competency Assessment Rating",
        filters={"parent": ("in", [x.name for x in rows])},
        fields=[
            "parent",
            "dimension_code",
            "dimension",
            "level_code",
            "level_value",
            "narrative",
        ],
        order_by="idx asc",
    ):
        ratings.setdefault(r.parent, []).append(r)
    return rows, ratings


def _series_from(rows, ratings, predicate):
    """Average the matching assessments' levels, per dimension.

    Averaging rather than taking the latest: when a school runs two mentors,
    both verdicts are real and the radar would otherwise silently drop one.
    """
    picked = [r for r in rows if predicate(r)]
    if not picked:
        return None
    buckets = {}
    for r in picked:
        for rating in ratings.get(r.name, []):
            if rating.level_value is None:
                continue
            buckets.setdefault(rating.dimension_code, []).append(
                flt(rating.level_value)
            )
    if not buckets:
        return None
    return {code: sum(vals) / len(vals) for code, vals in buckets.items()}


def _overall(values):
    """One number for a competency from its dimension values."""
    present = [v for v in (values or {}).values() if v is not None]
    return sum(present) / len(present) if present else None


@frappe.whitelist()
def get_competency_transcript(program_enrollment=None):
    """Finalized competency standing, keyed by course schedule.

    Feeds the transcript, so it reports only what has actually been sent: a
    Competency Result reaches "Competent" as soon as one activity is graded and
    keeps moving until the roster is finalized (ADR 065 section 7a), and a
    transcript that showed the working number would be wrong most of the time.
    """
    student = _current_student()
    if not student:
        return {}

    rosters = frappe.get_all(
        "Scheduled Course Roster",
        filters={"student": student},
        fields=["name", "course_sc", "active", "audit_bool"],
    )
    out = {}
    for r in rosters:
        if r.active or r.audit_bool:
            continue
        framework = cbe.framework_for(r.course_sc)
        if not framework:
            continue
        results = frappe.get_all(
            "Competency Result",
            filters={"student": student, "course_schedule": r.course_sc},
            fields=[
                "name",
                "course_competency",
                "competency_name",
                "status",
                "final_code",
                "final_value",
            ],
        )
        if not results:
            continue
        if program_enrollment:
            pe = frappe.db.get_value(
                "Competency Result", results[0].name, "program_enrollment"
            )
            if pe != program_enrollment:
                continue
        for res in results:
            res["dimensions"] = frappe.get_all(
                "Competency Result Dimension",
                filters={"parent": res.name},
                fields=["dimension_code", "dimension", "final_code", "final_value"],
                order_by="idx asc",
            )
        out[r.course_sc] = {
            "framework": framework,
            "grading_scale": cbe.scale_for(r.course_sc),
            "competencies": results,
        }
    return out


@frappe.whitelist()
def get_competency_profile(program_enrollment=None):
    """The radar and the narrative timeline for one programme enrollment.

    Scoped to an enrollment rather than to the student because the dimensions
    and the level vocabulary come from the programme's framework: two programmes
    can disagree about what the axes even are, and a radar drawn across both
    would be a picture of nothing.
    """
    student = _current_student()
    if not student and not _is_staff():
        frappe.throw(_("This page is for students."), frappe.PermissionError)

    if program_enrollment:
        student = _assert_own_enrollment(program_enrollment)

    enrollments = _cbe_enrollments(student)
    if not enrollments:
        return {"is_cbe": False, "enrollments": []}

    chosen = None
    for pe in enrollments:
        if program_enrollment and pe.name == program_enrollment:
            chosen = pe
    if not chosen:
        chosen = enrollments[0]

    framework = frappe.get_cached_doc("Competency Framework", chosen.framework)
    scale = framework.grading_scale
    levels = cbe.levels_for(scale)
    dimensions = frappe.get_all(
        "Grading Scale Dimensions",
        filters={"parent": scale},
        fields=["dimension_code", "dimension", "description", "dimension_icon"],
        order_by="sequence asc, idx asc",
    )

    rosters = frappe.get_all(
        "Scheduled Course Roster",
        filters={"student": student},
        fields=["name", "course_sc", "active", "audit_bool"],
    )

    courses = []
    for r in rosters:
        if cbe.framework_for(r.course_sc) != chosen.framework:
            continue
        cs = frappe.db.get_value(
            "Course Schedule",
            r.course_sc,
            ["course", "title", "academic_term", "c_datestart"],
            as_dict=True,
        )
        # A section's own title is optional; the course's name is what the
        # student recognises when it is missing.
        course_name = cs.title or frappe.db.get_value(
            "Course", cs.course, "course_name"
        )
        finalized = not r.active and not r.audit_bool
        competencies = []
        for c in frappe.get_all(
            "Course Competency",
            filters={"course": cs.course, "is_active": 1},
            fields=["name", "competency_name", "statement", "sequence"],
            order_by="sequence asc, competency_name asc",
        ):
            rows, ratings = _profile_assessments(student, r.course_sc, c.name)
            series = {
                "baseline": _series_from(
                    rows,
                    ratings,
                    lambda x: x.evaluator_kind == "Self" and x.stage == "Baseline",
                ),
                "self_final": _series_from(
                    rows,
                    ratings,
                    lambda x: x.evaluator_kind == "Self" and x.stage == "Final",
                ),
                "mentor_final": _series_from(
                    rows,
                    ratings,
                    lambda x: x.evaluator_kind != "Self" and x.stage == "Final",
                ),
            }
            series["result"] = _result_series(student, r.course_sc, c.name, finalized)
            c["series"] = series
            c["overall"] = {k: _overall(v) for k, v in series.items()}
            c["narratives"] = _narrative_timeline(rows, ratings)
            competencies.append(c)

        if not competencies:
            continue
        courses.append(
            {
                "course_schedule": r.course_sc,
                "course": cs.course,
                "course_name": course_name,
                "academic_term": cs.academic_term,
                "start_date": cs.c_datestart,
                "finalized": finalized,
                "competencies": competencies,
            }
        )

    courses.sort(key=lambda c: (c["start_date"] or "", c["course_name"] or ""))

    return {
        "is_cbe": True,
        "enrollments": [
            {
                "name": pe.name,
                "program": pe.program,
                "status": pe.status,
                "active": pe.pgmenrol_active,
            }
            for pe in enrollments
        ],
        "program_enrollment": chosen.name,
        "program": chosen.program,
        "grading_scale": scale,
        "levels": levels,
        "max_value": max([flt(x.threshold) for x in levels] or [4]),
        "dimensions": dimensions,
        "self_eval_enabled": cint(framework.course_self_eval),
        "courses": courses,
    }


def _result_series(student, course_schedule, competency, finalized):
    """The recorded verdict, per dimension — only once grades have been sent."""
    if not finalized:
        return None
    result = frappe.db.get_value(
        "Competency Result",
        {
            "student": student,
            "course_schedule": course_schedule,
            "course_competency": competency,
        },
        "name",
    )
    if not result:
        return None
    values = {
        d.dimension_code: flt(d.final_value)
        for d in frappe.get_all(
            "Competency Result Dimension",
            filters={"parent": result},
            fields=["dimension_code", "final_value"],
        )
        if d.final_value is not None
    }
    return values or None


def _narrative_timeline(rows, ratings):
    """Every narrative anyone wrote about this competency, in order.

    The competency-level narrative and the per-dimension ones are flattened into
    one list because the reader is asking "what did people say about this", not
    "which field was it stored in".
    """
    names = _instructor_names({r.instructor for r in rows if r.instructor})
    out = []
    for r in rows:
        who = (
            _("You")
            if r.evaluator_kind == "Self"
            else (names.get(r.instructor) or r.instructor or r.instructor_category)
        )
        base = {
            "assessment": r.name,
            "evaluator_kind": r.evaluator_kind,
            "evaluator": who,
            "instructor_category": r.instructor_category,
            "stage": r.stage,
            "submitted_on": r.submitted_on,
        }
        if r.narrative:
            out.append(
                dict(base, dimension_code=None, dimension=None, narrative=r.narrative)
            )
        for rating in ratings.get(r.name, []):
            if not rating.narrative and rating.level_code is None:
                continue
            out.append(
                dict(
                    base,
                    dimension_code=rating.dimension_code,
                    dimension=rating.dimension,
                    level_code=rating.level_code,
                    level_value=rating.level_value,
                    narrative=rating.narrative,
                )
            )
    return out


# ---------------------------------------------------------------- development plan


def _plan_questions(framework):
    return [
        {
            "question_key": q.question_key,
            "question_text": q.question_text,
            "sequence": q.sequence,
        }
        for q in sorted(
            [q for q in framework.development_questions if cint(q.active)],
            key=lambda q: (cint(q.sequence), cint(q.idx)),
        )
    ]


def _plan_payload(doc, framework, course_schedule):
    questions = _plan_questions(framework)
    answered = {g.standard_question for g in doc.goals if g.standard_question}
    return {
        "name": doc.name,
        "status": doc.status,
        "reflection": doc.reflection,
        "submitted_on": doc.submitted_on,
        "mentor_feedback": doc.mentor_feedback,
        "reviewed_by": doc.reviewed_by,
        "reviewed_on": doc.reviewed_on,
        "goals": [
            {
                "standard_question": g.standard_question,
                "question_text": g.question_text,
                "course_competency": g.course_competency,
                "dimension_code": g.dimension_code,
                "goal": g.goal,
                "action_steps": g.action_steps,
                "target_date": g.target_date,
                "support_needed": g.support_needed,
                "status": g.status,
            }
            for g in doc.goals
        ],
        # The prompts still without an answer, so the page can offer them
        # without the student hunting for which ones they have done.
        "unanswered": [q for q in questions if q["question_key"] not in answered],
        "questions": questions,
        "course_schedule": course_schedule,
    }


@frappe.whitelist()
def get_development_plan(course_schedule, student=None):
    """A student's plan for one section, with the framework's prompts.

    Staff may read another student's; a student may only read their own, which
    `_assert_own_roster` decides rather than the caller.
    """
    framework = cbe.framework_doc(course_schedule)
    if not framework:
        return {"is_cbe": False}

    student = student if (student and _is_staff()) else _current_student()
    if not student:
        frappe.throw(_("This page is for students."), frappe.PermissionError)
    roster = _roster_for(course_schedule, student)
    if not roster:
        return {"is_cbe": True, "enrolled": False}
    _assert_own_roster(roster)

    name = frappe.db.get_value("Personal Development Plan", {"roster": roster}, "name")
    if name:
        doc = frappe.get_doc("Personal Development Plan", name)
    else:
        # Not created here: an unsaved shape lets the page render the prompts
        # without leaving an empty plan behind for a student who never returns.
        doc = frappe.new_doc("Personal Development Plan")
        doc.roster = roster

    payload = _plan_payload(doc, framework, course_schedule)
    payload.update(
        {
            "is_cbe": True,
            "enrolled": True,
            "roster": roster,
            "student": student,
            "student_name": frappe.db.get_value("Student", student, "student_name"),
            "require_pdp": cint(framework.require_pdp),
            "blocks_completion": cint(framework.pdp_blocks_completion),
            "competencies": frappe.get_all(
                "Course Competency",
                filters={
                    "course": frappe.db.get_value(
                        "Course Schedule", course_schedule, "course"
                    ),
                    "is_active": 1,
                },
                fields=["name", "competency_name"],
                order_by="sequence asc, competency_name asc",
            ),
            "dimensions": frappe.get_all(
                "Grading Scale Dimensions",
                filters={"parent": cbe.scale_for(course_schedule)},
                fields=["dimension_code", "dimension"],
                order_by="sequence asc, idx asc",
            ),
            "viewer_is_staff": _is_staff(),
        }
    )
    return payload


@frappe.whitelist()
def save_development_plan(course_schedule, goals, reflection=None, submit=0):
    """Write the student's own plan. Submitting is not reversible by the student.

    Only the student writes here; a mentor's response goes through
    `review_development_plan`, so a review can never overwrite the reflection it
    is responding to.
    """
    student = _current_student()
    if not student:
        frappe.throw(_("This page is for students."), frappe.PermissionError)
    roster = _roster_for(course_schedule, student)
    if not roster:
        frappe.throw(_("You are not enrolled in this course."), frappe.PermissionError)
    if not cbe.framework_for(course_schedule):
        frappe.throw(_("This course is not competency-based."))

    name = frappe.db.get_value("Personal Development Plan", {"roster": roster}, "name")
    doc = (
        frappe.get_doc("Personal Development Plan", name)
        if name
        else frappe.new_doc("Personal Development Plan")
    )
    if doc.status != "Draft":
        frappe.throw(_("This plan has been submitted and can no longer be changed."))

    doc.roster = roster
    doc.reflection = reflection
    doc.goals = []
    for row in json.loads(goals) if isinstance(goals, str) else goals:
        if not (row.get("goal") or "").strip():
            continue
        doc.append(
            "goals",
            {
                "standard_question": row.get("standard_question") or None,
                "course_competency": row.get("course_competency") or None,
                "dimension_code": row.get("dimension_code") or None,
                "goal": row.get("goal"),
                "action_steps": row.get("action_steps"),
                "target_date": row.get("target_date") or None,
                "support_needed": row.get("support_needed"),
                "status": row.get("status") or "Planned",
            },
        )
    if cint(submit):
        if not doc.goals:
            frappe.throw(_("Add at least one goal before submitting."))
        doc.status = "Submitted"
    doc.flags.ignore_permissions = True
    doc.save()
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def review_development_plan(plan, mentor_feedback=None, accept=0):
    """A mentor's response to a submitted plan.

    Separate from the student's write path so a review cannot edit the goals it
    is responding to; the mentor answers, they do not rewrite.
    """
    _assert_staff()
    doc = frappe.get_doc("Personal Development Plan", plan)
    if doc.status == "Draft":
        frappe.throw(_("This plan has not been submitted yet."))

    instructor = _current_instructor()
    if instructor and not any(
        e["instructor"] == instructor for e in cbe.evaluators_for(doc.roster)
    ):
        frappe.throw(
            _("You are not an evaluator for this student."), frappe.PermissionError
        )

    doc.mentor_feedback = mentor_feedback
    doc.reviewed_by = instructor
    doc.reviewed_on = frappe.utils.now_datetime()
    doc.status = "Accepted" if cint(accept) else "Reviewed"
    doc.flags.ignore_permissions = True
    doc.save()
    return {"name": doc.name, "status": doc.status}


# ---------------------------------------------------------------- the arc


def _assert_may_read_student(student):
    """A student reads their own arc; a mentor reads their mentees'.

    Resolved here rather than trusted from the caller, because this endpoint is
    the whole reading surface for a student's journal.
    """
    mine = _current_student()
    if mine and mine == student:
        return
    if set(frappe.get_roles()) & {
        "Seminary Manager",
        "System Manager",
        "Program Chair",
    }:
        return
    instructor = _current_instructor()
    if instructor and cbe.is_mentor_of(instructor, student):
        return
    frappe.throw(_("Not permitted."), frappe.PermissionError)


@frappe.whitelist()
def get_mentees():
    """The students an instructor currently mentors, for the mentor's selector."""
    instructor = _current_instructor()
    if not instructor:
        return []
    return [
        {
            "student": s,
            "student_name": frappe.db.get_value("Student", s, "student_name"),
        }
        for s in cbe.mentees_of(instructor)
    ]


@frappe.whitelist()
def get_development_arc(student=None):
    """Every plan, goal and note a student has written, across every course.

    This is the answer to the lifelong-journey problem (ADR 065 section 8a), and
    the reason plans need no `carried_forward_from`: continuity is produced by
    reading the independent records together, not by one plan claiming another's
    goals. The same payload is grouped three ways -- by question, by competency,
    by course -- because those are three different questions about the same
    material and a page cannot re-derive the last two cheaply.
    """
    student = student or _current_student()
    if not student:
        frappe.throw(_("This page is for students."), frappe.PermissionError)
    _assert_may_read_student(student)

    plans = frappe.get_all(
        "Personal Development Plan",
        filters={"student": student},
        fields=[
            "name",
            "course_schedule",
            "status",
            "reflection",
            "submitted_on",
            "mentor_feedback",
            "reviewed_on",
        ],
    )
    if not plans:
        return _empty_arc(student)

    course_names = _course_labels([p.course_schedule for p in plans])
    starts = {
        cs.name: cs.c_datestart
        for cs in frappe.get_all(
            "Course Schedule",
            filters={"name": ("in", [p.course_schedule for p in plans])},
            fields=["name", "c_datestart"],
        )
    }
    plans.sort(key=lambda p: (starts.get(p.course_schedule) or "", p.name))

    goals = frappe.get_all(
        "Personal Development Plan Goal",
        filters={"parent": ("in", [p.name for p in plans])},
        fields=[
            "parent",
            "idx",
            "standard_question",
            "question_text",
            "course_competency",
            "dimension_code",
            "goal",
            "action_steps",
            "target_date",
            "support_needed",
            "status",
        ],
        order_by="idx asc",
    )
    by_plan = {}
    for g in goals:
        by_plan.setdefault(g.parent, []).append(g)

    for p in plans:
        p["course_name"] = course_names.get(p.course_schedule, p.course_schedule)
        p["start_date"] = starts.get(p.course_schedule)
        p["goals"] = by_plan.get(p.name, [])

    competency_names = _competency_labels(
        {g.course_competency for g in goals if g.course_competency}
    )

    return {
        "student": student,
        "student_name": frappe.db.get_value("Student", student, "student_name"),
        "viewer_is_owner": _current_student() == student,
        "courses": plans,
        "by_question": _group_by_question(plans),
        "by_competency": _group_by_competency(plans, competency_names),
        "notes": get_development_notes(student),
        "competency_names": competency_names,
    }


def _empty_arc(student):
    return {
        "student": student,
        "student_name": frappe.db.get_value("Student", student, "student_name"),
        "viewer_is_owner": _current_student() == student,
        "courses": [],
        "by_question": [],
        "by_competency": [],
        "notes": get_development_notes(student),
        "competency_names": {},
    }


def _course_labels(course_schedules):
    labels = {}
    for cs in frappe.get_all(
        "Course Schedule",
        filters={"name": ("in", list(course_schedules))},
        fields=["name", "title", "course"],
    ):
        labels[cs.name] = cs.title or frappe.db.get_value(
            "Course", cs.course, "course_name"
        )
    return labels


def _competency_labels(names):
    if not names:
        return {}
    return {
        c.name: c.competency_name
        for c in frappe.get_all(
            "Course Competency",
            filters={"name": ("in", list(names))},
            fields=["name", "competency_name"],
        )
    }


def _group_by_question(plans):
    """Every answer to the same prompt, in course order.

    This is where growth becomes visible without any goal being copied forward:
    four years of answers to "where do you most need to grow in character?",
    read down the page. Keyed on `question_key`, which is why the key is stable
    and separate from the editable text.
    """
    groups = {}
    for p in plans:
        for g in p["goals"]:
            if not g.standard_question:
                continue
            entry = groups.setdefault(
                g.standard_question,
                {
                    "question_key": g.standard_question,
                    "question_text": g.question_text,
                    "answers": [],
                },
            )
            # The most recent wording wins: a reworded prompt is still the same
            # question, and showing the oldest phrasing would misdescribe it.
            if g.question_text:
                entry["question_text"] = g.question_text
            entry["answers"].append(
                {
                    "course_schedule": p.course_schedule,
                    "course_name": p["course_name"],
                    "start_date": p["start_date"],
                    "goal": g.goal,
                    "action_steps": g.action_steps,
                    "status": g.status,
                    "target_date": g.target_date,
                }
            )
    return sorted(groups.values(), key=lambda x: x["question_key"])


def _group_by_competency(plans, competency_names):
    groups = {}
    for p in plans:
        for g in p["goals"]:
            if not g.course_competency:
                continue
            key = (g.course_competency, g.dimension_code or "")
            entry = groups.setdefault(
                key,
                {
                    "course_competency": g.course_competency,
                    "competency_name": competency_names.get(
                        g.course_competency, g.course_competency
                    ),
                    "dimension_code": g.dimension_code,
                    "goals": [],
                },
            )
            entry["goals"].append(
                {
                    "course_schedule": p.course_schedule,
                    "course_name": p["course_name"],
                    "start_date": p["start_date"],
                    "goal": g.goal,
                    "status": g.status,
                }
            )
    return sorted(
        groups.values(), key=lambda x: (x["competency_name"], x["dimension_code"] or "")
    )


@frappe.whitelist()
def get_development_notes(student=None, limit=200):
    student = student or _current_student()
    if not student:
        return []
    _assert_may_read_student(student)
    notes = frappe.get_all(
        "Personal Development Note",
        filters={"student": student},
        fields=[
            "name",
            "note",
            "note_date",
            "course_schedule",
            "course_competency",
            "dimension_code",
            "development_plan",
            "owner",
        ],
        order_by="note_date desc",
        limit=cint(limit),
        ignore_permissions=True,
    )
    labels = _course_labels({n.course_schedule for n in notes if n.course_schedule})
    competencies = _competency_labels(
        {n.course_competency for n in notes if n.course_competency}
    )
    for n in notes:
        n["course_name"] = labels.get(n.course_schedule)
        n["competency_name"] = competencies.get(n.course_competency)
    return notes


@frappe.whitelist()
def save_development_note(
    note,
    name=None,
    course_schedule=None,
    course_competency=None,
    dimension_code=None,
    development_plan=None,
):
    """Only the student writes their own journal.

    Mentors read; they respond on the plan, not in the journal. Enforced here as
    well as on the doctype, because a mentor holds the Instructor role and would
    otherwise inherit whatever that role is granted.
    """
    student = _current_student()
    if not student:
        frappe.throw(_("This is your own journal."), frappe.PermissionError)

    doc = (
        frappe.get_doc("Personal Development Note", name)
        if name
        else frappe.new_doc("Personal Development Note")
    )
    if doc.student and doc.student != student:
        frappe.throw(_("Not permitted."), frappe.PermissionError)

    doc.student = student
    doc.note = note
    doc.course_schedule = course_schedule or None
    doc.course_competency = course_competency or None
    doc.dimension_code = dimension_code or None
    doc.development_plan = development_plan or None
    doc.flags.ignore_permissions = True
    doc.save()
    return {"name": doc.name}


@frappe.whitelist()
def delete_development_note(name):
    student = _current_student()
    owner = frappe.db.get_value("Personal Development Note", name, "student")
    if not student or owner != student:
        frappe.throw(_("Not permitted."), frappe.PermissionError)
    frappe.delete_doc(
        "Personal Development Note",
        name,
        ignore_permissions=True,
        delete_permanently=True,
    )
    return {"deleted": name}


# ---------------------------------------------------------------- assessment config


@frappe.whitelist()
def save_assessment_competency_config(course_schedule, config):
    """Dimension weights and the grading matrix for a section's assessments.

    Separate from `save_course_assessment` because these are separate records --
    `Assessment Dimension Weight` and `Assessment Grading Matrix` are standalone
    doctypes, not columns on the criteria row -- and because the criteria have to
    exist and be named before anything can point at them.
    """
    _assert_staff()
    framework = cbe.framework_doc(course_schedule)
    if not framework:
        frappe.throw(_("This section is not competency-based."))

    config = json.loads(config) if isinstance(config, str) else config
    for row in config:
        criteria = row.get("assess_criteria")
        if not criteria:
            continue
        if (
            frappe.db.get_value("Scheduled Course Assess Criteria", criteria, "parent")
            != course_schedule
        ):
            frappe.throw(_("Assessment {0} is not in this section.").format(criteria))
        _save_dimension_weights(criteria, row.get("weights") or {})
        _save_grading_matrix(criteria, row.get("matrix") or [])
    return {"saved": len(config)}


def _save_dimension_weights(assess_criteria, weights):
    """Upsert the per-dimension weights, deleting any the form dropped."""
    existing = {
        w.dimension_code: w.name
        for w in frappe.get_all(
            "Assessment Dimension Weight",
            filters={"assess_criteria": assess_criteria},
            fields=["name", "dimension_code"],
        )
    }
    for code, value in weights.items():
        if code in existing:
            doc = frappe.get_doc("Assessment Dimension Weight", existing.pop(code))
        else:
            doc = frappe.new_doc("Assessment Dimension Weight")
            doc.assess_criteria = assess_criteria
            doc.dimension_code = code
        doc.weight = flt(value)
        doc.flags.ignore_permissions = True
        doc.save()
    for name in existing.values():
        frappe.delete_doc(
            "Assessment Dimension Weight", name, ignore_permissions=True, force=True
        )


def _save_grading_matrix(assess_criteria, cells):
    """Upsert cell choices, deleting the ones the form no longer states.

    Deleting rather than writing `graded = 1` matters: an absent row means
    "follow the shape", which is not the same claim as "explicitly on", and a
    section that later changes its grading mode should follow the new one.
    """
    existing = {
        (c.instructor_category, c.dimension_code): c.name
        for c in frappe.get_all(
            "Assessment Grading Matrix",
            filters={"assess_criteria": assess_criteria},
            fields=["name", "instructor_category", "dimension_code"],
        )
    }
    for cell in cells:
        key = (cell.get("instructor_category"), cell.get("dimension_code"))
        if not all(key):
            continue
        if key in existing:
            doc = frappe.get_doc("Assessment Grading Matrix", existing.pop(key))
        else:
            doc = frappe.new_doc("Assessment Grading Matrix")
            doc.assess_criteria = assess_criteria
            doc.instructor_category = key[0]
            doc.dimension_code = key[1]
        doc.graded = cint(cell.get("graded"))
        doc.flags.ignore_permissions = True
        doc.save()
    for name in existing.values():
        frappe.delete_doc(
            "Assessment Grading Matrix", name, ignore_permissions=True, force=True
        )
