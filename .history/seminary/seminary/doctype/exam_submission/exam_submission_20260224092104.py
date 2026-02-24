# Copyright (c) 2025, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from seminary.seminary.api import sanitize_html


class ExamSubmission(Document):
    pass

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
            doc.append("result", {
                "question": answer.get("question"),
                "answer": sanitize_html(answer.get("answer")),
                "points": "",
            })
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
        doc.append("result", {
            "question": answer.get("question"),
            "answer": sanitize_html(answer.get("answer")),
            "points": "",
        })

    doc.flags.ignore_permissions = True
    doc.insert()
    return doc


@frappe.whitelist()
def submit_exam(submission_name):
    """Submit a saved exam draft."""
    doc = frappe.get_doc("Exam Submission", submission_name)

    if doc.docstatus != 0:
        frappe.throw(_("This exam has already been submitted."))

    doc.status = "Not Graded"
    doc.submission_date = frappe.utils.now_datetime()
    doc.flags.ignore_permissions = True
    doc.submit()
    return doc