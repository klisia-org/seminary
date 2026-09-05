# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Assessment Dimension Weight (ADR 065): what an activity measures.

Standalone rather than a child table on Scheduled Course Assess Criteria for the
same reason Course Competency is standalone: the assessment criteria row is
already a child of Course Schedule, and Frappe has no grandchild tables.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from seminary.seminary import cbe


class AssessmentDimensionWeight(Document):
    def validate(self):
        self.set_context()
        self.validate_dimension()
        self.validate_unique()

    def set_context(self):
        row = frappe.db.get_value(
            "Scheduled Course Assess Criteria",
            self.assess_criteria,
            ["parent", "course_competency"],
            as_dict=True,
        )
        if row:
            self.course_schedule = row.parent
            self.course_competency = row.course_competency

    def validate_dimension(self):
        if not self.course_competency:
            frappe.throw(
                _(
                    "Assessment {0} is not linked to a competency, so it has no "
                    "dimensions to weight."
                ).format(self.assess_criteria)
            )
        allowed = {
            d.dimension_code: d.dimension
            for d in cbe.dimensions_of(self.course_competency)
        }
        if self.dimension_code not in allowed:
            frappe.throw(
                _("{0} is not a dimension of competency {1}. Available: {2}.").format(
                    self.dimension_code,
                    self.course_competency,
                    ", ".join(sorted(allowed)) or _("(none)"),
                )
            )
        self.dimension = allowed[self.dimension_code]

    def validate_unique(self):
        # Compared after the fact rather than filtered on `name != self.name`:
        # autoname has already stamped a new doc with the colliding name, so
        # that filter would hide the very record being looked for.
        duplicate = frappe.db.get_value(
            "Assessment Dimension Weight",
            {
                "assess_criteria": self.assess_criteria,
                "dimension_code": self.dimension_code,
            },
            "name",
        )
        if duplicate and (self.is_new() or duplicate != self.name):
            frappe.throw(
                _("This assessment already has a weight for {0} ({1}).").format(
                    self.dimension_code, duplicate
                )
            )
