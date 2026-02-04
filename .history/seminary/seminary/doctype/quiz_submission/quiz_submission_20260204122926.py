# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.model.document import Document


class QuizSubmission(Document):
    def validate(self):
        self.validate_if_max_attempts_exceeded()
        self.validate_points()
        self.set_percentage()
        self.populate()

    def on_update(self):
        self.notify_member()

    def validate_if_max_attempts_exceeded(self):
        max_attempts = frappe.db.get_value("Quiz", self.quiz, ["max_attempts"])
        if max_attempts == 0:
            return

        current_user_submission_count = frappe.db.count(
            self.doctype, filters={"quiz": self.quiz, "member": frappe.session.user}
        )
        if current_user_submission_count >= max_attempts:
            frappe.throw(
                _(
                    "You have exceeded the maximum number of attempts ({0}) for this quiz"
                ).format(max_attempts),
                MaximumAttemptsExceededError,
            )

    def validate_points(self):
        self.score = 0
        for row in self.result:
            if cint(row.points) > cint(row.points_out_of):
                frappe.throw(
                    _(
                        "Points for question number {0} cannot be greater than the points allotted for that question."
                    )
                )
            else:
                self.score += cint(row.points)

    def set_percentage(self):
        if self.score and self.score_out_of:
            self.percentage = (self.score / self.score_out_of) * 100

    def populate(self):
        self.student = frappe.db.get_value("Student", {"user": self.member})
        self.submission_date = frappe.utils.now_datetime()
        self.course_assess = frappe.db.get_value(
            "Scheduled Course Assess Criteria",
            {"quiz": self.quiz, "parent": self.course},
            "name",
        )
        self.extra_credit = frappe.db.get_value(
            "Scheduled Course Assess Criteria",
            {"quiz": self.quiz, "parent": self.course},
            "extracredit_scac",
        )

    def notify_member(self):
        if self.score != 0 and self.has_value_changed("score"):
            notification = frappe._dict(
                {
                    "subject": _("You have got a score of {0} for the quiz {1}").format(
                        self.score, self.quiz_title
                    ),
                    "email_content": _(
                        "There has been an update on your submission. You have got a score of {0} for the quiz {1}"
                    ).format(self.score, self.quiz_title),
                    "document_type": self.doctype,
                    "document_name": self.name,
                    "for_user": self.member,
                    "from_user": "Administrator",
                    "type": "Alert",
                    "link": "",
                }
            )

            make_notification_logs(notification, [self.member])


class MaximumAttemptsExceededError(frappe.DuplicateEntryError):
    pass
