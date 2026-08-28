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
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    if roles & {
        "Seminary Manager",
        "System Manager",
        "Program Chair",
        "Registrar",
        "Instructor",
    }:
        return ""
    student = frappe.db.get_value("Student", {"user": user}, "name")
    if not student:
        return "1=0"
    return f"""`tabCompetency Result`.student = {frappe.db.escape(student)}"""


def has_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    if roles & {
        "Seminary Manager",
        "System Manager",
        "Program Chair",
        "Registrar",
        "Instructor",
    }:
        return True
    student = frappe.db.get_value("Student", {"user": user}, "name")
    return bool(student) and doc.student == student
