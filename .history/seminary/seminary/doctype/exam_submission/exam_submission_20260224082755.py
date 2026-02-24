# Copyright (c) 2025, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from seminary.seminary.api import sanitize_html

class ExamSubmission(Document):
    pass
@frappe.whitelist()
def create_exam_submission(exam, course, member, answers, time_taken):
    scac = frappe.get_value(
        "Scheduled Course Assess Criteria", {"exam": exam, "parent": course}, "name"
    )
    course_name = frappe.get_value("Course Schedule", course, "course")
    exam_title = frappe.get_value("Exam Activity", exam, "title")
    student = frappe.get_value("Student", {"user": member}, "name")
    member_name = frappe.get_value("User", {"name": member}, "full_name")
    answers = frappe.parse_json(answers)

    exam_submission = frappe.new_doc("Exam Submission")
    exam_submission.exam = exam
    exam_submission.course = course
    exam_submission.member = member
    exam_submission.course_assess = scac
    exam_submission.course_name = course_name
    exam_submission.exam_title = exam_title
    exam_submission.student = student
    exam_submission.member_name = member_name
    exam_submission.time_taken = time_taken
    exam_submission.submission_date = frappe.utils.now_datetime()

    for answer in answers:
        exam_submission.append(
            "result",
            {
                "question": answer.get("question"),
                "answer": sanitize_html(answer.get("answer")),  # ← sanitize
                "points": "",
            },
        )

    exam_submission.flags.ignore_permissions = True
    exam_submission.insert()
    return exam_submission




