# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Grade passback, bounded (privatedocs p009 §2.12).

**A SCORM score is a claim, not an assessment.** It is produced by third-party
code running in a browser the student controls: the launcher's CMI model is by
construction reachable from the package's own page, so a student with a console
can set `score.raw` to anything a commit will accept. Bounds-checking (§2.9)
makes that claim well-formed; it does not make it true.

So the score lands on the `SCORM Attempt`, where staff can see it, and reaches
the gradebook **only** through an explicit link an instructor sets --
`Course Lesson.scorm_assessment_criteria`. Unmapped, which is the default,
a package records completion and nothing else.

Four rules govern the write, and each exists for a reason found in the code it
has to live beside:

1. **Competency sections stand down.** `quizresult_to_card` already does this:
   on a CBE section the same cell holds a *level* (1-4) written by
   `cbe.rollup_activity_grades`, and a percentage written there would be read
   back as a level. ADR 065 owns that cell.
2. **An instructor's number wins, permanently.** A cell is ours to write while
   it is ungraded, or while it still holds the value we last wrote. The moment a
   grader changes it by hand, later attempts stand down and stay down.
3. **The cell says where the number came from.** `scorm_reported_card` is what a
   grader sees, and it is also how rule 2 knows the cell is still ours.
4. **Only a finished, passing attempt reports.** An incomplete SCO has no score
   worth carrying.
