# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Competency Result (ADR 065): a student's standing on one competency.

Stores every stage of the section 6a pipeline -- the computed weighted average,
any override with its reason and author, and the rounded result -- so a verdict
can be explained after the fact rather than only asserted.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from seminary.seminary import cbe


class CompetencyResult(Document):
    def validate(self):
        cbe.stamp_override(self)
        cbe.recompute_finals(self)
        self.validate_unique()

    def validate_unique(self):
        duplicate = frappe.db.get_value(
            "Competency Result",
            {
                "student": self.student,
                "course_schedule": self.course_schedule,
                "course_competency": self.course_competency,
                "name": ("!=", self.name or ""),
            },
            "name",
        )
        if duplicate:
            frappe.throw(
                _(
                    "A result for this student and competency already exists ({0})."
                ).format(duplicate)
            )


def get_permission_query_conditions(user=None):
    from seminary.seminary import cbe

    user = user or frappe.session.user
    staff = cbe.staff_row_condition("Competency Result", user)
    if staff == "":
        return ""
    student = frappe.db.get_value("Student", {"user": user}, "name")
    if not student:
        return staff or "1=0"
    own = f"""`tabCompetency Result`.student = {frappe.db.escape(student)}"""
    return f"({staff} or {own})" if staff else own


def has_permission(doc, user=None, permission_type=None):
    from seminary.seminary import cbe

    user = user or frappe.session.user
    # The recorded result is the section's: a mentor reads it, course staff
    # change it (p012 decision 2).
    if cbe.staff_may_access(doc, user, permission_type, staff_only_write=True):
        return True
    student = frappe.db.get_value("Student", {"user": user}, "name")
    return bool(student) and doc.student == student
