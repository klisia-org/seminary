"""Add custom_graduation_request Link field on Sales Invoice.

Mirrors the custom_cei pattern: a back-reference from a Sales Invoice
to the Graduation Request that generated it. Used by the Graduation
Request controller's on_cancel handler to find and cancel unpaid
invoices, and by the Payment Entry hook to auto-transition the GR
workflow on payment.

Run via: bench --site <site> migrate (or execute directly)
"""

import frappe


def execute():
    if frappe.db.exists("Custom Field", "Sales Invoice-custom_graduation_request"):
        print("custom_graduation_request field already exists. Skipping.")
        return

    cf = frappe.get_doc(
        {
            "doctype": "Custom Field",
            "dt": "Sales Invoice",
            "fieldname": "custom_graduation_request",
            "fieldtype": "Link",
            "options": "Graduation Request",
            "label": "Graduation Request",
            "insert_after": "custom_cei",
            "read_only": 1,
        }
    )
    cf.insert(ignore_permissions=True)
    frappe.db.commit()
    print("Created custom_graduation_request field on Sales Invoice.")
