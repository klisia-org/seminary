# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Competency Framework (ADR 065): the policy layer for competency-based education.

A framework holds the choices schools genuinely disagree about — who evaluates,
when students assess themselves, whether mentor ratings are averaged or summed,
whether the student's own rating counts — so those choices stay configuration
rather than branches in the grading engine.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

# Evaluator rows resolved from the section carry the same person for everyone in
# it; rows resolved from the student's enrollment differ per student. The label
# is stored on the row so the grid states the difference without the reader
# having to know how resolution works.
EVALUATES_LABELS = {
    "Course Schedule Instructors": "Every student in the section",
    "Program Enrollment Mentor": "Only their assigned students",
}


class CompetencyFramework(Document):
    def validate(self):
        self.validate_grading_scale()
        self.validate_evaluators()
        self.validate_development_questions()
        self.set_report_max()

    def validate_development_questions(self):
        """Question keys are the join between four years of separate plans.

        The text may be reworded freely; the key may not, because it is what
        lets a student read every answer they have given to the same prompt
        across every course. Uniqueness is therefore enforced here rather than
        left to convention (ADR 065 section 8).
        """
        from seminary.seminary.utils import assert_url_safe_code

        seen = {}
        for row in self.development_questions or []:
            assert_url_safe_code(row.question_key, _("Question Key"))
            if row.question_key in seen:
                frappe.throw(
                    _("Question key {0} appears in rows {1} and {2}.").format(
                        row.question_key, seen[row.question_key], row.idx
                    )
                )
            seen[row.question_key] = row.idx

    def validate_grading_scale(self):
        scale_type = frappe.db.get_value(
            "Grading Scale", self.grading_scale, "grscale_type"
        )
        if scale_type != "Competency-based education":
            frappe.throw(
                _(
                    "Grading Scale {0} is a {1} scale. A competency framework needs a "
                    "Competency-based education scale, which is what defines its "
                    "proficiency levels and dimensions."
                ).format(self.grading_scale, scale_type or _("different kind of"))
            )

    def validate_evaluators(self):
        seen = {}
        for row in self.evaluators or []:
            # Derived, not user-entered: keep it in step with assignment_source on
            # every save so an edited row cannot keep a stale label.
            row.evaluates = EVALUATES_LABELS.get(row.assignment_source, "")

            key = (row.instructor_category, row.assignment_source)
            if key in seen:
                frappe.throw(
                    _(
                        "{0} appears twice with the same assignment source "
                        "(rows {1} and {2})."
                    ).format(row.instructor_category, seen[key], row.idx)
                )
            seen[key] = row.idx

            if not (row.grades_activities or row.gives_competency_verdict):
                frappe.throw(
                    _(
                        "Row {0}: {1} does nothing. An evaluator must grade "
                        "activities, give a competency verdict, or both."
                    ).format(row.idx, row.instructor_category)
                )

        if self.status == "Active" and not self.evaluators:
            frappe.throw(_("An active framework needs at least one evaluator."))

        if self.aggregation_method == "Instructor of record decides" and not any(
            frappe.db.get_value(
                "Instructor Category",
                row.instructor_category,
                "is_instructor_of_record",
            )
            for row in self.evaluators or []
        ):
            frappe.throw(
                _(
                    "No evaluator is an instructor of record, so nobody can decide "
                    "the verdict. Mark one Instructor Category as instructor of "
                    "record, or choose another aggregation method."
                )
            )

    def set_report_max(self):
        """Highest value a reported result can reach, for display and for the
        portal's scale labels.

        On the framework scale a result is one level, so the maximum is the top
        level. Summed, it is the top level times the number of ratings actually
        being added up — which is what makes a 1-4 scale report as 1-12 for three
        contributors.
        """
        top = frappe.get_all(
            "Grading Scale Interval",
            filters={"parent": self.grading_scale},
            fields=["threshold"],
            order_by="threshold desc",
            limit=1,
        )
        top_level = flt(top[0].threshold) if top else 0
        if self.report_basis == "Summed":
            contributors = sum(
                1 for row in self.evaluators or [] if row.gives_competency_verdict
            )
            if self.include_self_in_verdict and self.course_self_eval:
                contributors += 1
            self.report_max = flt(top_level) * max(contributors, 1)
        else:
            self.report_max = flt(top_level)
