# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Activity Competency Grade (ADR 065): one evaluator's level on one activity.

Activities are graded by mentors only. Self-assessment is competency-scoped and
lives in Competency Assessment, so there is deliberately no evaluator_kind here
-- a "Self" value would be a state no framework configuration can produce.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from seminary.seminary import cbe


class ActivityCompetencyGrade(Document):
    def validate(self):
        self.set_context()
        self.validate_level()
        self.validate_evaluator()
        self.validate_unique()

    def set_context(self):
        roster = frappe.db.get_value(
            "Scheduled Course Roster",
            self.roster,
            ["student", "course_sc"],
            as_dict=True,
        )
        if roster:
            self.student = roster.student
            self.course_schedule = roster.course_sc
        self.course_competency = frappe.db.get_value(
            "Scheduled Course Assess Criteria",
            self.assess_criteria,
            "course_competency",
        )
        if self.instructor and not self.instructor_category:
            self.instructor_category = frappe.db.get_value(
                "Course Schedule Instructors",
                {"parent": self.course_schedule, "instructor": self.instructor},
                "instructor_category",
            )
        if not self.graded_on:
            self.graded_on = now_datetime()

    def validate_level(self):
        scale = cbe.scale_for(self.course_schedule)
        value = cbe.level_value(scale, self.level_code) if scale else None
        if value is None:
            codes = [r.grade_code for r in cbe.levels_for(scale)] if scale else []
            frappe.throw(
                _("{0} is not a level on grading scale {1}. Available: {2}.").format(
                    self.level_code,
                    scale or _("(none)"),
                    ", ".join(codes) or _("(none)"),
                )
            )
        self.level_value = value

    def validate_evaluator(self):
        """Only someone the framework recognises for this student may grade.

        Resolution already knows who that is; checking it here is what stops a
        grade being recorded by a mentor who was never assigned, which would
        then quietly count toward a competency verdict.
        """
        allowed = {
            e["instructor"]
            for e in cbe.evaluators_for(self.roster)
            if e["grades_activities"]
        }
        if not allowed:
            return
        if self.instructor not in allowed:
            frappe.throw(
                _(
                    "{0} is not an evaluator for this student in this section. "
                    "Assign them as a course instructor or as the student's mentor "
                    "first."
                ).format(self.instructor)
            )

    def validate_unique(self):
        # A blank dimension is stored as NULL by some paths and "" by others, and
        # SQL equality matches neither against the other -- so the whole-activity
        # case has to be matched explicitly or a duplicate slips through.
        dimension_filter = (
            self.dimension_code if self.dimension_code else ("in", ["", None])
        )
        duplicate = frappe.db.get_value(
            "Activity Competency Grade",
            {
                "roster": self.roster,
                "assess_criteria": self.assess_criteria,
                "instructor": self.instructor,
                "dimension_code": dimension_filter,
                "name": ("!=", self.name or ""),
            },
            "name",
        )
        if duplicate:
            frappe.throw(
                _(
                    "{0} has already graded this activity for this student ({1})."
                ).format(self.instructor, duplicate)
            )
