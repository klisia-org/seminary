"""Give competency sections that predate ADR 079 their reflection lessons.

The outline's ad-hoc self-assessment prompts are gone; the reflection lessons
replace them, so a section created before them would otherwise leave its
students no way in. `cbe_reflection.scaffold` is idempotent: it adds a chapter
for any competency without one and the reflection lessons the framework asks
for, and stamps any reflection already present rather than duplicating it.
Closed and cancelled sections are left as they were.
"""

import frappe

from seminary.seminary import cbe, cbe_reflection


def execute():
    for cs in frappe.get_all(
        "Course Schedule",
        filters={"workflow_state": ("not in", ("Closed", "Cancelled"))},
        pluck="name",
    ):
        if not cbe.framework_for(cs):
            continue
        try:
            cbe_reflection.scaffold(cs)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"adr079_scaffold_reflection_lessons: {cs}"
            )
