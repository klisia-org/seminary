# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""A student's current and projected grade in a section (privatedocs p015 §3).

One algorithm, on the server, so *My Status* and the instructors' Students tab
always agree. The portal's "Simulate Grades" mode reruns ``current`` in the
browser on edited scores; keep CourseStatus.vue's ``gradeFromScores`` in step
with this file.

- **Current:** every regular assessment counts, a missing score as zero, each
  times its weight; extra-credit points are added; divided by the maximum grade.
- **Projected:** the same, but an assessment with no score yet counts at the
  unweighted average of the student's scored regular assessments. None until
  at least one regular assessment has a score.
- **Descriptive scales** (decisions/096a section 4): both are the weighted mean
  of the graded rows that count, in grade points, as Send Grades works it out
  (ADR 072); an ungraded row leaves the mean rather than counting as 0.
- **Weights** are the student's own (decisions/096): ``effective_weight`` where
  a row carries it, and a dropped or excused row (``weight_status``) does not
  count at all, not even toward the average.
"""

import math

import frappe
from frappe.utils import flt


def _score(value):
    # A raw score of 0 means "no score yet" on a results card.
    value = flt(value)
    return value if value > 0 else None


def _round2(value):
    """Math.round(value * 100) / 100, as the portal did it (half up, not
    banker's rounding)."""
    return math.floor(value * 100 + 0.5) / 100


def _interval(score, intervals):
    for row in sorted(intervals, key=lambda r: flt(r.get("threshold")), reverse=True):
        if score >= flt(row.get("threshold")):
            return row.get("grade_code") or "", row.get("grade_pass") or ""
    return "", ""


def _result(total, max_grade, intervals):
    score = total / max_grade
    grade, grade_pass = _interval(score, intervals)
    return {
        "score": _round2(score),
        "max_grade": max_grade,
        "grade": grade,
        "grade_pass": grade_pass,
    }


def _weight(a):
    if "effective_weight" in a:
        return flt(a.get("effective_weight"))
    return flt(a.get("weight_scac"))


def _descriptive(regular, max_grade, intervals):
    graded = [a for a in regular if a.get("graded_card") and _weight(a) > 0]
    weight = sum(_weight(a) for a in graded)
    if not weight:
        return {"current": None, "projected": None}
    mean = sum(flt(a.get("rawscore_card")) * _weight(a) for a in graded) / weight
    grade, grade_pass = _interval(mean, intervals)
    result = {
        "score": _round2(mean),
        "max_grade": max_grade,
        "grade": grade,
        "grade_pass": grade_pass,
    }
    return {"current": result, "projected": dict(result)}


def compute(assessments, intervals, max_grade, descriptive=False):
    """``{"current": {...} | None, "projected": {...} | None}`` from the
    section's assessment rows (``rawscore_card``, ``actualextrapt_card``,
    ``weight_scac``, ``extracredit_scac``, and ``graded_card`` on a
    Descriptive scale) and its grading scale intervals."""
    max_grade = flt(max_grade) or 100
    if not assessments or intervals is None:
        return {"current": None, "projected": None}

    regular = [
        a
        for a in assessments
        if not a.get("extracredit_scac") and not a.get("weight_status")
    ]
    if descriptive:
        return _descriptive(regular, max_grade, intervals)
    extra = sum(
        flt(a.get("actualextrapt_card"))
        for a in assessments
        if a.get("extracredit_scac")
    )

    current = sum(flt(a.get("rawscore_card")) * _weight(a) for a in regular)
    out = {"current": _result(current + extra, max_grade, intervals), "projected": None}

    scored = [_score(a.get("rawscore_card")) for a in regular]
    scored = [s for s in scored if s is not None]
    if scored:
        average = sum(scored) / len(scored)
        projected = sum(
            (_score(a.get("rawscore_card")) or average) * _weight(a) for a in regular
        )
        out["projected"] = _result(projected + extra, max_grade, intervals)
    return out


def section_scale(course_schedule):
    """(max grade, grading scale intervals) of a section."""
    cs = frappe.db.get_value(
        "Course Schedule", course_schedule, ["gradesc_cs", "maxnumgrade"], as_dict=True
    )
    if not cs:
        return 100, []
    intervals = (
        frappe.get_all(
            "Grading Scale Interval",
            fields=["grade_code", "threshold", "grade_pass"],
            filters={"parent": cs.gradesc_cs},
            order_by="threshold desc",
        )
        if cs.gradesc_cs
        else []
    )
    return flt(cs.maxnumgrade) or 100, intervals


def is_descriptive(course_schedule):
    scale = frappe.db.get_value("Course Schedule", course_schedule, "gradesc_cs")
    return bool(scale) and (
        frappe.db.get_value("Grading Scale", scale, "grscale_type") == "Descriptive"
    )


def section_assessments(course_schedule, rosters):
    """{roster name: [assessment rows]}: every assessment of the section, each
    with that roster's card values (None where it has no card) and its own
    weight (decisions/096)."""
    from seminary.seminary.gradebook_weights import for_rosters

    if not rosters:
        return {}
    weights = for_rosters(course_schedule, rosters)
    criteria = frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": course_schedule},
        fields=["name", "weight_scac", "extracredit_scac"],
        order_by="idx asc",
    )
    cards = {}
    for c in frappe.get_all(
        "Course Assess Results Detail",
        filters={"parent": ("in", list(rosters))},
        fields=[
            "parent",
            "assessment_criteria",
            "rawscore_card",
            "actualextrapt_card",
            "graded_card",
        ],
    ):
        cards[(c.parent, c.assessment_criteria)] = c
    out = {}
    for roster in rosters:
        rows = []
        for crit in criteria:
            card = cards.get((roster, crit.name)) or {}
            w = (weights.get(roster) or {}).get(crit.name) or {}
            rows.append(
                {
                    "assessment_criteria": crit.name,
                    "weight_scac": crit.weight_scac,
                    "extracredit_scac": crit.extracredit_scac,
                    "rawscore_card": card.get("rawscore_card"),
                    "actualextrapt_card": card.get("actualextrapt_card"),
                    "graded_card": card.get("graded_card"),
                    "effective_weight": w.get("weight", crit.weight_scac),
                    "weight_status": w.get("status"),
                }
            )
        out[roster] = rows
    return out


