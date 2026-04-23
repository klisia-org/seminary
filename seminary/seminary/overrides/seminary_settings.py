# Copyright (c) 2026, Klisia, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def validate(doc, method=None):
    """Block saving Seminary Settings with ``hrms_enable`` on if HRMS is missing."""
    if doc.hrms_enable and "hrms" not in frappe.get_installed_apps():
        frappe.throw(
            _(
                "The HRMS app is not installed on this site. "
                "Install it via 'bench get-app hrms && bench install-app hrms' "
                "before enabling HRMS Payroll."
            )
        )


def on_update(doc, method=None):
    """Provision Salary Slip custom fields + Instructor Pay component when HRMS is on."""
    if not doc.hrms_enable:
        return

    from seminary.seminary.overrides.salary_slip import (
        ensure_custom_fields,
        ensure_salary_components,
    )

    ensure_custom_fields()
    ensure_salary_components()
