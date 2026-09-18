# Copyright (c) 2025, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from seminary.seminary.api import sanitize_html
from frappe import _
from frappe.utils import sanitize_html as _frappe_sanitize_html
from seminary.seminary.guards import is_grader, require_grader
import re


class ExamSubmission(Document):
    def validate(self):
        from seminary.seminary.utils import backfill_submission_course_if_missing

        backfill_submission_course_if_missing(self)

    def before_save(self):
        # Pre-populate empty comments from standard_comments / explanation
        for row in self.result:
            if not row.comments and row.question:
                eq = frappe.db.get_value(
                    "Exam Question",
                    row.question,
                    ["standard_comments", "question"],
                    as_dict=True,
                )
                if eq:
                    row.comments = (
                        eq.standard_comments
                        or frappe.db.get_value(
                            "Open Question", eq.question, "explanation"
                        )
                        or ""
                    )

        if not self.is_new() and self.has_value_changed("result"):
            timestamp = frappe.utils.now_datetime()
            user = frappe.session.user

            log_entry = f"\n--- [{timestamp}] {user} ---\n"
            for row in self.result:
                question_label = (
                    frappe.get_value("Exam Question", row.question, "question_detail")
                    or row.question
                    or ""
                )
                # Strip HTML tags for readability
                clean_question = re.sub("<[^<]+?>", "", question_label).strip()[:80]
                clean_answer = re.sub("<[^<]+?>", "", row.answer or "").strip()

                log_entry += f"Q: {clean_question}\nA: {clean_answer}\n\n"

            self.answer_log = (self.answer_log or "") + log_entry


def _clean_rich_text(value):
    """p006 F13: grader-authored comments are rendered as HTML in the
    student's view, so sanitise them on the way in (nh3 allow-list, always)."""
    if not value:
        return value
    return _frappe_sanitize_html(value, always_sanitize=True)


def _assert_may_take_exam(course_schedule):
    """p006 F7: a student may draft an exam only for a course they are
    enrolled in; graders may act on any."""
    from seminary.seminary.utils import user_is_enrolled_in_course

    if is_grader():
        return
    catalogue_course = (
        frappe.get_value("Course Schedule", course_schedule, "course")
        if course_schedule
        else None
    )
    if not user_is_enrolled_in_course(catalogue_course):
        frappe.throw(_("You are not enrolled in this course."), frappe.PermissionError)


def _assert_owns_submission(doc):
    """p006 F7: student-owned writers require the owner (or a grader)."""
    if doc.member != frappe.session.user and not is_grader():
        frappe.throw(
            _("You can only act on your own exam submission."),
            frappe.PermissionError,
        )


@frappe.whitelist()
def save_exam_comment(submission_name, row_name, comments):
    """Save a single question comment on an Exam Submission."""
    require_grader()
    frappe.db.set_value(
        "Exam Question Result", row_name, "comments", _clean_rich_text(comments)
    )


@frappe.whitelist()
def save_exam_grade(submission_name, status, score, percentage, fudge_points, result):
    """Save instructor grading for an Exam Submission."""
    require_grader()
    result = frappe.parse_json(result)
    doc = frappe.get_doc("Exam Submission", submission_name)

    doc.status = status
    doc.score = score
    doc.percentage = percentage
    doc.fudge_points = fudge_points

    for row_data in result:
        for row in doc.result:
            if row.name == row_data.get("name"):
                row.points = row_data.get("points")
                row.graded = row_data.get("graded")
                row.comments = _clean_rich_text(row_data.get("comments")) or ""
                break

    doc.flags.ignore_permissions = True
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return doc


@frappe.whitelist()
def save_exam_draft(exam, course, member, answers, time_taken, submission_name=None):
    """Save or update an exam draft (docstatus=0).

    ``member`` is kept in the signature so the SPA call is unchanged, but it
    is ignored: the draft always belongs to the session user (p006 F7).
    """
    answers = frappe.parse_json(answers)
    member = frappe.session.user

    if submission_name:
        # Update existing draft
        doc = frappe.get_doc("Exam Submission", submission_name)
        _assert_owns_submission(doc)
        _assert_may_take_exam(doc.course or course)
        if doc.docstatus != 0:
            frappe.throw(_("Cannot modify a submitted exam."))

        doc.time_taken = time_taken
        doc.result = []
        for answer in answers:
            doc.append(
                "result",
                {
                    "question": answer.get("question"),
                    "answer": sanitize_html(answer.get("answer")),
                    "points": "",
                },
            )
        doc.flags.ignore_permissions = True
        doc.save()
        return doc

    # Create new draft
    _assert_may_take_exam(course)
    scac = frappe.get_value(
        "Scheduled Course Assess Criteria", {"exam": exam, "parent": course}, "name"
    )
    course_name = frappe.get_value("Course Schedule", course, "course")
    exam_title = frappe.get_value("Exam Activity", exam, "title")
    student = frappe.get_value("Student", {"user": member}, "name")
    member_name = frappe.get_value("User", {"name": member}, "full_name")

    doc = frappe.new_doc("Exam Submission")
    doc.exam = exam
    doc.course = course
    doc.member = member
    doc.course_assess = scac
    doc.course_name = course_name
    doc.exam_title = exam_title
    doc.student = student
    doc.member_name = member_name
    doc.time_taken = time_taken
    doc.submission_date = frappe.utils.now_datetime()

    for answer in answers:
        doc.append(
            "result",
            {
                "question": answer.get("question"),
                "answer": sanitize_html(answer.get("answer")),
                "points": "",
            },
        )

    doc.flags.ignore_permissions = True
    doc.insert()
    return doc


@frappe.whitelist()
def submit_exam(submission_name):
    """Mark exam as submitted (not Frappe submit, just status change)."""
    doc = frappe.get_doc("Exam Submission", submission_name)
    _assert_owns_submission(doc)

    if doc.status != "Not Submitted":
        frappe.throw("This exam has already been submitted.")

    doc.status = "Not Graded"
    doc.submission_date = frappe.utils.now_datetime()
    doc.flags.ignore_permissions = True
    doc.save()
    return doc


@frappe.whitelist()
def get_exam_grading_comments(submission_name):
    """Get all grading comments for an Exam Submission."""
    if not submission_name:
        frappe.throw(_("Submission name is required."))

    return frappe.get_all(
        "Grading Comment",
        filters={"parent": submission_name, "parenttype": "Exam Submission"},
        fields=["author", "author_name", "comment", "comment_dt", "name"],
        order_by="comment_dt asc",
    )


@frappe.whitelist()
def add_exam_grading_comment(submission_name, comment):
    """Add a grading comment to an Exam Submission."""
    if not submission_name or not comment:
        frappe.throw(_("Submission name and comment are required."))

    doc = frappe.get_doc("Exam Submission", submission_name)

    from seminary.seminary.guards import is_course_staff

    user = frappe.session.user
    is_owner = doc.member == user
    # The student and the section's staff converse here; another section's
    # instructor does not (p007 §2.4).
    is_staff = is_course_staff(doc.course)
    if not is_owner and not is_staff:
        frappe.throw(
            _("You do not have permission to comment on this submission."),
            frappe.PermissionError,
        )

    author_name = frappe.db.get_value("User", user, "full_name") or user
    doc.append(
        "grading_comments",
        {
            "author": user,
            "author_name": author_name,
            "comment": comment,
            "comment_dt": frappe.utils.now_datetime(),
        },
    )
    doc.flags.ignore_permissions = True
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return doc.grading_comments[-1].as_dict()
