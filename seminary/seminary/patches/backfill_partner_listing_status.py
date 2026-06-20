"""Backfill the alumni Partner Organization directory settings (ADR 053).

Three things existing sites can't pick up automatically:

1. `Partner Organization.listing_status` — the directory shows only "Listed" orgs.
   The field defaults to "Listed", but rows created before it existed land empty;
   set those to "Listed" so current partners stay visible. Alumni self-service
   submissions are created as "Pending Approval" and are unaffected.

2. `Seminary Settings.allow_alumni_view_partner_directory` — its field default of
   1 is only applied to a freshly created Single, not the existing singleton, so
   seed it to 1 (directory on by default) when it has never been set.

3. `Program Level.allow_alumni_create_partner_org` — adding a Check field doesn't
   reliably apply its default of 1 to existing rows. Since the field is brand new
   (no row was ever set deliberately), set every existing Program Level to 1 so the
   intended "default on" holds — a seminary then enables creation by flipping the
   single Seminary Settings toggle, and restricts specific levels from there.

Runs once (recorded in Patch Log); the listing/settings steps are also guarded so
a manual re-run won't clobber deliberate choices.
"""

import frappe


def execute():
    # On a site where the Partner module tables haven't been created yet,
    # `has_column` raises TableMissingError (it no longer returns False for a
    # missing table). Guard every table access with `table_exists` first — a
    # site without these tables has no rows to backfill, so skipping is correct.
    if frappe.db.table_exists("Partner Organization") and frappe.db.has_column(
        "Partner Organization", "listing_status"
    ):
        frappe.db.sql(
            """UPDATE `tabPartner Organization`
               SET listing_status = 'Listed'
               WHERE listing_status IS NULL OR listing_status = ''"""
        )
        print("Backfilled listing_status='Listed' on existing Partner Organizations.")

    # Seed the directory toggle ON for existing sites (default behavior) only when
    # it has never been set — never clobber a deliberate admin choice on re-run.
    has_value = frappe.db.exists(
        "Singles",
        {
            "doctype": "Seminary Settings",
            "field": "allow_alumni_view_partner_directory",
        },
    )
    if not has_value:
        frappe.db.set_single_value(
            "Seminary Settings", "allow_alumni_view_partner_directory", 1
        )
        print("Seeded allow_alumni_view_partner_directory=1 on Seminary Settings.")

    # Apply the "default on" to existing Program Levels (the field is new, so no
    # row was ever set deliberately).
    if frappe.db.table_exists("Program Level") and frappe.db.has_column(
        "Program Level", "allow_alumni_create_partner_org"
    ):
        frappe.db.sql(
            "UPDATE `tabProgram Level` SET allow_alumni_create_partner_org = 1"
        )
        print("Set allow_alumni_create_partner_org=1 on existing Program Levels.")

    frappe.db.commit()
