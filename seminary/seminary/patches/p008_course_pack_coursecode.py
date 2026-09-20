# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Courses created by a Course Pack import before p008 F10 have no ``coursecode``
(mandatory and unique on Course; the importer inserted with ignore_mandatory and
never set it). Give each one a code derived from its name.

Existing Course Competency records named "-<code>" are deliberately NOT renamed:
they are Link targets of Course Schedule Assess Criteria, Competency Results, PDP
goals and chapters. New competencies get a proper prefix from the controller's
autoname. Idempotent."""

import frappe


def execute():
    if not frappe.db.has_column("Course", "coursecode"):
        return
    for name in frappe.get_all(
        "Course", filters={"coursecode": ["in", ["", None]]}, pluck="name"
    ):
        base = frappe.scrub(name).upper()[:60] or "COURSE"
        code, n = base, 2
        while frappe.db.exists("Course", {"coursecode": code}):
            code = f"{base}-{n}"
            n += 1
        frappe.db.set_value("Course", name, "coursecode", code, update_modified=False)
