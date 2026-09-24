# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Reflection lessons: where a competency section asks students to look back
(ADR 079 decisions 1-3).

A reflection is lesson content -- a `selfAssessment` or `developmentPlan`
EditorJS block inside a lesson -- and the Competency Framework, not the
instructor, decides where it sits. This module:

* recognises a reflection block in a lesson's content (`reflection_of`);
* scaffolds a section from its competencies: a chapter per competency and the
  reflection lessons the framework asks for (`scaffold`);
* keeps reflection lessons where the policy put them (`pin_chapter`), and
  refuses the edits that would contradict it (`assert_*`).

A block stores no competency: it resolves one from its lesson's chapter when it
renders, so it survives course packs and re-mapping. What a block does store is
its kind, its scope (this chapter's competency, or every competency in the
course) and, for a self-assessment, its stage.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint

from seminary.seminary import cbe

SELF = "selfAssessment"
PLAN = "developmentPlan"
REFLECTION_TYPES = (SELF, PLAN)

# Where each reflection sits in its chapter. A Baseline opens the course; the
# rest close their chapter, in this order when several share the last one.
LEADING = "leading"
_TRAILING_ORDER = {
    (SELF, "chapter", "Final"): 0,
    (SELF, "course", "Final"): 1,
    (PLAN, "course", None): 2,
}


# ---------------------------------------------------------------- recognising


def reflection_of(content):
    """The reflection block in a lesson's EditorJS content, as
    ``(kind, scope, stage)``, or None. A lesson holds at most one."""
    if not content:
        return None
    try:
        data = json.loads(content) if isinstance(content, str) else content
    except (TypeError, ValueError):
        return None
    for block in (data or {}).get("blocks") or []:
        if not isinstance(block, dict) or block.get("type") not in REFLECTION_TYPES:
            continue
        bdata = block.get("data") or {}
        if block["type"] == PLAN:
            return (PLAN, "course", None)
        return (
            SELF,
            "course" if bdata.get("scope") == "course" else "chapter",
            "Baseline" if bdata.get("stage") == "Baseline" else "Final",
        )
    return None


def _placement(reflection):
    if reflection == (SELF, "course", "Baseline"):
        return (LEADING, 0)
    return ("trailing", _TRAILING_ORDER.get(reflection, 0))


# ---------------------------------------------------------------- the policy


def required_reflections(framework):
    """What the framework asks for, as ``[(kind, scope, stage)]``.

    Every self-assessment tests `course_self_eval` first and the development
    plan tests `require_pdp`: Frappe keeps a dependent field's stored value
    after its parent Check is cleared, so the dependent value alone can claim
    what the framework no longer asks for (ADR 079 decision 1).
    """
    out = []
    if cint(framework.course_self_eval):
        points = framework.course_self_eval_points or ""
        if points.startswith("Start"):
            out.append((SELF, "course", "Baseline"))
        if points in cbe.END_OF_COMPETENCY_POINTS:
            out.append((SELF, "chapter", "Final"))
        elif "end" in points.lower():
            out.append((SELF, "course", "Final"))
    if cint(framework.require_pdp):
        out.append((PLAN, "course", None))
    return out


def _lesson_title(reflection, competency_name=None):
    kind, scope, stage = reflection
    if kind == PLAN:
        return _("My Development Plan")
    if stage == "Baseline":
        return _("Where I am starting")
    if scope == "chapter":
        return _("Reflect: {0}").format(competency_name)
    return _("Where I am now")


def _lesson_intro(reflection):
    kind, scope, stage = reflection
    if kind == PLAN:
        return _(
            "Before the course closes, set out what you will work on next and how."
        )
    if stage == "Baseline":
        return _(
            "Before you begin, say where you think you are on each competency "
            "of this course, and why."
        )
    if scope == "chapter":
        return _("Look back on this competency: where are you now, and what shows it?")
    return _("Look back on the whole course: where are you now on each competency?")


