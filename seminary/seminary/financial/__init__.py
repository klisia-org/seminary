# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Financial backend seam.

Seminary is being decoupled from ERPNext: all billing/payment logic moves to a
separate `oikonomos` app, and seminary must run on Frappe alone. This package
holds the *seam* — an abstract `FinancialBackend` interface plus a
`NullFinancialBackend` so academic flows work with no financial app installed.

The real (ERPNext-backed) implementation is registered via the
`seminary_financial_backend` hook. During Phase 0 of the refactor that
implementation still lives in seminary (`erpnext_backend.SeminaryErpnextBackend`)
and is registered from seminary's own hooks.py; in a later phase it moves to
oikonomos and seminary's temporary registration is removed.

See ~/.claude/plans (oikonomos roadmap) for the full sequence.
"""
