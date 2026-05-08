"""Ensure the custom_cei DB column exists on tabSales Invoice.

The earlier patch (add_custom_cei_field) only creates the Custom Field doc
when missing, so on sites where the doc exists but the underlying column
was never synced (or was dropped), CEI creation fails with
'Unknown column custom_cei in WHERE'. create_custom_fields() upserts the
doc AND forces frappe.db.updatedb() to add the column.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Sales Invoice": [
                {
                    "fieldname": "custom_cei",
                    "fieldtype": "Link",
                    "options": "Course Enrollment Individual",
                    "label": "Course Enrollment Individual",
                    "insert_after": "custom_student",
                    "read_only": 1,
                }
            ]
        }
    )
    frappe.db.commit()
