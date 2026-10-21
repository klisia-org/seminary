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
    """Asset Location sync and instructor-payroll provisioning are owned by the
    oikonomos bridge, which subscribes to Seminary Settings on_update itself."""
    # Per-role upload caps are cached (they are read on every upload), so the
    # table has to be invalidated here or a changed limit would not take effect
    # until the cache expired. privatedocs/p004.
    from seminary.storage import limits

    limits.clear_cache()

    # Instructor-payroll provisioning (Salary Slip custom fields + Instructor Pay
    # component) is owned by the oikonomos bridge, which subscribes to Seminary
    # Settings on_update. Nothing payroll-related runs here on a Frappe-only install.
