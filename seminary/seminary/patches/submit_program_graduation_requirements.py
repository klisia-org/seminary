"""Auto-submit existing Program Graduation Requirement rows after the
doctype became submittable.

Once `Program Graduation Requirement` has `is_submittable = 1`, the
doctype follows a cancel-as-retire lifecycle: cancel sets `active = 0`
and `active_until = today()` via the controller's `on_cancel` hook.
Pre-existing rows created when the doctype was non-submittable
(`docstatus = 0`) need to be lifted to docstatus 1 so future amendments
work and so the policy's snapshot semantics are unambiguous.

Idempotent: skips rows already at docstatus 1.
"""

import frappe


def execute():
    rows = frappe.db.sql(
        "SELECT name FROM `tabProgram Graduation Requirement` WHERE docstatus = 0",
        as_dict=True,
    )
    if not rows:
        print("No draft Program Graduation Requirement rows to submit.")
        return

    for row in rows:
        frappe.db.set_value(
            "Program Graduation Requirement",
            row.name,
            "docstatus",
            1,
            update_modified=False,
        )

    frappe.db.commit()
    print(f"Submitted {len(rows)} Program Graduation Requirement row(s).")
