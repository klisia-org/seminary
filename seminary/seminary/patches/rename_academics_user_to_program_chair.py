"""Rename the "Academics User" role to "Program Chair".

Background: Seminary used the ERPNext-inherited "Academics User" role as its
de-facto broad academic-authority role (programs & curriculum) but never created
it itself, and the role's name no longer matched its meaning. It is renamed to
"Program Chair"; the app now owns the role via install.create_program_chair_role.
See ADR 030.

frappe.rename_doc on a Role cascades the Link fields that reference it — notably
`tabDocPerm.role` and `tabHas Role.role` — so existing doctype permissions and
every user's role assignment move to "Program Chair" automatically. The doctype
JSON permission blocks are updated in the same change so `bench migrate` does not
re-import the old name.

NOTE: this moves ALL former "Academics User" holders to "Program Chair" wholesale.
Records-lifecycle staff who should instead hold "Registrar" must be re-assigned
manually afterwards — that is user data the rename cannot split.

Idempotent.
"""

import frappe


def execute():
    if not frappe.db.exists("Role", "Academics User"):
        return

    if frappe.db.exists("Role", "Program Chair"):
        # Target already exists (e.g. created by install on a fresh-then-upgraded
        # site). Merge the old role into it so assignments/permissions collapse.
        frappe.rename_doc(
            "Role", "Academics User", "Program Chair", merge=True, force=True
        )
    else:
        frappe.rename_doc("Role", "Academics User", "Program Chair", force=True)

    frappe.db.commit()
    print('Renamed role "Academics User" -> "Program Chair".')
