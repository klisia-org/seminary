# Copyright (c) 2025, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from seminary.seminary.utils import get_course_progress


class CourseScheduleChapter(Document):
    def validate(self):
        self.validate_course_competency()

    def validate_course_competency(self):
        """A chapter may only deliver a competency of its own course (ADR 065).

        The link has no declarative filter because the eligible set depends on
        this chapter's course, so the guard has to be here: a mismatched
        competency would otherwise silently break the self-assessment timing and
        content gating that read this mapping.
        """
        if not self.course_competency:
            return
        competency_course = frappe.db.get_value(
            "Course Competency", self.course_competency, "course"
        )
        chapter_course = self.course_title or frappe.db.get_value(
            "Course Schedule", self.coursesc, "course"
        )
        if chapter_course and competency_course != chapter_course:
            frappe.throw(
                _(
                    "Competency {0} belongs to course {1}, but this chapter is in "
                    "course {2}."
                ).format(self.course_competency, competency_course, chapter_course)
            )

        # One chapter per competency per section. Gating resolves a competency
        # back to "the chapter that delivers it" (cbe._chapter_for_competency),
        # and with two candidates it would pick one arbitrarily and lock the
        # other for reasons nobody could explain. Compared after the fact rather
        # than filtered on `name != self.name`, because autoname has already
        # stamped a new doc with its name.
        duplicate = frappe.db.get_value(
            "Course Schedule Chapter",
            {"coursesc": self.coursesc, "course_competency": self.course_competency},
            "name",
        )
        if duplicate and (self.is_new() or duplicate != self.name):
            frappe.throw(
                _(
                    "Competency {0} is already delivered by chapter {1} in this "
                    "section. A competency belongs to one chapter."
                ).format(self.course_competency, duplicate)
            )

    def on_update(self):
        self.recalculate_course_progress()

    def recalculate_course_progress(self):
        previous_lessons = (
            self.get_doc_before_save() and self.get_doc_before_save().as_dict().lessons
        )
        current_lessons = self.lessons

        if previous_lessons and previous_lessons != current_lessons:
            enrolled_members = frappe.get_all(
                "Scheduled Course Roster",
                {"course_sc": self.coursesc},
                ["student", "name"],
            )
            for enrollment in enrolled_members:
                new_progress = get_course_progress(self.coursesc, enrollment.member)
                frappe.db.set_value(
                    "Scheduled Course Roster", enrollment.name, "progress", new_progress
                )
