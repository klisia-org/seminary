# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Rubrics on assignments and discussions (decisions/095).

The school owns the levels (Rubric Scale); the instructor owns the criteria
(Rubric, one per activity, versioned once used); the grader picks a level per
criterion (Rubric Score). We do the arithmetic: weights are free numbers
rescaled to a total of 100, and the grade is Σ share × level percent of the
section's maximum grade.

Other apps read scores through `criterion_scores` and listen through three
hooks, so seminary never names what they measure:

- ``rubric_scored``: ``fn(submission)`` after a submission's scores are saved;
- ``rubric_replaced``: ``fn(activity_doctype, activity, old, new)`` whenever an
  activity's rubric is saved or removed (``old == new`` for an edit in place);
- ``rubric_criterion_labels``: ``fn(activity_doctype, activity) ->
  {criterion_code: [label]}``, chips shown beside each criterion.
"""

import re

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from seminary.seminary.guards import (
    is_course_staff,
    require_course_staff,
    require_grader,
)

ACTIVITIES = {
    "Assignment Activity": "title",
    "Discussion Activity": "discussion_name",
}

# submission doctype -> (activity doctype, activity field, section field)
SUBMISSIONS = {
    "Assignment Submission": ("Assignment Activity", "assignment", "course"),
    "Discussion Submission": ("Discussion Activity", "disc_activity", "coursesc"),
}


# --- arithmetic ---------------------------------------------------------------


def shares(criteria) -> dict:
    """{criterion_code: share}, shares summing to 1.

    A blank (or zero) weight counts as an average criterion, so a rubric with
    no weights at all splits evenly and one with a few typed weights does not
    drop the others to nothing."""
    weights = [flt(c.get("weight")) for c in criteria]
    typed = [w for w in weights if w > 0]
    fill = sum(typed) / len(typed) if typed else 1.0
    weights = [w if w > 0 else fill for w in weights]
    total = sum(weights)
    if not total:
        return {}
    return {c.get("criterion_code"): w / total for c, w in zip(criteria, weights)}


def slug(text) -> str:
    return (
        re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40] or "criterion"
    )


def scale_levels(scale) -> list:
    return frappe.get_all(
        "Rubric Scale Level",
        filters={"parent": scale, "parenttype": "Rubric Scale"},
        fields=["label", "percent", "meets_expectations", "description"],
        order_by="idx asc",
    )


def max_grade(course_schedule) -> float:
    """The top of the section's numeric scale, which every assignment and
    discussion grade is already expressed on."""
    value = (
        frappe.db.get_value("Course Schedule", course_schedule, "maxnumgrade")
        if course_schedule
        else None
    )
    return flt(value) or 100.0


def numeric_section(course_schedule) -> bool:
    """Rubrics stand down on competency and descriptive sections, where the
    gradebook cell holds a level rather than a score (decisions/095 §7)."""
    from seminary.seminary import cbe
    from seminary.seminary.api import narrative_section

    if not course_schedule:
        return True
    return not cbe.framework_for(course_schedule) and not narrative_section(
        course_schedule
    )


# --- submissions --------------------------------------------------------------


def _submission_context(doc):
    activity_doctype, activity_field, section_field = SUBMISSIONS[doc.doctype]
    activity = doc.get(activity_field)
    rubric = (
        frappe.db.get_value(activity_doctype, activity, "rubric") if activity else None
    )
    return activity_doctype, activity, doc.get(section_field), rubric


def _scores(submission_doctype, submission) -> list:
    return frappe.get_all(
        "Rubric Score",
        filters={"submission_doctype": submission_doctype, "submission": submission},
        fields=["name", "rubric", "criterion_code", "level", "percent", "comment"],
    )


def scored_rubric(doc):
    """The rubric this submission's scores were given on: the one already used
    if any (a new version must not re-grade old work), else the activity's."""
    if not doc.is_new():
        used = frappe.db.get_value(
            "Rubric Score",
            {"submission_doctype": doc.doctype, "submission": doc.name},
            "rubric",
        )
        if used:
            return used
    return _submission_context(doc)[3]