def course_grade_projection(course_schedule, student):
    """Current and projected grade of one student (a Student name) in a
    section. Callers check access; this reads."""
    roster = frappe.db.get_value(
        "Scheduled Course Roster",
        {"course_sc": course_schedule, "student": student},
        "name",
    )
    if not roster:
        return {"current": None, "projected": None}
    max_grade, intervals = section_scale(course_schedule)
    rows = section_assessments(course_schedule, [roster]).get(roster)
    return compute(rows, intervals, max_grade, is_descriptive(course_schedule))


def course_grades(course_schedule, rosters):
    """{roster name: {score, max_grade, grade, grade_pass, final} | None}: the
    course grade the gradebook and the Desk roster show (decisions/096a). The
    current grade until grades are sent; the stored result once they are, or
    once the student is failed for absences. None on a competency section."""
    from seminary.seminary import cbe

    if not rosters or cbe.framework_for(course_schedule):
        return {}
    max_grade, intervals = section_scale(course_schedule)
    descriptive = is_descriptive(course_schedule)
    stored = {
        r.name: r
        for r in frappe.get_all(
            "Scheduled Course Roster",
            filters={"name": ("in", list(rosters))},
            fields=[
                "name",
                "active",
                "failed_for_absence",
                "fscore",
                "fgrade",
                "fgradepass",
            ],
        )
    }
    live = [n for n, r in stored.items() if r.active and not r.failed_for_absence]
    rows = section_assessments(course_schedule, live)
    out = {}
    for name, r in stored.items():
        if name in rows:
            out[name] = compute(rows[name], intervals, max_grade, descriptive)[
                "current"
            ]
            if out[name]:
                out[name]["final"] = 0
        elif r.fgrade:
            out[name] = {
                "score": _round2(flt(r.fscore)),
                "max_grade": max_grade,
                "grade": r.fgrade,
                "grade_pass": r.fgradepass or "",
                "final": 1,
            }
        else:
            out[name] = None
    return out
