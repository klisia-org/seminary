# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Financial backend seam.

Seminary is being decoupled from ERPNext: all billing/payment logic moves to a
separate `oikonomos` app, and seminary must run on Frappe alone. This package
holds the *seam* — an abstract `FinancialBackend` interface plus a
`NullFinancialBackend` so academic flows work with no financial app installed.

The real (ERPNext-backed) implementation lives in the oikonomos app
(`oikonomos.financial.backend.OikonomosFinancialBackend`) and registers itself
via the `seminary_financial_backend` hook. Seminary holds only the contract
(`backend.py`) and never imports oikonomos or ERPNext.

See ~/.claude/plans (oikonomos roadmap) for the full sequence.
"""
