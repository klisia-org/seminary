"""Give the starter Partner Types their Sources of Funding line (p020)."""

import frappe

from seminary.install import FUNDING_LINE_DEFAULTS


def execute():
    frappe.reload_doc("partner", "doctype", "partner_type")
    for type_name, line in FUNDING_LINE_DEFAULTS.items():
        if frappe.db.exists("Partner Type", type_name) and not frappe.db.get_value(
            "Partner Type", type_name, "funding_line"
        ):
            frappe.db.set_value(
                "Partner Type", type_name, "funding_line", line, update_modified=False
            )
