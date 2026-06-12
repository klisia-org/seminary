"""Move Channel Provider Account credentials from the raw `settings` JSON into
the typed fields added in ADR 045 — secrets land in encrypted Password fields.

Idempotent: only fills a typed field that is still empty, and strips the keys
it migrated out of the JSON so secrets no longer sit in plain text.
"""

import json

import frappe

from seminary.seminary.doctype.channel_provider_account.channel_provider_account import (
    CONFIG_FIELDS,
)


def execute():
    if not frappe.db.exists("DocType", "Channel Provider Account"):
        return
    for name in frappe.get_all("Channel Provider Account", pluck="name"):
        doc = frappe.get_doc("Channel Provider Account", name)
        mapping = CONFIG_FIELDS.get(doc.provider)
        if not mapping or not doc.settings:
            continue
        try:
            raw = json.loads(doc.settings)
        except ValueError:
            continue
        if not isinstance(raw, dict):
            continue

        changed = False
        for key, fieldname, _is_secret in mapping:
            if key in raw and raw[key] and not doc.get(fieldname):
                doc.set(fieldname, raw.pop(key))
                changed = True

        if not changed:
            continue
        # Keep any unmapped extras; drop the now-migrated keys (incl. secrets).
        doc.settings = json.dumps(raw) if raw else None
        doc.save(ignore_permissions=True)
    frappe.db.commit()