def _content(reflection):
    kind, scope, stage = reflection
    data = {} if kind == PLAN else {"scope": scope, "stage": stage}
    return json.dumps(
        {
            "blocks": [
                {"type": "paragraph", "data": {"text": _lesson_intro(reflection)}},
                {"type": kind, "data": data},
            ]
        }
    )


# ---------------------------------------------------------------- scaffolding


def scaffold(course_schedule):
    """Give a competency section its chapters and reflection lessons.

    Idempotent, so it serves every way a section gets its outline: creation,
    a course-pack import, a template import and the backfill of sections that
    predate ADR 079. A competency with no chapter gets one, appended to the
    outline; a reflection the framework asks for is created where missing,
    and one already present -- copied in by an import -- is stamped as
    governed rather than duplicated. Returns the number of lessons created.
    """
    framework = cbe.framework_doc(course_schedule)
    if not framework:
        return 0

    course = frappe.db.get_value("Course Schedule", course_schedule, "course")
    competencies = frappe.get_all(
        "Course Competency",
        filters={"course": course, "is_active": 1},
        fields=["name", "competency_name"],
        order_by="sequence asc",
    )
    mapped = {c.course_competency for c in cbe._mapped_chapters(course_schedule)}
    for c in competencies:
        if c.name not in mapped:
            _add_chapter(course_schedule, c)

    wanted = _wanted(course_schedule, framework, competencies)
    created = 0
    touched = set()
    for chapter, reflection, competency_name in wanted:
        if _stamp_existing(chapter.name, reflection):
            touched.add(chapter.name)
            continue
        _add_lesson(course_schedule, chapter.name, reflection, competency_name)
        touched.add(chapter.name)
        created += 1

    for name in touched:
        pin_chapter(name)
    return created


def _wanted(course_schedule, framework, competencies):
    """``[(chapter, reflection, competency_name)]``: where the framework puts
    each reflection in this section's outline as it stands."""
    chapters = cbe._mapped_chapters(course_schedule)
    if not chapters:
        return []
    names = {c.name: c.competency_name for c in competencies}
    wanted = []
    for reflection in required_reflections(framework):
        if reflection[1] == "chapter":
            wanted.extend(
                (ch, reflection, names.get(ch.course_competency))
                for ch in chapters
                if ch.course_competency in names
            )
        elif reflection[2] == "Baseline":
            wanted.append((chapters[0], reflection, None))
        else:
            wanted.append((chapters[-1], reflection, None))
    return wanted


def missing_reflections(course_schedule):
    """What the framework asks for that this section's outline lacks -- a
    competency with no chapter, or a reflection lesson not where it belongs.
    Nothing is written: the scaffold does not follow a policy changed after it
    was built, so this is how the gap is reported instead (ADR 079)."""
    framework = cbe.framework_doc(course_schedule)
    if not framework:
        return []
    course = frappe.db.get_value("Course Schedule", course_schedule, "course")
    competencies = frappe.get_all(
        "Course Competency",
        filters={"course": course, "is_active": 1},
        fields=["name", "competency_name"],
        order_by="sequence asc",
    )
    mapped = {c.course_competency for c in cbe._mapped_chapters(course_schedule)}
    missing = [
        _("a chapter for {0}").format(c.competency_name)
        for c in competencies
        if c.name not in mapped
    ]
    for chapter, reflection, competency_name in _wanted(
        course_schedule, framework, competencies
    ):
        if not any(
            reflection_of(frappe.db.get_value("Course Lesson", lesson, "content"))
            == reflection
            for lesson in _chapter_lessons(chapter.name)
        ):
            missing.append(_lesson_title(reflection, competency_name))
    return missing