def computed_grade(doc):
    """The grade the rubric gives this submission, or None while any criterion
    is still without a level (or the submission is not graded by rubric)."""
    if doc.is_new() or doc.doctype not in SUBMISSIONS:
        return None
    _a, _b, section, _r = _submission_context(doc)
    rubric = scored_rubric(doc)
    if not rubric or not numeric_section(section):
        return None
    criteria = frappe.get_all(
        "Rubric Criterion",
        filters={"parent": rubric, "parenttype": "Rubric"},
        fields=["criterion_code", "weight"],
        order_by="idx asc",
    )
    by_code = {
        s.criterion_code: s
        for s in _scores(doc.doctype, doc.name)
        if s.rubric == rubric
    }
    if not criteria or any(c.criterion_code not in by_code for c in criteria):
        return None
    fraction = sum(
        share * flt(by_code[code].percent) / 100.0
        for code, share in shares(criteria).items()
    )
    return round(fraction * max_grade(section), 2)


def apply_grade(doc):
    """Called from both submissions' validate: once every criterion has a
    level the grade is derived, so a whole-document save from a grading page
    cannot drift from the rubric."""
    grade = computed_grade(doc)
    if grade is not None:
        doc.grade = grade


# --- editor -------------------------------------------------------------------


def _check_activity(activity_doctype, activity, ptype="read"):
    if ptype != "read":
        # Who before what: a student is refused before anything about the
        # activity is looked at.
        require_grader()
    if activity_doctype not in ACTIVITIES:
        frappe.throw(_("Rubrics are only for assignments and discussions."))
    frappe.has_permission(activity_doctype, ptype, activity, throw=True)


def is_locked(rubric) -> bool:
    return bool(rubric) and bool(frappe.db.exists("Rubric Score", {"rubric": rubric}))


def criterion_labels(activity_doctype, activity) -> dict:
    labels = {}
    for path in frappe.get_hooks("rubric_criterion_labels") or []:
        try:
            for code, items in (
                frappe.get_attr(path)(activity_doctype, activity) or {}
            ).items():
                labels.setdefault(code, []).extend(items or [])
        except Exception:
            frappe.log_error(title=f"rubric_criterion_labels: {path}")
    return labels


def rubric_payload(rubric) -> dict | None:
    if not rubric:
        return None
    doc = frappe.get_doc("Rubric", rubric)
    criteria = [c.as_dict() for c in doc.criteria]
    share = shares(criteria)
    return {
        "name": doc.name,
        "version": doc.version,
        "scale": doc.scale,
        "levels": scale_levels(doc.scale),
        "criteria": [
            {
                "criterion_code": c.criterion_code,
                "title": c.title,
                "description": c.description,
                "weight": c.weight or None,
                "share": round(share.get(c.criterion_code, 0) * 100, 1),
            }
            for c in doc.criteria
        ],
        "cells": [
            {
                "criterion_code": c.criterion_code,
                "level": c.level,
                "descriptor": c.descriptor,
            }
            for c in doc.cells
            if c.descriptor
        ],
        "labels": criterion_labels(doc.activity_doctype, doc.activity),
    }


@frappe.whitelist()
def get_editor(activity_doctype, activity):
    """What the activity page's rubric editor needs."""
    _check_activity(activity_doctype, activity, "write")
    rubric = frappe.db.get_value(activity_doctype, activity, "rubric")
    return {
        "rubric": rubric_payload(rubric),
        "locked": is_locked(rubric),
        "scales": [
            {**s, "levels": scale_levels(s.name)}
            for s in frappe.get_all(
                "Rubric Scale",
                filters={"enabled": 1},
                fields=["name", "is_default", "description"],
                order_by="is_default desc, name asc",
            )
        ],
        "can_manage_scales": frappe.has_permission("Rubric Scale", "create"),
    }


@frappe.whitelist()
def copy_candidates(activity_doctype, activity):
    """Current rubrics the instructor may start from, this course's first."""
    _check_activity(activity_doctype, activity, "write")
    course = frappe.db.get_value(activity_doctype, activity, "course")
    rows = []
    for dt, title_field in ACTIVITIES.items():
        for a in frappe.get_all(
            dt,
            filters={"rubric": ["is", "set"]},
            fields=["name", "rubric", "course", f"{title_field} as title"],
            limit=500,
        ):
            if dt == activity_doctype and a.name == activity:
                continue
            rows.append(
                {"rubric": a.rubric, "title": a.title, "course": a.course, "kind": dt}
            )
    rows.sort(key=lambda r: (r["course"] != course, (r["title"] or "").lower()))
    return rows


@frappe.whitelist()
def get_rubric(rubric):
    """One rubric's content, to fill the editor from (Copy from…)."""
    require_grader()
    frappe.has_permission("Rubric", "read", rubric, throw=True)
    return rubric_payload(rubric)


