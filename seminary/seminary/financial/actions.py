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


def has_financial_backend() -> bool:
    """`desk_block_gates` predicate for Getting Started's financial step."""
    return get_financial_backend().setup_route() is not None


@frappe.whitelist()
def open_financial_setup():
    """Send the browser to the active billing app's first setup page."""
    frappe.only_for(["Seminary Manager", "System Manager"])
    route = get_financial_backend().setup_route() or "/desk/seminary-settings"
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = route
