# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Rubric Score (decisions/095 §5): one student's level on one criterion."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from seminary.seminary import rubrics


class RubricScore(Document):
    def validate(self):
        self.set_context()
        self.validate_level()
        self.validate_unique()

    def set_context(self):
        if self.submission_doctype not in rubrics.SUBMISSIONS:
            frappe.throw(_("Rubrics are only for assignments and discussions."))
        _a, _f, section_field = rubrics.SUBMISSIONS[self.submission_doctype]
        sub = frappe.db.get_value(
            self.submission_doctype,
            self.submission,
            ["student", section_field, "course_assess"],
            as_dict=True,
        )
        if not sub:
            frappe.throw(
                _("{0} {1} does not exist.").format(
                    _(self.submission_doctype), self.submission
                )
            )
        self.student = sub.student
        self.course_schedule = sub.get(section_field)
        self.assess_criteria = sub.course_assess
        if (
            self.is_new()
            or self.has_value_changed("level")
            or self.has_value_changed("comment")
        ):
            self.graded_by = frappe.session.user
            self.graded_on = now_datetime()

    def validate_level(self):
        rubric = frappe.get_doc("Rubric", self.rubric)
        if self.criterion_code not in {c.criterion_code for c in rubric.criteria}:
            frappe.throw(
                _("{0} is not a criterion of this rubric.").format(self.criterion_code)
            )
        level = next(
            (lv for lv in rubrics.scale_levels(rubric.scale) if lv.label == self.level),
            None,
        )
        if not level:
            frappe.throw(
                _("{0} is not a level of scale {1}.").format(self.level, rubric.scale)
            )
        self.percent = level.percent

    def validate_unique(self):
        if frappe.db.exists(
            "Rubric Score",
            {
                "submission_doctype": self.submission_doctype,
                "submission": self.submission,
                "criterion_code": self.criterion_code,
                "name": ["!=", self.name],
            },
        ):
            frappe.throw(_("This criterion already has a score on this submission."))
