# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Point mentor-sourced evaluators at the cohort instead (ADR 066 section 5).

`Competency Framework Evaluator.assignment_source` loses `Program Enrollment
Mentor` and gains `Program Cohort`. Existing rows are moved across with
`cohort_type` left empty, which makes them **inert**: `cbe.cohort_evaluator_rows`
skips a row that names no type, so nobody is resolved as an evaluator or as a
note reader through it until a chair says which kind of cohort it means.

Narrowing is the only safe direction here. Guessing a cohort type would grant
grading rights and access to a student's development notes on the strength of an
inference, and this is precisely the access ADR 066 section 5 exists to stop
being granted by accident. A framework that goes quiet is visible on the next
grading screen; access silently handed to the wrong person is not.
"""

import frappe

OLD = "Program Enrollment Mentor"
NEW = "Program Cohort"


def execute():
    if not frappe.db.has_column("Competency Framework Evaluator", "assignment_source"):
        return
    rows = frappe.get_all(
        "Competency Framework Evaluator",
        filters={"assignment_source": OLD},
        fields=["name", "parent", "instructor_category"],
    )
    if not rows:
        return
    frappe.db.set_value(
        "Competency Framework Evaluator",
        {"assignment_source": OLD},
        {"assignment_source": NEW, "evaluates": ""},
        update_modified=False,
    )
    frappe.db.commit()
    for r in rows:
        print(
            "Competency Framework %s: evaluator %s now needs a Cohort Type before "
            "it grants anything." % (r.parent, r.instructor_category)
        )
