# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs


class QuizSubmission(Document):
    def validate(self):
        from seminary.seminary.utils import backfill_submission_course_if_missing

        # A standalone quiz is taken for some other record (e.g. Aretenic document training) rather
        # than a Course Schedule; skip the LMS course wiring for it. See decisions/026.
        self.standalone = frappe.db.get_value("Quiz", self.quiz, "standalone") or 0
        if not self.standalone:
            backfill_submission_course_if_missing(self)
        self.validate_if_max_attempts_exceeded()
        self.validate_points()
        self.set_percentage()
        self.populate()
        self.validate_context()

    def validate_context(self):
        # mandatory_depends_on is client-side only in this Frappe version, so enforce the
        # course requirement here too (server-authoritative). See decisions/026.
        #
        # A standalone quiz is not bound to a Course Schedule. Its context (e.g. aretenic's
        # Document Distribution Registry) is owned and validated by the consuming app via its
        # own doc_events hook, so seminary stays independent and installable without aretenic.
        if self.standalone:
            return

        # course is seminary's non-standalone context. course_assess is NOT required: it's
        # derived in populate() from the SCAC linking this quiz to the course, and legitimately
        # stays empty when no such SCAC exists. Requiring it regressed normal submissions.
        if not self.get("course"):
            frappe.throw(
                _("Missing mandatory fields: {0}").format("course"),
                frappe.MandatoryError,
            )

    def on_update(self):
        self.notify_member()

    def validate_if_max_attempts_exceeded(self):
        max_attempts = frappe.db.get_value("Quiz", self.quiz, ["max_attempts"])
        if not max_attempts:
            return

        # Seminary counts attempts per quiz + member. A consuming app that reuses one standalone
        # quiz across many records (e.g. aretenic, scoped per Document Distribution Registry)
        # owns its own per-context attempt limiting so seminary stays independent of it.
        filters = {"quiz": self.quiz, "member": frappe.session.user}
        current_user_submission_count = frappe.db.count(self.doctype, filters=filters)
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
            if flt(row.points) > flt(row.points_out_of):
                frappe.throw(
                    _(
                        "Points for question number {0} cannot be greater than the points allotted for that question."
                    )
                )
            else:
                self.score += flt(row.points)
        self.score = flt(self.score, 2)

    def set_percentage(self):
        if self.score and self.score_out_of:
            self.percentage = (self.score / self.score_out_of) * 100

    def populate(self):
        self.submission_date = frappe.utils.now_datetime()
        if self.standalone:
            return  # no Course Schedule / gradebook wiring for standalone quizzes
        self.student = frappe.db.get_value("Student", {"user": self.member})
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
