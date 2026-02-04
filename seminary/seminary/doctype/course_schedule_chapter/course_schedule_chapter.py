# Copyright (c) 2025, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from seminary.seminary.utils import get_course_progress


class CourseScheduleChapter(Document):
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
