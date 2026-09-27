# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Billing actions Desk offers, routed to whichever billing app is active.

A Desk button never calls a billing app by name: the app may be missing, or
installed but retired (aretenic decision 051 §3). It calls here, and the active
`FinancialBackend` does the work -- or says it can't, and the button is hidden.
"""

import frappe

from seminary.seminary.financial.backend import get_financial_backend


def can_regenerate_current_term_charges() -> bool:
    """`desk_block_gates` predicate for the Registrar's regenerate button."""
    return get_financial_backend().can_regenerate_current_term_charges()


@frappe.whitelist()
def regenerate_current_term_charges() -> dict:
    frappe.only_for(["Registrar", "Seminary Manager", "System Manager"])
    return get_financial_backend().regenerate_current_term_charges()
