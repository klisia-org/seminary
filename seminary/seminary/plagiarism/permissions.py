"""Defense-in-depth permission query for Plagiarism Check Result.

The doctype JSON already withholds the Student role, but plagiarism findings are
sensitive enough to gate a second way: only graders/managers may read a result,
regardless of any share or owner path. Mirrors the staff-role check style used
across api.py.
"""

import frappe

STAFF_ROLES = {
    "Instructor",
    "Program Chair",
    "Seminary Manager",
    "System Manager",
}


def has_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    return bool(STAFF_ROLES & set(frappe.get_roles(user)))
