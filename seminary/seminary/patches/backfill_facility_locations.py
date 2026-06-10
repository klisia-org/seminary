"""Create ERPNext Locations for existing Campuses, Buildings, and Rooms (ADR 039).

No-op when room→Location sync is disabled. Idempotent (identity is the stored
``location`` link), so re-running is safe.
"""

import frappe

from seminary.seminary import locations


def execute():
    # A `default: 1` on a new field doesn't backfill an existing Single, so the
    # opt-out toggle reads 0 on upgraded sites. Set it on (the rollout default)
    # only if it was never written — never override an explicit choice.
    already_set = frappe.db.sql(
        """SELECT 1 FROM `tabSingles`
           WHERE doctype = 'Seminary Settings'
             AND field = 'sync_rooms_to_asset_locations' LIMIT 1"""
    )
    if not already_set:
        frappe.db.set_single_value(
            "Seminary Settings", "sync_rooms_to_asset_locations", 1
        )

    locations.backfill()
    frappe.db.commit()
    print("Backfilled Asset Locations for facilities (if sync enabled).")