def _add_chapter(course_schedule, competency):
    chapter = frappe.new_doc("Course Schedule Chapter")
    chapter.coursesc = course_schedule
    chapter.chapter_title = competency.competency_name
    chapter.course_competency = competency.name
    chapter.flags.ignore_permissions = True
    chapter.insert()
    idx = (
        frappe.db.count(
            "Course Schedule Chapter Reference",
            {"parent": course_schedule, "parenttype": "Course Schedule"},
        )
        + 1
    )
    frappe.get_doc(
        {
            "doctype": "Course Schedule Chapter Reference",
            "parent": course_schedule,
            "parenttype": "Course Schedule",
            "parentfield": "chapters",
            "idx": idx,
            "chapter": chapter.name,
        }
    ).insert(ignore_permissions=True)


def _chapter_lessons(chapter):
    return frappe.get_all(
        "Course Schedule Lesson Reference",
        filters={"parent": chapter, "parenttype": "Course Schedule Chapter"},
        fields=["lesson"],
        order_by="idx asc",
        pluck="lesson",
    )


def _stamp_existing(chapter, reflection):
    for lesson in _chapter_lessons(chapter):
        row = frappe.db.get_value(
            "Course Lesson", lesson, ["content", "autocreated"], as_dict=True
        )
        if row and reflection_of(row.content) == reflection:
            if not row.autocreated:
                frappe.db.set_value(
                    "Course Lesson", lesson, "autocreated", 1, update_modified=False
                )
            return True
    return False


def _add_lesson(course_schedule, chapter, reflection, competency_name):
    lesson = frappe.new_doc("Course Lesson")
    lesson.course_sc = course_schedule
    lesson.chapter = chapter
    lesson.lesson_title = _lesson_title(reflection, competency_name)
    lesson.content = _content(reflection)
    lesson.autocreated = 1
    lesson.flags.ignore_permissions = True
    lesson.insert()
    idx = len(_chapter_lessons(chapter)) + 1
    frappe.get_doc(
        {
            "doctype": "Course Schedule Lesson Reference",
            "parent": chapter,
            "parenttype": "Course Schedule Chapter",
            "parentfield": "lessons",
            "idx": idx,
            "lesson": lesson.name,
        }
    ).insert(ignore_permissions=True)


# ---------------------------------------------------------------- pinning


def pinned_order(lessons):
    """Reorder ``[(lesson, reflection-or-None)]`` so a Baseline opens and the
    closing reflections close, keeping every other lesson's relative order."""
    leading, middle, trailing = [], [], []
    for lesson, reflection in lessons:
        if not reflection:
            middle.append(lesson)
            continue
        side, rank = _placement(reflection)
        (leading if side == LEADING else trailing).append((rank, lesson))
    trailing.sort(key=lambda x: x[0])
    return [x[1] for x in leading] + middle + [x[1] for x in trailing]


def pin_rows(rows):
    """Reorder a chapter's lesson reference rows in place (from the chapter's
    own validate, so every save keeps reflection lessons where they belong).
    Only governed lessons are pinned."""
    governed = _governed({r.lesson for r in rows if r.lesson})
    order = pinned_order([(r.lesson, governed.get(r.lesson)) for r in rows])
    by_lesson = {r.lesson: r for r in rows}
    reordered = [by_lesson[name] for name in order]
    for idx, row in enumerate(reordered, start=1):
        row.idx = idx
    return reordered


def pin_chapter(chapter):
    """Re-pin a chapter whose rows were written without its validate running
    -- a direct child insert, as the lesson form and the importers do."""
    rows = frappe.get_all(
        "Course Schedule Lesson Reference",
        filters={"parent": chapter, "parenttype": "Course Schedule Chapter"},
        fields=["name", "lesson", "idx"],
        order_by="idx asc",
    )
    governed = _governed({r.lesson for r in rows if r.lesson})
    order = pinned_order([(r.lesson, governed.get(r.lesson)) for r in rows])
    by_lesson = {r.lesson: r for r in rows}
    for idx, lesson in enumerate(order, start=1):
        if by_lesson[lesson].idx != idx:
            frappe.db.set_value(
                "Course Schedule Lesson Reference",
                by_lesson[lesson].name,
                "idx",
                idx,
                update_modified=False,
            )


