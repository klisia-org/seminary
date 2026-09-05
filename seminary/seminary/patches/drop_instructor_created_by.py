"""ADR 068 §7 — remove the `instructor_created_by` setting and its orphan.

The Select on `Seminary Settings` (Full Name / Naming Series / Employee Number)
had one consumer: a `validate` that toggled the `hidden` Property Setter of
`Instructor.naming_series`. Instructor has no `naming_series` field, which is
why both calls passed `validate_fields_for_doctype=False` and why the dead
branch survived. ADR 068 §5 then gave Instructor an unconditional opaque
docname, so the setting could not have meant anything even if the field had
existed.

Dropping the docfield leaves the Property Setter behind pointing at a field on
no doctype, and leaves the stored value in `tabSingles`. Neither breaks
anything on its own; both are the kind of residue that makes the next reader
believe the feature is still there.
"""

import frappe


def execute():
    setter = frappe.db.exists(
        "Property Setter", {"doc_type": "Instructor", "field_name": "naming_series"}
    )
    if setter:
        frappe.delete_doc(
            "Property Setter", setter, force=True, ignore_permissions=True
        )
        print("  removed the orphan Instructor.naming_series property setter")

    frappe.db.delete(
        "Singles", {"doctype": "Seminary Settings", "field": "instructor_created_by"}
    )