"""

from __future__ import annotations

import frappe

#: What a completion has to look like before a score is worth reporting.
REPORTING_COMPLETION = {"completed"}
REPORTING_SUCCESS = {"passed"}


def percentage_for(attempt) -> float | None:
    """The attempt's score as a percentage, or None if it has none.

    **`has_score`, not `is not None`.** The score columns are Floats, so they
    are NOT NULL: an attempt loaded from the database reports `score_scaled ==
    0.0` whether the package set it to zero or never mentioned it. Reading that
    as a scaled zero turned a second commit of 90/100 into a grade of 0 --
    caught by the test that commits twice, and invisible to every test that
    commits once, because a *fresh* document really does hold None. This is the
    same trap `Course Assess Results Detail.graded_card` exists for, and the
    same answer: a companion flag that says the number is real.

    `score.scaled` is authoritative where a 2004 package sets it -- it is
    defined as -1..1 and needs no range -- so a non-zero scaled wins. Otherwise
    the raw score is normalised against the range the package declared,
    defaulting to 0..100, which is the convention `quizresult_to_card` already
    receives from a submission. The one case the two cannot be told apart is a
    package reporting `scaled` of exactly 0 alongside a different raw, which is
    both pathological and unreachable here: §2.12 reports only on a passing
    attempt.
    """
    if not attempt.get("has_score"):
        return None

    if attempt.score_scaled:
        return max(0.0, min(100.0, float(attempt.score_scaled) * 100.0))

    if attempt.score_raw is None:
        return None

    low = float(attempt.score_min) if attempt.score_min is not None else 0.0
    high = float(attempt.score_max) if attempt.score_max is not None else 100.0
    if high <= low:
        # The package contradicted itself; its range tells us nothing.
        low, high = 0.0, 100.0
    return max(
        0.0, min(100.0, ((float(attempt.score_raw) - low) / (high - low)) * 100.0)
    )


def push_from_attempt(attempt, lesson: str | None) -> dict:
    """Report `attempt`'s score to its mapped criterion, if all four rules hold.

    Returns a small dict rather than raising: a refusal here must never fail the
    commit that triggered it. A package whose grade does not propagate has still
    recorded its completion, and the reason is in the result.
    """
    if not lesson:
        return {"reported": False, "reason": "no lesson"}

    criteria = frappe.db.get_value("Course Lesson", lesson, "scorm_assessment_criteria")
    if not criteria:
        # The default, and the whole point of §2.12.
        return {"reported": False, "reason": "not mapped"}

    if (attempt.completion_status or "") not in REPORTING_COMPLETION and (
        attempt.success_status or ""
    ) not in REPORTING_SUCCESS:
        return {"reported": False, "reason": "not finished"}

    percentage = percentage_for(attempt)
    if percentage is None:
        return {"reported": False, "reason": "no score"}

    from seminary.seminary import cbe

    if cbe.framework_for(attempt.course):
        # The cell holds a level, not a percentage (ADR 065 §7). Writing one
        # here would be read back as the other.
        return {"reported": False, "reason": "competency section"}

    student = (
        frappe.db.get_value("Scheduled Course Roster", attempt.student, "student")
        if attempt.student
        else None
    )
    if not student:
        return {"reported": False, "reason": "no roster row"}

    card_name = frappe.db.get_value(
        "Course Assess Results Detail",
        {"assessment_criteria": criteria, "student_card": student},
        "name",
    )
    if not card_name:
        # The same condition `quizresult_to_card` logs: a criterion with no cell
        # for this student means the gradebook was never built for them.
        frappe.log_error(
            f"No Course Assess Results Detail for criterion {criteria} and student "
            f"{student} (SCORM attempt {attempt.name}). Score not propagated.",
            "scorm grades: missing CARD row",
        )
        return {"reported": False, "reason": "no gradebook cell"}

    card = frappe.get_doc("Course Assess Results Detail", card_name)

    if not _ours(card, attempt):
        return {"reported": False, "reason": "a grader owns this cell"}

    card.rawscore_card = percentage
    card.graded_card = 1
    card.scorm_reported_card = 1
    card.save(ignore_permissions=True)

    attempt.db_set("pushed_score", percentage, update_modified=False)
    return {"reported": True, "percentage": percentage, "criteria": criteria}


def _ours(card, attempt) -> bool:
    """May this attempt write this cell?

    Yes while nothing has graded it, and yes while it still holds the number we
    put there. Once a grader has changed it the cell is theirs -- for good, not
    until the next commit, which is why the comparison is against what *we* last
    wrote rather than against whether the flag happens to be set.
    """
    if not card.graded_card:
        return True
    if not card.scorm_reported_card:
        return False
    if attempt.pushed_score is None:
        # Flagged as ours but we have no record of writing it: a re-imported
        # gradebook, or a row copied from elsewhere. Do not assume.
        return False
    return abs(float(card.rawscore_card or 0) - float(attempt.pushed_score)) < 0.001


# ---------------------------------------------------------------- the mapping
#
# §2.12 sketched this link as living on the chapter. It lives on the lesson,
# because the ADL Golf sample settles the question: four content SCOs and one
# quiz SCO under a single chapter, so a chapter-level link would force a rollup
# across five SCOs that nobody specified. Mapping the SCO that *is* the
# assessment needs no aggregation -- and for a single-SCO package the chapter
# and its one lesson are the same thing, so §2.12 remains true where it was
# written.


@frappe.whitelist()
def criteria_for_lesson(lesson: str) -> dict:
    """The criteria a SCORM lesson could report to, and the one it does.

    Staff-only, and scoped to the lesson's own section: the list a picker can
    show is exactly the list `set_criteria` will accept.
    """
    row = _lesson_context(lesson)

    from seminary.seminary import cbe

    return {
        "lesson": lesson,
        "course": row.course,
        "current": row.scorm_assessment_criteria,
        # A competency section is told plainly rather than shown a picker that
        # would silently never fire (rule 1 in this module's docstring).
        "competency_section": bool(cbe.framework_for(row.course)),
        "criteria": frappe.get_all(
            "Scheduled Course Assess Criteria",
            filters={"parent": row.course, "parenttype": "Course Schedule"},
            fields=["name", "title", "assesscriteria_scac", "weight_scac", "type"],
            order_by="idx asc",
        ),
    }


@frappe.whitelist()
def set_criteria(lesson: str, criteria: str | None = None) -> dict:
    """Map this SCORM lesson's score to `criteria`, or clear the mapping.

    Two checks, and the second is the one that matters: the criterion must
    belong to **this lesson's own section**. Without it an instructor of one
    section could name a criterion of another and write into a gradebook they
    have no business in -- the link is a write capability, so it is scoped the
    same way every other course write is.
    """
    row = _lesson_context(lesson)

    criteria = (criteria or "").strip() or None
    if criteria:
        owner = frappe.db.get_value(
            "Scheduled Course Assess Criteria",
            criteria,
            ["parent", "parenttype"],
            as_dict=True,
        )
        if not owner or owner.parenttype != "Course Schedule":
            frappe.throw(
                frappe._("No such assessment criterion."), frappe.DoesNotExistError
            )
        if owner.parent != row.course:
            from seminary.seminary import security_log

            security_log.record_denial(
                "scorm_criteria_scope", lesson=lesson, course=row.course
            )
            frappe.throw(
                frappe._("That criterion belongs to a different section."),
                frappe.PermissionError,
            )

    frappe.db.set_value("Course Lesson", lesson, "scorm_assessment_criteria", criteria)
    return {"ok": True, "lesson": lesson, "current": criteria}


def _lesson_context(lesson: str):
    """Resolve the lesson and gate on its section. Both endpoints enter here.

    **The permission check comes before every other refusal, and a lesson that
    does not resolve is refused the same way one in someone else's section is.**
    Answering "no such lesson" to a caller who would not have been allowed to
    see it either way turns the endpoint into a way to probe which lessons
    exist -- the same disclosure p008 F11 closed on `applicant_payment`.

    Only once the caller is established as this section's staff does the
    lesson's *kind* matter. A mapping on a lesson that is not a SCO is a promise
    the gradebook cannot keep, because no commit will ever reach it.
    """
    from seminary.seminary.guards import require_course_staff

    row = frappe.db.get_value(
        "Course Lesson",
        lesson,
        ["name", "chapter", "scorm_sco_identifier", "scorm_assessment_criteria"],
        as_dict=True,
    )
    course = (
        frappe.db.get_value("Course Schedule Chapter", row.chapter, "coursesc")
        if row and row.chapter
        else None
    )
    if not course:
        frappe.throw(frappe._("Not permitted."), frappe.PermissionError)

    require_course_staff(course, include_registrar=True)

    if not row.scorm_sco_identifier:
        frappe.throw(
            frappe._("This lesson is not part of a SCORM package."),
            frappe.DoesNotExistError,
        )
    row.course = course
    return row
