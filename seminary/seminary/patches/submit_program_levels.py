"""Auto-submit existing Program Level rows after Program Level became submittable.

Once `Program Level` has `is_submittable = 1`, the Program form's
`program_level` link query filters by `docstatus = 1`. Pre-existing rows
were created when the doctype was non-submittable (`docstatus = 0`) and
would otherwise disappear from the picker.

Idempotent: skips rows already at docstatus 1.
"""

import frappe


def execute():
    rows = frappe.db.sql(
        "SELECT name FROM `tabProgram Level` WHERE docstatus = 0",
        as_dict=True,
    )
    if not rows:
        print("No draft Program Level rows to submit.")
        return

    for row in rows:
        frappe.db.set_value(
            "Program Level",
            row.name,
            "docstatus",
            1,
            update_modified=False,
        )

    frappe.db.commit()
    print(f"Submitted {len(rows)} Program Level row(s).")
