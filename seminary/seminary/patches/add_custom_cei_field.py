"""Add custom_cei Link field on Sales Invoice.

Run via: bench --site <site> execute seminary.seminary.patches.add_custom_cei_field.execute
"""

import frappe


def execute():
    if frappe.db.exists("Custom Field", "Sales Invoice-custom_cei"):
        print("custom_cei field already exists. Skipping.")
        return

    cf = frappe.get_doc(
        {
            "doctype": "Custom Field",
            "dt": "Sales Invoice",
            "fieldname": "custom_cei",
            "fieldtype": "Link",
            "options": "Course Enrollment Individual",
            "label": "Course Enrollment Individual",
            "insert_after": "custom_student",
            "read_only": 1,
        }
    )
    cf.insert(ignore_permissions=True)
    frappe.db.commit()
    print("Created custom_cei field on Sales Invoice.")
