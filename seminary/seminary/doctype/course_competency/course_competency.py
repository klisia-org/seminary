# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Course Competency (ADR 065): a competency a course develops.

Course = outcome; the competencies inside it are what students demonstrate.
Standalone rather than a child table on Course because assessment criteria,
per-evaluator grades, competency results and development-plan goals all Link to
a specific competency, and a Link cannot target a child row.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from seminary.seminary.utils import assert_url_safe_code


class CourseCompetency(Document):
    def validate(self):
        self.validate_code()
        self.validate_dimensions()

    def validate_code(self):
        assert_url_safe_code(self.competency_code, _("Competency Code"))
        # Compare after the fact rather than filtering on `name != self.name`:
        # autoname has already stamped a new doc with the colliding name, so that
        # filter would exclude the very record being looked for and let the
        # duplicate through to a raw database error.
        duplicate = frappe.db.get_value(
            "Course Competency",
            {"course": self.course, "competency_code": self.competency_code},
            "name",
        )
        if duplicate and (self.is_new() or duplicate != self.name):
            frappe.throw(
                _(
                    "Course {0} already has a competency with the code {1} ({2})."
                ).format(self.course, self.competency_code, duplicate)
            )

    def validate_dimensions(self):
        """Dimensions must come from the course's own grading scale.

        The scale is the single vocabulary for dimensions (ADR 065 section 1);
        letting a competency invent one would produce a descriptor no assessment
        can ever be recorded against.
        """
        scale = frappe.db.get_value("Course", self.course, "default_grading_scale")
        allowed = {}
        if scale:
            allowed = {
                d.dimension_code: d.dimension
                for d in frappe.get_all(
                    "Grading Scale Dimensions",
                    filters={"parent": scale},
                    fields=["dimension_code", "dimension"],
                )
            }

        if not allowed:
            if self.dimensions:
                frappe.throw(
                    _(
                        "Grading Scale {0} on course {1} defines no dimensions, so "
                        "this competency cannot describe how it is demonstrated. Add "
                        "dimensions to the scale first."
                    ).format(scale or _("(none)"), self.course)
                )
            return

        seen = {}
        for row in self.dimensions:
            if row.dimension_code not in allowed:
                frappe.throw(
                    _(
                        "Row {0}: {1} is not a dimension of grading scale {2}. "
                        "Available: {3}."
                    ).format(
                        row.idx,
                        row.dimension_code,
                        scale,
                        ", ".join(sorted(allowed)),
                    )
                )
            if row.dimension_code in seen:
                frappe.throw(
                    _("Dimension {0} appears in rows {1} and {2}.").format(
                        row.dimension_code, seen[row.dimension_code], row.idx
                    )
                )
            seen[row.dimension_code] = row.idx
            # Denormalised label, refreshed on every save so a renamed dimension
            # does not leave stale text on the competency.
            row.dimension = allowed[row.dimension_code]


@frappe.whitelist()
def get_course_dimensions(course):
    """Dimensions available to a competency, read off the course's grading scale.

    Used by the Desk form to offer the dimension codes rather than making the
    author copy them from the scale.
    """
    scale = frappe.db.get_value("Course", course, "default_grading_scale")
    if not scale:
        return []
    return frappe.get_all(
        "Grading Scale Dimensions",
        filters={"parent": scale},
        fields=["dimension_code", "dimension", "description"],
        order_by="sequence asc, idx asc",
    )
