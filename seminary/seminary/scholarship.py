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
from seminary.seminary.guards import require_own_enrollment, require_own_student


# All three take a caller-supplied target and gate on nothing (p005a A01-17).
# They return empty on this Frappe-only bench, which is why nobody noticed --
# with the oikonomos bridge installed they are another student's awards, and a
# scholarship filed against another student's enrollment. Gated here rather
# than in the bridge, so the check exists before the bridge does (p010 H15).


@frappe.whitelist()
def get_student_scholarship(student):
    """The student's active award(s) for the Fees page (empty without a backend)."""
    require_own_student(student)
    return get_financial_backend().student_scholarships(student)


@frappe.whitelist()
def get_available_scholarships(student):
    """Scholarships the student may apply for on the portal (empty without one)."""
    require_own_student(student)
    return get_financial_backend().available_scholarships(student)


@frappe.whitelist()
def apply_for_scholarship(program_enrollment, scholarship, comment=None):
    """Create a Scholarship Award request from the portal."""
    require_own_enrollment(program_enrollment)
    return get_financial_backend().apply_for_scholarship(
        program_enrollment, scholarship, comment
    )
