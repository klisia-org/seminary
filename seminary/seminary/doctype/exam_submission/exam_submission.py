# Copyright (c) 2025, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from seminary.seminary.api import sanitize_html
from frappe import _
import re


class ExamSubmission(Document):
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


@frappe.whitelist()
def save_exam_comment(submission_name, row_name, comments):
    """Save a single question comment on an Exam Submission."""
    frappe.db.set_value("Exam Question Result", row_name, "comments", comments)


@frappe.whitelist()
def save_exam_grade(submission_name, status, score, percentage, fudge_points, result):
    """Save instructor grading for an Exam Submission."""
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
                row.comments = row_data.get("comments") or ""
                break

    doc.flags.ignore_permissions = True
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return doc


@frappe.whitelist()
def save_exam_draft(exam, course, member, answers, time_taken, submission_name=None):
    """Save or update an exam draft (docstatus=0)."""
    answers = frappe.parse_json(answers)

    if submission_name:
        # Update existing draft
        doc = frappe.get_doc("Exam Submission", submission_name)
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

    user = frappe.session.user
    user_doc = frappe.get_doc("User", user)
    is_owner = doc.member == user
    is_staff = any(
        r.role in ("Instructor", "Course Moderator", "Evaluator", "System Manager")
        for r in user_doc.roles
    )
    if not is_owner and not is_staff:
        frappe.throw(_("You do not have permission to comment on this submission."))

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
