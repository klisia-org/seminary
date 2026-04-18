# Copyright (c) 2026, Klisia, Frappe Technologies and contributors
# For license information, please see license.txt

"""One-time migration: refresh all open Student Balances from current Sales
Invoice state, applying the customer filter (only the student's own customer).

Run via:
    bench --site <site> execute seminary.seminary.patches.refresh_student_balances.execute
"""

import frappe
from seminary.seminary.doctype.student_balance.student_balance import (
    refresh_from_sales_invoices,
)


def execute():
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
