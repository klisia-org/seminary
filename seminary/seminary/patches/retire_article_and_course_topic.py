"""Retire the Article and Course Topic doctypes.

Both were leftovers from the original LMS scaffolding and are unused:

- `Course Topic` is a child table whose only `topic` link pointed at a
  `Topic` doctype that no longer exists in the app, and it was no longer
  mounted as a table on any parent (the Course form even kept a dead grid
  handler for it).
- `Article` was reference content linked from those Topics. Nothing in the
  app reads or writes it anymore.

Their JSON folders have been removed; this patch drops the leftover DocType
records and their tables so they disappear from the database too.

Idempotent.
"""

import frappe


def execute():
    for name in ("Course Topic", "Article"):
        if frappe.db.exists("DocType", name):
            frappe.delete_doc("DocType", name, force=True, ignore_missing=True)
            print(f"Deleted leftover DocType '{name}'.")

    frappe.db.commit()