def on_lesson_reference_insert(doc, method=None):
    """doc_events hook: a lesson row inserted on its own lands after whatever
    is last -- which, in a chapter with a closing reflection, is the wrong side
    of it."""
    if doc.parenttype == "Course Schedule Chapter" and doc.parent:
        pin_chapter(doc.parent)


def _governed(lessons):
    if not lessons:
        return {}
    return {
        r.name: reflection_of(r.content)
        for r in frappe.get_all(
            "Course Lesson",
            filters={"name": ("in", list(lessons)), "autocreated": 1},
            fields=["name", "content"],
        )
    }


# ---------------------------------------------------------------- guards
#
# Every refusal names the reason and what the instructor can do instead
# (ADR 079 decisions 3 and 7).


def _governed_message():
    return _(
        "This is a reflection lesson placed by the course's Competency Framework, "
        "so it stays where the framework puts it. You can change its title and "
        "the text around the reflection."
    )


def assert_lesson_deletable(lesson):
    if frappe.db.get_value("Course Lesson", lesson, "autocreated"):
        frappe.throw(
            _governed_message() + " " + _("It cannot be deleted."),
            title=_("Reflection lesson"),
        )


def assert_lesson_movable(lesson):
    if frappe.db.get_value("Course Lesson", lesson, "autocreated"):
        frappe.throw(
            _governed_message() + " " + _("It cannot be moved."),
            title=_("Reflection lesson"),
        )


def assert_chapter_deletable(chapter):
    governed = [
        lesson
        for lesson in _chapter_lessons(chapter)
        if frappe.db.get_value("Course Lesson", lesson, "autocreated")
    ]
    if governed:
        frappe.throw(
            _(
                "This chapter holds reflection lessons placed by the course's "
                "Competency Framework, so it cannot be deleted. Rename it or add "
                "lessons to it instead."
            ),
            title=_("Reflection lesson"),
        )


def assert_block_kept(lesson_doc):
    """A governed lesson keeps its reflection block, unchanged in kind, scope
    and stage; everything around it is the instructor's."""
    if not lesson_doc.autocreated or lesson_doc.is_new():
        return
    before = lesson_doc.get_doc_before_save()
    if not before:
        return
    was = reflection_of(before.content)
    if was and reflection_of(lesson_doc.content) != was:
        frappe.throw(
            _governed_message()
            + " "
            + _("Its reflection block cannot be removed or replaced."),
            title=_("Reflection lesson"),
        )


def assert_not_unflagged(lesson_doc):
    """`autocreated` is set by the system only; nothing clears it."""
    if lesson_doc.is_new():
        return
    before = lesson_doc.get_doc_before_save()
    if before and before.autocreated and not lesson_doc.autocreated:
        lesson_doc.autocreated = 1


# ---------------------------------------------------------------- import


def untouched_scaffold(course_schedule):
    """Whether a section's outline is only its scaffold: every chapter delivers
    a competency and every lesson in it is a governed reflection lesson. Such an outline can give way to an imported
    template, which is then re-scaffolded, instead of refusing the import."""
    chapters = cbe._mapped_chapters(course_schedule)
    if any(not c.course_competency for c in chapters):
        return False
    for c in chapters:
        for lesson in _chapter_lessons(c.name):
            if not frappe.db.get_value("Course Lesson", lesson, "autocreated"):
                return False
    return True


def clear_scaffold(course_schedule):
    """Remove an untouched scaffold before a template takes its place."""
    for ref in frappe.get_all(
        "Course Schedule Chapter Reference",
        filters={"parent": course_schedule, "parenttype": "Course Schedule"},
        pluck="chapter",
    ):
        frappe.db.delete("Course Schedule Lesson Reference", {"parent": ref})
        frappe.db.delete("Course Lesson", {"chapter": ref})
        frappe.db.delete("Course Schedule Chapter", ref)
    frappe.db.delete(
        "Course Schedule Chapter Reference",
        {"parent": course_schedule, "parenttype": "Course Schedule"},
    )


# ---------------------------------------------------------------- status


