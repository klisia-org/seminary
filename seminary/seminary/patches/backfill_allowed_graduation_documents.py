# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Backfill the curated Allowed Graduation Document picker on existing
'Linked Document' graduation requirements (ADR 054).

Existing library items carry a raw `link_doctype`. We ensure an Allowed
Graduation Document exists for each distinct doctype and point the item's new
`allowed_document` field at it, so the friendly picker is populated and the
read-only `link_doctype` keeps resolving."""

import frappe

from seminary.seminary.graduation import LINKED_DOC_FULFILL_STATUS


def execute():
    if not frappe.db.exists("DocType", "Allowed Graduation Document"):
        return

    items = frappe.get_all(
        "Graduation Requirement Item",
        filters={"requirement_type": "Linked Document", "link_doctype": ("is", "set")},
        fields=["name", "link_doctype", "allowed_document"],
    )
    for item in items:
        if item.allowed_document:
            continue
        dt = item.link_doctype
        if not dt:
            continue
        if not frappe.db.exists("Allowed Graduation Document", dt):
            frappe.get_doc(
                {
                    "doctype": "Allowed Graduation Document",
                    "document_type": dt,
                    "label": dt,
                    "fulfilling_status": LINKED_DOC_FULFILL_STATUS.get(dt, "Completed"),
                    "is_active": 1,
                    "built_in": 1 if dt in LINKED_DOC_FULFILL_STATUS else 0,
                }
            ).insert(ignore_permissions=True)
        frappe.db.set_value(
            "Graduation Requirement Item", item.name, "allowed_document", dt
        )
    frappe.db.commit()
