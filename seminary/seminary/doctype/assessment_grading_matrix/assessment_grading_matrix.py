# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Assessment Grading Matrix (ADR 065 section 11b).

One cell of an assessment's grading grid: does this kind of evaluator judge this
dimension on this activity? Standalone rather than a child table because
`Scheduled Course Assess Criteria` is itself a child table and Frappe has no
grandchildren -- the same constraint that made Assessment Dimension Weight
standalone.
"""

import frappe
from frappe import _
from frappe.model.document import Document


class AssessmentGradingMatrix(Document):
    def validate(self):
        self.set_context()
        self.validate_dimension()
        self.validate_unique()

    def set_context(self):
        """Denormalise from the assessment, so a report can filter by section."""
        row = frappe.db.get_value(
            "Scheduled Course Assess Criteria",
            self.assess_criteria,
            ["parent", "course_competency"],
            as_dict=True,
        )
        if not row:
            frappe.throw(
                _("Assessment {0} does not exist.").format(self.assess_criteria)
            )
        self.course_schedule = row.parent
        self.course_competency = row.course_competency

    def validate_dimension(self):
        """The dimension must be one the section's scale defines."""
        scale = frappe.db.get_value(
            "Course Schedule", self.course_schedule, "gradesc_cs"
        )
        allowed = {
            d.dimension_code: d.dimension
            for d in frappe.get_all(
                "Grading Scale Dimensions",
                filters={"parent": scale},
                fields=["dimension_code", "dimension"],
            )
        }
        if self.dimension_code not in allowed:
            frappe.throw(
                _(
                    "{0} is not a dimension of grading scale {1}. Available: {2}."
                ).format(
                    self.dimension_code, scale, ", ".join(sorted(allowed)) or _("none")
                )
            )
        # Refreshed on every save so a renamed dimension leaves no stale label.
        self.dimension = allowed[self.dimension_code]

    def validate_unique(self):
        """One cell per assessment, evaluator type and dimension.

        Compared after the fact rather than filtered on `name != self.name`:
        autoname has already stamped a new doc, so that filter would exclude the
        very record being looked for and let the duplicate through.
        """
        duplicate = frappe.db.get_value(
            "Assessment Grading Matrix",
            {
                "assess_criteria": self.assess_criteria,
                "instructor_category": self.instructor_category,
                "dimension_code": self.dimension_code,
            },
            "name",
        )
        if duplicate and (self.is_new() or duplicate != self.name):
            frappe.throw(
                _("{0} already has a cell for {1} / {2} ({3}).").format(
                    self.assess_criteria,
                    self.instructor_category,
                    self.dimension_code,
                    duplicate,
                )
            )
