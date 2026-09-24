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
            # A competency that lists no dimensions yet is graded whole, so an
            # empty vocabulary is not an error here -- only a wrong code is.
            if allowed:
                row.dimension = cbe.assert_known_dimension(
                    allowed, row.dimension_code, idx=row.idx
                )
            cbe.assert_unique_dimension(seen, row.dimension_code, row.idx)

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
    # A mentor's assessment reaches a student only once the framework says so
    # (ADR 079 decision 5), which a list condition cannot express; the student
    # reads those through the endpoints and `has_permission`, which apply it.
    return (
        f"""`tabCompetency Assessment`.student = {frappe.db.escape(student)} """
        """and `tabCompetency Assessment`.evaluator_kind = 'Self'"""
    )


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
    if not student or doc.student != student:
        return False
    if doc.evaluator_kind != "Mentor":
        return True
    from seminary.seminary import cbe

    return doc.status == "Submitted" and cbe.mentor_assessments_visible(
        doc.student, doc.course_schedule, doc.course_competency
    )