@frappe.whitelist()
def save_rubric(activity_doctype, activity, scale, criteria):
    """Create or edit the activity's rubric. A rubric someone was graded on
    is never edited: the save becomes a new version and earlier grades keep
    theirs (decisions/095 §4).

    ``criteria``: ``[{criterion_code, title, description, weight, cells:
    {level: descriptor}}]``. A criterion without a code gets one from its
    title; codes that come in are kept, so a new version stays comparable."""
    _check_activity(activity_doctype, activity, "write")
    criteria = frappe.parse_json(criteria) or []
    old = frappe.db.get_value(activity_doctype, activity, "rubric")

    if old and not is_locked(old):
        doc = frappe.get_doc("Rubric", old)
        doc.scale = scale
        doc.set("criteria", [])
        doc.set("cells", [])
    else:
        doc = frappe.new_doc("Rubric")
        doc.update(
            {
                "activity_doctype": activity_doctype,
                "activity": activity,
                "scale": scale,
                "version": (
                    (cint(frappe.db.get_value("Rubric", old, "version")) + 1)
                    if old
                    else 1
                ),
                "previous_version": old,
            }
        )
    used = {c.get("criterion_code") for c in criteria if c.get("criterion_code")}
    for c in criteria:
        code = c.get("criterion_code")
        if not code:
            base = code = slug(c.get("title"))
            n = 2
            while code in used:
                code, n = f"{base}-{n}", n + 1
            used.add(code)
        doc.append(
            "criteria",
            {
                "criterion_code": code,
                "title": c.get("title"),
                "description": c.get("description"),
                "weight": flt(c.get("weight")),
            },
        )
        for level, descriptor in (c.get("cells") or {}).items():
            if (descriptor or "").strip():
                doc.append(
                    "cells",
                    {"criterion_code": code, "level": level, "descriptor": descriptor},
                )
    doc.save()
    # Fired on an edit in place too (old == new): criteria may have gone that
    # another app had keyed on.
    _set_activity_rubric(activity_doctype, activity, old, doc.name)
    return get_editor(activity_doctype, activity)


@frappe.whitelist()
def remove_rubric(activity_doctype, activity):
    """Detach the rubric. An unused one is deleted; a used one stays for the
    grades it gave."""
    _check_activity(activity_doctype, activity, "write")
    old = frappe.db.get_value(activity_doctype, activity, "rubric")
    if not old:
        return
    _set_activity_rubric(activity_doctype, activity, old, None)
    if not is_locked(old):
        frappe.delete_doc("Rubric", old)


def _set_activity_rubric(activity_doctype, activity, old, new):
    if old != new:
        frappe.db.set_value(activity_doctype, activity, "rubric", new)
    for path in frappe.get_hooks("rubric_replaced") or []:
        frappe.get_attr(path)(activity_doctype, activity, old, new)


# --- grading ------------------------------------------------------------------


def _grading_doc(submission_doctype, submission):
    if submission_doctype not in SUBMISSIONS:
        frappe.throw(_("Rubrics are only for assignments and discussions."))
    doc = frappe.get_doc(submission_doctype, submission)
    return doc, _submission_context(doc)


@frappe.whitelist()
def get_grading(submission_doctype, submission):
    """The grading panel: inactive when the activity has no rubric or the
    section does not grade in numbers."""
    require_grader()
    doc, (activity_doctype, activity, section, _r) = _grading_doc(
        submission_doctype, submission
    )
    require_course_staff(section)
    rubric = scored_rubric(doc)
    if not rubric or not numeric_section(section):
        return {"active": False}
    return {
        "active": True,
        "rubric": rubric_payload(rubric),
        "scores": [
            s for s in _scores(submission_doctype, submission) if s.rubric == rubric
        ],
        "max_grade": max_grade(section),
        "grade": computed_grade(doc),
    }


