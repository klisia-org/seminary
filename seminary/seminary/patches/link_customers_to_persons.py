"""Backfill the Customer.person reverse link (ADR 042 addendum).

Creates the custom field if missing, then walks Persons with a customer and
person-linked Students/Applicants with a customer, mirroring the link both
ways. Idempotent (first link wins, never overwrites).
"""

import frappe


def execute():
    # Customer + the Person<->Customer linker now live in the oikonomos bridge.
    # Nothing to backfill on a Frappe-only install; deferred import keeps this
    # historical patch loadable without oikonomos.
    if "oikonomos" not in frappe.get_installed_apps():
        return
    from oikonomos.financial.customer_person import (
        setup_custom_fields,
        link_customer,
    )

    setup_custom_fields()

    linked = 0
    for p in frappe.get_all(
        "Person", filters={"customer": ("is", "set")}, fields=["name", "customer"]
    ):
        if not frappe.db.get_value("Customer", p.customer, "person"):
            frappe.db.set_value(
                "Customer", p.customer, "person", p.name, update_modified=False
            )
            linked += 1

    for doctype in ("Student", "Student Applicant"):
        rows = frappe.get_all(
            doctype,
            filters={"person": ("is", "set"), "customer": ("is", "set")},
            fields=["person", "customer"],
        )
        for row in rows:
            link_customer(row.person, row.customer)

    frappe.db.commit()
    print(f"Customer.person backfilled ({linked} direct Person links).")
