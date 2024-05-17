# seminary/seminary/web_form/enroll_in_a_course/enroll_in_a_course.py

import frappe


def get_context(context):
    pass

@frappe.whitelist()
def get_student_name():
    user = frappe.session.user
    student = frappe.get_value("Student", {"user": user}, "student_name")
    print(student)
    return student