def _competencies_in_scope(course_schedule, reflection, chapter_competency):
    if reflection[1] == "chapter":
        return [chapter_competency] if chapter_competency else []
    course = frappe.db.get_value("Course Schedule", course_schedule, "course")
    return frappe.get_all(
        "Course Competency",
        filters={"course": course, "is_active": 1},
        order_by="sequence asc",
        pluck="name",
    )


def _plan_status(course_schedule, student):
    roster = frappe.db.get_value(
        "Scheduled Course Roster", {"course_sc": course_schedule, "student": student}
    )
    if not roster:
        return None
    return frappe.db.get_value(
        "Personal Development Plan",
        {"roster": roster},
        ["status", "mentor_feedback"],
        as_dict=True,
    )


def reflection_status(course_schedule, student, reflection, chapter_competency=None):
    """Where one student stands on one reflection lesson.

    ``done`` completes the lesson (ADR 079 decision 4); ``mentor_feedback``
    lights the outline badge once a mentor's view is there to read -- the
    mentors' assessments where the framework lets the student see them, or the
    mentor's review of the plan; ``required`` marks a plan the course cannot
    close without.
    """
    kind, _scope, stage = reflection
    framework = cbe.framework_doc(course_schedule)
    if kind == PLAN:
        plan = _plan_status(course_schedule, student) if student else None
        status = plan.status if plan else None
        return {
            "done": status in ("Submitted", "Reviewed", "Accepted"),
            "mentor_feedback": bool(
                plan and (status in ("Reviewed", "Accepted") or plan.mentor_feedback)
            ),
            "required": bool(
                framework
                and cint(framework.require_pdp)
                and cint(framework.pdp_blocks_completion)
            ),
        }

    competencies = _competencies_in_scope(
        course_schedule, reflection, chapter_competency
    )
    done = (
        bool(competencies)
        and all(
            cbe._self_assessment_submitted(student, course_schedule, c, stage)
            for c in competencies
        )
        if student
        else False
    )
    feedback = False
    if student and stage == "Final":
        for c in competencies:
            if frappe.db.exists(
                "Competency Assessment",
                {
                    "student": student,
                    "course_schedule": course_schedule,
                    "course_competency": c,
                    "evaluator_kind": "Mentor",
                    "status": "Submitted",
                },
            ) and cbe.mentor_assessments_visible(
                student, course_schedule, c, framework
            ):
                feedback = True
                break
    return {"done": done, "mentor_feedback": feedback, "required": False}


def lesson_reflection(lesson):
    """``(reflection, chapter, chapter_competency, course_schedule)`` for a
    governed lesson, or None -- read from the stored lesson, never from what a
    page says the block is."""
    row = frappe.db.get_value(
        "Course Lesson", lesson, ["content", "chapter", "autocreated"], as_dict=True
    )
    if not row:
        return None
    reflection = reflection_of(row.content)
    if not reflection:
        return None
    chapter = frappe.db.get_value(
        "Course Schedule Chapter",
        row.chapter,
        ["name", "coursesc", "course_competency"],
        as_dict=True,
    )
    if not chapter:
        return None
    return reflection, chapter.name, chapter.course_competency, chapter.coursesc


def lesson_done(lesson, student):
    """Whether a reflection lesson is complete for this student; None when the
    lesson holds no reflection, so the caller's own rules apply."""
    found = lesson_reflection(lesson)
    if not found:
        return None
    reflection, _chapter, competency, course_schedule = found
    return reflection_status(course_schedule, student, reflection, competency)["done"]


def final_lesson_for(course_schedule, competency):
    """The lesson holding a competency's closing self-assessment -- what a
    locked chapter links to, since it is what unlocks it."""
    for chapter in cbe._mapped_chapters(course_schedule):
        if chapter.course_competency != competency:
            continue
        for lesson in _chapter_lessons(chapter.name):
            content = frappe.db.get_value("Course Lesson", lesson, "content")
            if reflection_of(content) == (SELF, "chapter", "Final"):
                return lesson
    return None
