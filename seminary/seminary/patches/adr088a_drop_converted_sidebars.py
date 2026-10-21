"""Drop the sidebars Frappe 16 converted from Seminary's old Workspace Sidebars (decision 088a).

The conversion stored one per module ("Seminary", "Partner"), with no app and not standard. They
are not on the rail, but the "Seminary" one claimed the Seminary Workspace, so opening Home from
any area could switch to it. Seminary now ships its own sidebars, so these are removed. A sidebar
someone edited after the conversion (modified later than created) is a school's own and is
kept.
"""

import frappe

NAMES = ("Seminary", "Partner", "Alumni")


def execute():
    for name in NAMES:
        row = frappe.db.get_value(
            "Sidebar", name, ["app", "standard", "creation", "modified"], as_dict=True
        )
        if not row or row.app or row.standard or row.modified > row.creation:
            continue
        frappe.delete_doc("Sidebar", name, ignore_permissions=True, force=True)
