import frappe

ACCOUNTING_BYPASS_ROLES = {"System Manager", "Accounts Manager", "Accounts User"}


def _current_student(user):
    return frappe.db.get_value("Student", {"user": user}, "name")


def _should_restrict(user):
    if not user or user == "Administrator":
        return False
    roles = set(frappe.get_roles(user))
    if roles & ACCOUNTING_BYPASS_ROLES:
        return False
    return bool(_current_student(user))


def has_permission(doc, ptype, user):
    if not user:
        user = frappe.session.user
    if not _should_restrict(user):
        return True
    student = _current_student(user)
    return getattr(doc, "custom_student", None) == student


def get_permission_query_conditions(user):
    if not user:
        user = frappe.session.user
    if not _should_restrict(user):
        return ""
    student = _current_student(user)
    if not student:
        return "1=0"
    return f"(`tabSales Invoice`.custom_student = {frappe.db.escape(student)})"
