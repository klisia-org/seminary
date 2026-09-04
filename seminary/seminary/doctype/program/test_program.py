# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
"""Program test helpers.

The original Frappe LMS tests here were commented out wholesale when Topic and
Article were retired (see the `retire_article_and_course_topic` patch) and
`Program.program_code` became `program_abbreviation`. What was lost with them
was `make_program_and_linked_courses`, which `test_student` and
`test_program_enrollment` still import — so the whole app's test suite failed at
collection, not at any assertion.

The helpers are restored here in their current shape. The Topic/Article
scaffolding is not: those doctypes no longer exist, and a helper that builds
records the app has retired would be worse than none.
"""

import frappe


def make_course(name):
    """A Course, with the fields the doctype actually requires today."""
    if frappe.db.exists("Course", name):
        return name
    scale = frappe.db.get_value("Grading Scale", {}, "name")
    course = frappe.get_doc(
        {
            "doctype": "Course",
            "course_name": name,
            "coursecode": name.replace(" ", "-")[:20],
            "default_grading_scale": scale,
            "description": "_test description",
        }
    ).insert(ignore_permissions=True)
    return course.name


def make_program(name):
    program = frappe.get_doc(
        {
            "doctype": "Program",
            "program_name": name,
            # `program_code` was replaced by `program_abbreviation`; the field
            # is mandatory, so a helper that omits it cannot insert.
            "program_abbreviation": "".join(w[0] for w in name.split() if w)[:10]
            or "TP",
            "description": "_test description",
        }
    ).insert(ignore_permissions=True)
    return program.name


def make_program_and_linked_courses(program_name, course_name_list):
    """Get-or-create a Program and attach the named courses to it."""
    if frappe.db.exists("Program", program_name):
        program = frappe.get_doc("Program", program_name)
    else:
        make_program(program_name)
        program = frappe.get_doc("Program", program_name)

    existing = {row.course for row in program.courses}
    for course_name in course_name_list:
        course = make_course(course_name)
        if course not in existing:
            program.append("courses", {"course": course, "required": 1})
    program.save(ignore_permissions=True)
    return program
