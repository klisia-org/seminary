"""Auto-submit existing Graduation Requirement Item rows after the doctype
became submittable.

Once `Graduation Requirement Item` has `is_submittable = 1`, both the
Program Graduation Requirement Link picker and the wildcard hook's
`_linked_doctypes()` cache filter by `docstatus = 1`. Pre-existing rows
created when the doctype was non-submittable (`docstatus = 0`) would
otherwise disappear from the picker and stop propagating linked-doc
status reflection.

Idempotent: skips rows already at docstatus 1.
"""

import frappe


def execute():
    rows = frappe.db.sql(
        "SELECT name FROM `tabGraduation Requirement Item` WHERE docstatus = 0",
        as_dict=True,
    )
    if not rows:
        print("No draft Graduation Requirement Item rows to submit.")
        return

    for row in rows:
        frappe.db.set_value(
            "Graduation Requirement Item",
            row.name,
            "docstatus",
            1,
            update_modified=False,
        )

    frappe.db.commit()
    frappe.cache().delete_value("_seminary_grad_link_doctypes")
    print(f"Submitted {len(rows)} Graduation Requirement Item row(s).")
