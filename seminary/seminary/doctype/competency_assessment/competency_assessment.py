# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Competency Assessment (ADR 065): one person's verdict on one competency.

Baseline self-assessment, final self-assessment and each mentor's final
assessment all share this shape, which is what makes the radar a single query
rather than three.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from seminary.seminary import cbe


class CompetencyAssessment(Document):
    def validate(self):
        self.set_context()
        self.validate_ratings()
        self.validate_unique()
        self.stamp_submission()

    def set_context(self):
        if self.evaluator_kind == "Self":
            self.instructor = None
            self.instructor_category = None
        elif self.instructor and not self.instructor_category:
            self.instructor_category = frappe.db.get_value(
                "Course Schedule Instructors",
                {"parent": self.course_schedule, "instructor": self.instructor},
                "instructor_category",
            )

    def validate_ratings(self):
        scale = cbe.scale_for(self.course_schedule)
        allowed = {
            d.dimension_code: d.dimension
            for d in cbe.dimensions_of(self.course_competency)
        }
        seen = {}
        for row in self.ratings or []:
            if allowed and row.dimension_code not in allowed:
                frappe.throw(
                    _("Row {0}: {1} is not a dimension of this competency.").format(
                        row.idx, row.dimension_code
                    )
                )
            if row.dimension_code in seen:
                frappe.throw(
                    _("Dimension {0} appears in rows {1} and {2}.").format(
                        row.dimension_code, seen[row.dimension_code], row.idx
                    )
                )
            seen[row.dimension_code] = row.idx
            row.dimension = allowed.get(row.dimension_code, row.dimension)

            value = cbe.level_value(scale, row.level_code) if scale else None
            if value is None:
                frappe.throw(
                    _("Row {0}: {1} is not a level on grading scale {2}.").format(
                        row.idx, row.level_code, scale or _("(none)")
                    )
                )
            row.level_value = value

        if self.status == "Submitted" and not self.ratings:
            frappe.throw(_("Rate every dimension before submitting this assessment."))

    def validate_unique(self):
        """One assessment per author, per competency, per stage.

        Without this a mentor could submit twice and have both counted, which
        would silently double their weight in the verdict.
        """
        filters = {
            "student": self.student,
            "course_schedule": self.course_schedule,
            "course_competency": self.course_competency,
            "stage": self.stage,
            "evaluator_kind": self.evaluator_kind,
            "name": ("!=", self.name or ""),
        }
        if self.evaluator_kind == "Mentor":
            filters["instructor"] = self.instructor
        duplicate = frappe.db.get_value("Competency Assessment", filters, "name")
        if duplicate:
            frappe.throw(
                _("A {0} assessment for this competency already exists ({1}).").format(
                    self.stage.lower(), duplicate
                )
            )

    def stamp_submission(self):
        if self.status == "Submitted" and not self.submitted_on:
            self.submitted_on = now_datetime()


def get_permission_query_conditions(user=None):
    """Students see only their own assessments.

    These carry a student's own words about their formation; the list view must
    not become a way to read a classmate's.
    """
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
    return f"""`tabCompetency Assessment`.student = {frappe.db.escape(student)}"""


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
