"""decisions/100d: the two meeting capture methods are allowed unless the school
turns one off. On an existing site the new checks would otherwise read as off."""

import frappe


def execute():
    for field in ("meeting_capture_account", "meeting_capture_bot"):
        if not frappe.db.exists(
            "Singles", {"doctype": "Seminary Settings", "field": field}
        ):
            frappe.db.set_single_value("Seminary Settings", field, 1)
