# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Course Folder scopes (p006 F2, ADR §2.2a).

1. Every existing folder becomes a Course-scope folder (that is what every
   folder was: scoped to the catalogue Course).
2. Lesson folder blocks stored `{"folder": <foldername>}` and the API resolved
   the name site-wide. The block now carries `folder_ref` (the Course Folder
   docname); `folder` stays as the display label. Each block is resolved once by
   (foldername, the lesson's course) — never site-wide — and an unresolvable one
   is left as it is and logged.

There are no live schools, so this rewrites fixture data. Idempotent.
"""

import json

import frappe


def execute():
    if not frappe.db.has_column("Course Folder", "scope"):
        return
    frappe.db.sql(
        """
        UPDATE `tabCourse Folder`
        SET scope = 'Course'
        WHERE IFNULL(scope, '') = ''
        """
    )
    unresolved = _rewrite_lesson_blocks()
    if unresolved:
        frappe.log_error(
            title="course_folder_scopes: unresolved folder references",
            message="\n".join(unresolved),
        )
    frappe.db.commit()


def _rewrite_lesson_blocks():
    unresolved = []
    lessons = frappe.db.sql(
        """
        SELECT name, chapter, course_sc, content, instructor_content
        FROM `tabCourse Lesson`
        WHERE content LIKE %(needle)s OR instructor_content LIKE %(needle)s
        """,
        {"needle": '%"folder":%'},
        as_dict=True,
    )
    for lesson in lessons:
        course = _course_of_lesson(lesson)
        update = {}
        for field in ("content", "instructor_content"):
            rewritten, missing = _rewrite(lesson.get(field), course)
            if rewritten is not None:
                update[field] = rewritten
            for foldername in missing:
                unresolved.append(
                    f"{lesson.name}.{field}: '{foldername}' in course {course}"
                )
        if update:
            frappe.db.set_value(
                "Course Lesson", lesson.name, update, update_modified=False
            )
    return unresolved


def _course_of_lesson(lesson):
    cs = lesson.get("course_sc")
    if not cs and lesson.get("chapter"):
        cs = frappe.db.get_value("Course Schedule Chapter", lesson.chapter, "coursesc")
    if not cs:
        return None
    return frappe.db.get_value("Course Schedule", cs, "course")


def _rewrite(content, course):
    """Return (new_json_or_None, [unresolved foldernames])."""
    if not content:
        return None, []
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return None, []
    if not isinstance(data, dict) or not isinstance(data.get("blocks"), list):
        return None, []

    changed = False
    missing = []
    for block in data["blocks"]:
        if not isinstance(block, dict) or block.get("type") != "folder":
            continue
        bdata = block.get("data")
        if not isinstance(bdata, dict) or bdata.get("folder_ref"):
            continue
        foldername = bdata.get("folder")
        if not foldername:
            continue
        docname = None
        if course:
            docname = frappe.db.get_value(
                "Course Folder", {"foldername": foldername, "course": course}, "name"
            )
        if not docname:
            missing.append(foldername)
            continue
        bdata["folder_ref"] = docname
        changed = True
    if not changed:
        return None, missing
    return json.dumps(data), missing
