# Copyright (c) 2026, Klisia, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from seminary.seminary.sales_invoice_permissions import (
    _current_student,
    _should_restrict,
)


def has_permission(doc, ptype, user):
    if not user:
        user = frappe.session.user
    if not _should_restrict(user):
        return True
    student = _current_student(user)
    return doc.student == student


def get_permission_query_conditions(user):
    if not user:
        user = frappe.session.user
    if not _should_restrict(user):
        return ""
    student = _current_student(user)
    if not student:
        return "1=0"
    return f"(`tabStudent Balance`.student = {frappe.db.escape(student)})"
