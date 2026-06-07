"""Backfill `category` on existing Withdrawal Reasons.

The category field (added for the program-status spine) is required; default
existing rows to "Voluntary". Catalog rows are desk-configured, so this only
sets a safe default and does not otherwise touch them. Idempotent. See ADR 031.
"""

import frappe


def execute():
    updated = frappe.db.sql(
        """UPDATE `tabWithdrawal Reasons`
           SET category = 'Voluntary'
           WHERE category IS NULL OR category = ''"""
    )
    frappe.db.commit()
    print(f"Backfilled category on Withdrawal Reasons (rows touched: {updated}).")
