# Copyright (c) 2025, Klisia, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class DiscussionSubmission(Document):
    def validate(self):
        from seminary.seminary.utils import backfill_submission_course_if_missing

        backfill_submission_course_if_missing(self)
        self.populate()
        self.sync_percentage_from_grade()

    def sync_percentage_from_grade(self):
        """Mirror grade → percentage so quizresult_to_card can propagate the
        score to the gradebook. The Assignment Submission UI only sets `grade`
        but the bridge to Course Assess Results Detail reads `percentage`
        (kept consistent with Exam/Quiz/Discussion submissions, which
        compute percentage on their own)."""
        if self.grade is not None:
            self.percentage = self.grade

    def populate(self):
        if self.student is None and self.member:
            self.student = frappe.db.get_value("Student", {"user": self.member})
        if self.student_name is None and self.student:
            self.student_name = frappe.db.get_value(
                "Student", self.student, "student_name"
            )
        self.course_assess = frappe.db.get_value(
            "Scheduled Course Assess Criteria",
            {"discussion": self.disc_activity, "parent": self.coursesc},
            "name",
        )
        self.extra_credit = frappe.db.get_value(
            "Scheduled Course Assess Criteria",
            {"discussion": self.disc_activity, "parent": self.coursesc},
            "extracredit_scac",
        )
