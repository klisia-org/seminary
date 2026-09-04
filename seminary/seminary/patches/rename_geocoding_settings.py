"""ADR 068 §7 — `Geocoding Settings` becomes `Address Geocoding Settings`.

Frappe already ships a `Geolocation Settings` single (Integrations module,
Geoapify / Nomatim / HERE) for *address autocompletion* — completing an address
as someone types it. Ours resolves a finished address to coordinates. Different
jobs, different provider accounts, but adjacent enough names that an admin
searching "geo" finds two settings pages holding API keys and has to guess.

Runs pre-model-sync, so it renames the existing doctype and its `tabSingles`
rows before `sync_all` would otherwise create a second, empty single under the
new name and leave the old one orphaned with the school's key inside it.

The stored password is carried across by hand: `__Auth` is keyed on the doctype
name, and `rename_doc` does not follow it — so without this the key silently
vanishes and geocoding starts failing with no visible cause, which is the exact
failure mode the rest of this work exists to prevent.
"""

import frappe

OLD = "Geocoding Settings"
NEW = "Address Geocoding Settings"


def execute():
    if not frappe.db.exists("DocType", OLD):
        return
    if frappe.db.exists("DocType", NEW):
        # Both present: the new one was synced before this ran. Keep the old
        # values, they are the ones a human typed.
        _carry_values()
        frappe.delete_doc("DocType", OLD, force=True, ignore_permissions=True)
        return

    key = _stored_key(OLD)
    frappe.rename_doc("DocType", OLD, NEW, force=True, show_alert=False)
    frappe.db.sql("update `tabSingles` set doctype = %s where doctype = %s", (NEW, OLD))
    if key:
        _store_key(NEW, key)
    print("  renamed %r to %r" % (OLD, NEW))


def _stored_key(doctype):
    from frappe.utils.password import get_decrypted_password

    try:
        return get_decrypted_password(
            doctype, doctype, "api_key", raise_exception=False
        )
    except Exception:
        return None


def _store_key(doctype, key):
    from frappe.utils.password import set_encrypted_password

    set_encrypted_password(doctype, doctype, key, "api_key")


def _carry_values():
    rows = frappe.db.sql(
        "select field, value from `tabSingles` where doctype = %s", (OLD,), as_dict=True
    )
    for row in rows:
        if row.value in (None, ""):
            continue
        frappe.db.set_value(NEW, NEW, row.field, row.value, update_modified=False)
    key = _stored_key(OLD)
    if key:
        _store_key(NEW, key)
    frappe.db.sql("delete from `tabSingles` where doctype = %s", (OLD,))
