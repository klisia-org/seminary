# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Portal scholarship shims (the scholarship engine lives in oikonomos).

Scholarships (the `Scholarships` template + per-enrollment `Scholarship Award`)
are oikonomos doctypes; all the logic — budget availability, portal application,
the daily retention review — lives in `oikonomos.financial.scholarship`.

These three names survive in seminary only because the student SPA (Fees.vue)
calls them by their seminary path. They delegate to the financial backend, so a
Frappe-only seminary returns empty (there are no scholarships) without importing
oikonomos or touching a missing doctype.
"""

import frappe

from seminary.seminary.financial.backend import get_financial_backend


@frappe.whitelist()
def get_student_scholarship(student):
    """The student's active award(s) for the Fees page (empty without a backend)."""
    return get_financial_backend().student_scholarships(student)


@frappe.whitelist()
def get_available_scholarships(student):
    """Scholarships the student may apply for on the portal (empty without one)."""
    return get_financial_backend().available_scholarships(student)


@frappe.whitelist()
def apply_for_scholarship(program_enrollment, scholarship, comment=None):
    """Create a Scholarship Award request from the portal."""
    return get_financial_backend().apply_for_scholarship(
        program_enrollment, scholarship, comment
    )
