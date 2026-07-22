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
    """Backfill Asset Locations when room sync is switched on (ERPNext only).

    Room→Asset Location sync and the root_asset_location field require ERPNext's
    Location doctype, so the backfill is guarded: it never runs on a Frappe-only
    install. Instructor-payroll provisioning is owned by the oikonomos bridge
    (it subscribes to Seminary Settings on_update separately)."""
    if (
        doc.has_value_changed("sync_rooms_to_asset_locations")
        and doc.sync_rooms_to_asset_locations
        and frappe.db.exists("DocType", "Location")
    ):
        from seminary.seminary import locations

        frappe.enqueue(locations.backfill, queue="long")

    # Instructor-payroll provisioning (Salary Slip custom fields + Instructor Pay
    # component) is owned by the oikonomos bridge, which subscribes to Seminary
    # Settings on_update. Nothing payroll-related runs here on a Frappe-only install.
