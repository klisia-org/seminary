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
        ["course", "gradesc_cs", "workflow_state", "open_ended", "c_dateend"],
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

    assessments = []
    for a in frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": course_schedule, "course_competency": ("is", "set")},
        fields=[
            "name",
            "title",
            "course_competency",
            "grading_mode_override",
            "due_date",
        ],
        order_by="idx asc",
    ):
        a["weights"] = cbe.dimension_weights_for(a.name, a.course_competency)
        a["grading_mode"] = a.grading_mode_override or framework.activity_grading_mode
        assessments.append(a)

    return {
        "is_cbe": True,
        "course_schedule": course_schedule,
        "workflow_state": cs.workflow_state,
        "open_ended": bool(cs.open_ended),
        "grading_scale": scale,
        "levels": cbe.levels_for(scale),
        "dimensions": dimensions,
        "competencies": competencies,
        "assessments": assessments,
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
        for a in c["assessments"]:
            a["grades"] = grade_index.get(a.name, {})
            a["weights"] = cbe.dimension_weights_for(a.name, c.name)
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
    gating = {"mode": framework.content_release_mode, "gated": False, "chapters": {}}
    if student and not _is_staff():
        roster = _roster_for(course_schedule, student)
        if roster:
            gating = cbe.visible_outline(roster)

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
