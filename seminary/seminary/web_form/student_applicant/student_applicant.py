import frappe


@frappe.whitelist()
def get_context(context):
    at = frappe.db.get_value("Academic Term", {"iscurrent_acterm": 1}, "name")
    context.academic_term = at
    return context
