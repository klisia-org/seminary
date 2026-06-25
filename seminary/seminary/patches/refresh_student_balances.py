# Copyright (c) 2026, Klisia, Frappe Technologies and contributors
# For license information, please see license.txt

"""One-time migration: refresh all open Student Balances from current Sales
Invoice state, applying the customer filter (only the student's own customer).

Run via:
    bench --site <site> execute seminary.seminary.patches.refresh_student_balances.execute
"""

import frappe


def execute():
    # Student Balance was relocated to the oikonomos bridge. On a Frappe-only
    # install the doctype is absent and there is nothing to refresh; the import
    # is deferred so this historical patch stays loadable without oikonomos.
    if not frappe.db.exists("DocType", "Student Balance"):
        return
    from oikonomos.oikonomos.doctype.student_balance.student_balance import (
        refresh_from_sales_invoices,
    )

    open_balances = frappe.get_all(
        "Student Balance",
        filters={"is_open": 1},
        pluck="name",
    )
    print(f"Refreshing {len(open_balances)} open Student Balances...")

    refreshed = 0
    for sb_name in open_balances:
        try:
            result = refresh_from_sales_invoices(sb_name)
            refreshed += 1
            print(
                f"  {sb_name}: {result['invoices']} invoices, "
                f"net outstanding {result['net_outstanding']}"
            )
        except Exception as e:
            print(f"  {sb_name}: ERROR - {e}")

    frappe.db.commit()
    print(f"Done. Refreshed {refreshed} balances.")
