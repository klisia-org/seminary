# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""The manifest's SCOs become the chapter's lessons (privatedocs p009 §2.10).

This is the decision that keeps p009 small. A SCORM chapter already had a
lesson-shaped slot -- `api.add_lesson` created one placeholder per chapter --
and the entire progress model hangs off lessons: `Course Schedule Progress` is
keyed `(lesson, chapter, course, member)`, `save_progress` writes it, and
`get_course_progress` counts them. So one Course Lesson per SCO buys chapter and
course rollup, the ADR 065 competency mapping, gating, and the outline's
navigation with **no new code** -- and a single-SCO package, which is the
overwhelming majority, is exactly the one-lesson chapter that existed before.

**A lesson is never deleted here.** Deleting one takes its Course Schedule
Progress rows with it, and no instructor's re-upload may silently erase a
cohort's recorded work. A SCO that disappears from a replacement package marks
its lesson `scorm_orphaned`; staff remove it deliberately, with the usual
warning.
"""

from __future__ import annotations

import frappe


def reconcile(package, chapter_name: str) -> dict:
    """Bring `chapter_name`'s lessons in line with `package`'s SCOs.

    Runs after a successful unpack and after a dedup adoption -- a chapter that
    adopts an already-unpacked package needs its lessons just as much as the one
    that caused the unpack.
    """
    chapter = frappe.db.get_value(
        "Course Schedule Chapter",
        chapter_name,
        ["name", "coursesc", "chapter_title"],
        as_dict=True,
    )
    if not chapter:
        return {"added": 0, "kept": 0, "orphaned": 0}

    existing = frappe.get_all(
        "Course Lesson",
        filters={"chapter": chapter_name},
        fields=["name", "lesson_title", "scorm_sco_identifier", "scorm_orphaned"],
        order_by="creation asc",
    )
    by_identifier = {
        row.scorm_sco_identifier: row for row in existing if row.scorm_sco_identifier
    }

    # The placeholder `upsert_chapter` used to create carries no SCO identifier.
    # Where a chapter holds exactly one such lesson and nothing else, it is that
    # placeholder: claim it for the first SCO rather than leaving a stray beside
    # the real ones. Any other identifier-less lesson is someone's own content
    # and is left alone.
    unclaimed = [row for row in existing if not row.scorm_sco_identifier]
    placeholder = unclaimed[0] if len(existing) == 1 and unclaimed else None

    added = kept = 0
    ordered: list[str] = []

    for item in sorted(package.items, key=lambda i: i.idx):
        identifier = item.sco_identifier
        row = by_identifier.get(identifier)

        if row is None and placeholder is not None:
            row = placeholder
            placeholder = None
            frappe.db.set_value(
                "Course Lesson", row.name, "scorm_sco_identifier", identifier
            )

        if row is None:
            ordered.append(_create_lesson(chapter, item, identifier))
            added += 1
            continue

        update = {}
        if item.title and row.lesson_title != item.title:
            update["lesson_title"] = item.title
        if row.scorm_orphaned:
            # The SCO is back: a re-upload that restores it restores the lesson,
            # with its progress rows intact, which is the whole reason nothing
            # was deleted.
            update["scorm_orphaned"] = 0
        if update:
            frappe.db.set_value("Course Lesson", row.name, update)
        ordered.append(row.name)
        kept += 1

    live = {item.sco_identifier for item in package.items}
    orphaned = 0
    for row in existing:
        if row.scorm_sco_identifier and row.scorm_sco_identifier not in live:
            if not row.scorm_orphaned:
                frappe.db.set_value("Course Lesson", row.name, "scorm_orphaned", 1)
            orphaned += 1
            ordered.append(row.name)

    _reorder(chapter_name, ordered, existing)
    return {"added": added, "kept": kept, "orphaned": orphaned}


def _create_lesson(chapter, item, identifier: str) -> str:
    lesson = frappe.new_doc("Course Lesson")
    lesson.update(
        {
            "lesson_title": item.title or identifier,
            "chapter": chapter.name,
            "course_sc": chapter.coursesc,
            "scorm_sco_identifier": identifier,
        }
    )
    lesson.flags.ignore_permissions = True
    lesson.insert()
    return lesson.name


def _reorder(chapter_name: str, ordered: list[str], existing) -> None:
    """Put the chapter's lesson references in manifest order, orphans last.

    Written as direct child rows rather than through a chapter save, the way the
    template importer does it: saving the chapter runs `recalculate_course_progress`
    for every enrolled member, which is a great deal of work to reorder a list.
    """
    rows = {
        r.lesson: r.name
        for r in frappe.get_all(
            "Course Schedule Lesson Reference",
            filters={"parent": chapter_name, "parenttype": "Course Schedule Chapter"},
            fields=["name", "lesson"],
        )
    }

    for idx, lesson in enumerate(ordered, start=1):
        if lesson in rows:
            frappe.db.set_value(
                "Course Schedule Lesson Reference",
                rows[lesson],
                "idx",
                idx,
                update_modified=False,
            )
            continue
        reference = frappe.get_doc(
            {
                "doctype": "Course Schedule Lesson Reference",
                "parent": chapter_name,
                "parenttype": "Course Schedule Chapter",
                "parentfield": "lessons",
                "idx": idx,
                "lesson": lesson,
            }
        )
        reference.flags.ignore_permissions = True
        reference.insert()


# --------------------------------------------------------------- progress


#: What a SCO's reported state means for the lesson that carries it (§2.10).
#: `failed` is *progress*, not completion: the student did the work.
def status_for(completion: str | None, success: str | None) -> str | None:
    completion = (completion or "unknown").lower()
    success = (success or "unknown").lower()

    if completion == "completed" or success == "passed":
        return "Complete"
    if success == "failed" or completion == "incomplete":
        return "Partially Complete"
    return None


def record_progress(lesson: str, chapter: str, course: str, status: str | None) -> None:
    """Write a SCO's state onto its lesson, through the app's own writer.

    Completion goes through `save_progress` rather than around it: that function
    already owns the roster `db_set` p008 fixed (a Student may not `save()` a
    roster row), already refreshes the course percentage, and is the one place
    that decides a lesson is done. One completion writer, not two.

    A partial state has no path through it -- `save_progress` only ever writes
    `Complete` -- so it is upserted here, and **never downgrades an existing
    completion**. A student who finished, reopened the package and had it report
    `incomplete` on the way in must not lose what they had.
    """
    if not status or not (lesson and chapter and course):
        return

    from seminary.seminary.doctype.course_lesson.course_lesson import save_progress

    if status == "Complete":
        save_progress(lesson, chapter, course)
        return

    existing = frappe.db.get_value(
        "Course Schedule Progress",
        {"lesson": lesson, "member": frappe.session.user},
        ["name", "status"],
        as_dict=True,
    )
    if existing and existing.status == "Complete":
        return

    if existing:
        if existing.status != status:
            frappe.db.set_value(
                "Course Schedule Progress", existing.name, "status", status
            )
    else:
        frappe.get_doc(
            {
                "doctype": "Course Schedule Progress",
                "lesson": lesson,
                "chapter": chapter,
                "course": course,
                "status": status,
                "member": frappe.session.user,
            }
        ).save(ignore_permissions=True)

    # The bookmark half of `save_progress`, which a partial state wants just as
    # much: "where was I" is exactly what an unfinished SCO is recording.
    membership = frappe.db.exists(
        "Scheduled Course Roster",
        {"course_sc": course, "stuemail_rc": frappe.session.user},
    )
    if membership:
        frappe.db.set_value(
            "Scheduled Course Roster", membership, "current_lesson", lesson
        )
