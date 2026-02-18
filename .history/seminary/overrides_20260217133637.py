import frappe

def update_website_context(context):
    try:
        context.show_student_application = frappe.db.get_single_value(
            "Seminary Settings", "show_student_application_on_login"
        )
    except Exception:
        context.show_student_application = 0