@frappe.whitelist()
def save_scores(submission_doctype, submission, scores):
    """Upsert the grader's levels and comments, then re-save the submission so
    its grade (and from there the gradebook) follows."""
    require_grader()
    doc, (activity_doctype, activity, section, _r) = _grading_doc(
        submission_doctype, submission
    )
    require_course_staff(section)
    rubric = scored_rubric(doc)
    if not rubric:
        frappe.throw(_("This activity has no rubric."))
    existing = {
        s.criterion_code: s.name for s in _scores(submission_doctype, submission)
    }
    for row in frappe.parse_json(scores) or []:
        code, level = row.get("criterion_code"), row.get("level")
        name = existing.get(code)
        if not level:
            if name:
                frappe.delete_doc("Rubric Score", name, ignore_permissions=True)
            continue
        score = (
            frappe.get_doc("Rubric Score", name)
            if name
            else frappe.new_doc("Rubric Score")
        )
        score.update(
            {
                "submission_doctype": submission_doctype,
                "submission": submission,
                "rubric": rubric,
                "criterion_code": code,
                "level": level,
                "comment": row.get("comment"),
            }
        )
        score.save(ignore_permissions=True)

    doc.reload()
    grade = computed_grade(doc)
    if grade is not None:
        doc.grade = grade
        doc.status = "Graded"
        doc.save(ignore_permissions=True)
    for path in frappe.get_hooks("rubric_scored") or []:
        frappe.get_attr(path)(doc)
    return {"grade": grade, "status": doc.status}


@frappe.whitelist()
def get_student_view(activity_doctype, activity, submission=None):
    """The rubric as a student reads it before submitting, and their own
    levels once the work is graded."""
    _check_activity(activity_doctype, activity)
    rubric = frappe.db.get_value(activity_doctype, activity, "rubric")
    result = {"rubric": None, "scores": []}
    if submission:
        sub_doctype = next(
            dt for dt, (adt, _f, _s) in SUBMISSIONS.items() if adt == activity_doctype
        )
        doc = frappe.get_doc(sub_doctype, submission)
        own = doc.member == frappe.session.user
        section = _submission_context(doc)[2]
        if not own and not is_course_staff(section):
            frappe.throw(_("Not permitted"), frappe.PermissionError)
        if section and not numeric_section(section):
            return result
        rubric = scored_rubric(doc) or rubric
        if doc.status == "Graded":
            result["scores"] = [
                {
                    "criterion_code": s.criterion_code,
                    "level": s.level,
                    "comment": s.comment,
                }
                for s in _scores(sub_doctype, submission)
                if s.rubric == rubric
            ]
    result["rubric"] = rubric_payload(rubric)
    return result


# --- read API for other apps --------------------------------------------------


def criterion_scores(scheduled_assess_criteria) -> list:
    """Every graded rubric score on one assessment of one section:
    ``[{student, rubric, criterion_code, level, share, percent, meets_expectations_percent}]``.

    ``share`` is the criterion's part of its rubric (0-1); ``percent`` the
    level reached (0-100); ``meets_expectations_percent`` the percent of the
    scale's *meets expectations* level. Ungraded submissions are left out."""
    rows = frappe.get_all(
        "Rubric Score",
        filters={"assess_criteria": scheduled_assess_criteria},
        fields=[
            "submission_doctype",
            "submission",
            "student",
            "rubric",
            "criterion_code",
            "level",
            "percent",
        ],
    )
    graded = {}
    rubrics = {}
    out = []
    for r in rows:
        key = (r.submission_doctype, r.submission)
        if key not in graded:
            graded[key] = (
                frappe.db.get_value(r.submission_doctype, r.submission, "status")
                == "Graded"
            )
        if not graded[key]:
            continue
        if r.rubric not in rubrics:
            doc = frappe.get_doc("Rubric", r.rubric)
            meets = next(
                (lv.percent for lv in scale_levels(doc.scale) if lv.meets_expectations),
                None,
            )
            rubrics[r.rubric] = (shares([c.as_dict() for c in doc.criteria]), meets)
        share, meets = rubrics[r.rubric]
        out.append(
            {
                "student": r.student,
                "rubric": r.rubric,
                "criterion_code": r.criterion_code,
                "level": r.level,
                "share": share.get(r.criterion_code, 0.0),
                "percent": flt(r.percent),
                "meets_expectations_percent": flt(meets) if meets is not None else None,
            }
        )
    return out


def assessment_rubric(scheduled_assess_criteria):
    """The current rubric of the activity behind one assessment row, as a
    payload, or None."""
    sac = frappe.db.get_value(
        "Scheduled Course Assess Criteria",
        scheduled_assess_criteria,
        ["type", "assignment", "discussion"],
        as_dict=True,
    )
    if not sac:
        return None
    if sac.type == "Assignment" and sac.assignment:
        rubric = frappe.db.get_value("Assignment Activity", sac.assignment, "rubric")
    elif sac.type == "Discussion" and sac.discussion:
        rubric = frappe.db.get_value("Discussion Activity", sac.discussion, "rubric")
    else:
        return None
    return rubric_payload(rubric)
