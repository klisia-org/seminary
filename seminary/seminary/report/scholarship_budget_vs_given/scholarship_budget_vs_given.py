# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Scholarship Budget vs Given.

Scholarships are modeled as a tuition discount (forgone revenue), so the 100%-
discounted forgiveness invoices net to $0 in the GL and never reach ERPNext's
native Budget Variance Report. This report fills that gap, per scholarship cost
center and broken down by the Budget's distribution **periods**:

  * Budget    — the period's allocation (Budget Distribution row amount; a Budget
                with no distribution shows a single whole-fiscal-year row).
  * Given     — gross of the scholarship-customer invoices booked to the cost
                center with a posting date inside the period (what's committed).
  * Requested — estimated value of pending requests (Submitted / Under Review)
                whose effective date falls in the period; only Flat terms can be
                valued before invoicing, so Pending Requests (#) shows the full
                pipeline.
  * Remaining — Budget − Given − Requested.
"""

import frappe
from frappe import _

from seminary.seminary.scholarship import (
    _current_fiscal_year,
    _given_on_cost_center,
    _pending_requests_value,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})

    fy = filters.fiscal_year or _current_fiscal_year()[0]
    fy_dates = frappe.db.get_value(
        "Fiscal Year", fy, ["year_start_date", "year_end_date"], as_dict=True
    )
    if not fy_dates:
        frappe.throw(_("Fiscal Year {0} not found.").format(fy))
    fy_start, fy_end = fy_dates.year_start_date, fy_dates.year_end_date

    default_cc = frappe.db.get_single_value("Seminary Settings", "scholarship_cc")

    # Group scholarship templates by their effective cost center (own, else default).
    cc_to_templates = {}
    for t in frappe.get_all(
        "Scholarships", fields=["name", "scholarship", "cost_center"]
    ):
        cc = t.cost_center or default_cc
        if cc:
            cc_to_templates.setdefault(cc, []).append(t)

    if filters.cost_center:
        cc_to_templates = {
            filters.cost_center: cc_to_templates.get(filters.cost_center, [])
        }

    data = []
    for cc in sorted(cc_to_templates):
        names = [t.name for t in cc_to_templates[cc]]

        # Collect the budget periods on this cost center for the fiscal year. Merge
        # identical periods across budgets; fall back to one whole-year period when
        # no distribution is configured.
        budgets = frappe.get_all(
            "Budget",
            filters={
                "budget_against": "Cost Center",
                "cost_center": cc,
                "from_fiscal_year": fy,
                "docstatus": ["<", 2],
            },
            fields=["name", "budget_amount"],
        )
        periods = {}
        for b in budgets:
            dist = frappe.get_all(
                "Budget Distribution",
                filters={"parent": b.name},
                fields=["start_date", "end_date", "amount"],
            )
            rows = [r for r in dist if r.start_date and r.end_date]
            if rows:
                for r in rows:
                    key = (r.start_date, r.end_date)
                    periods[key] = periods.get(key, 0) + frappe.utils.flt(r.amount)
            else:
                # No distribution on this budget — bill it as one whole-year period
                # so its amount is never silently dropped.
                key = (fy_start, fy_end)
                periods[key] = periods.get(key, 0) + frappe.utils.flt(b.budget_amount)
        if not periods:
            periods = {(fy_start, fy_end): 0}

        for p_start, p_end in sorted(periods):
            budget = periods[(p_start, p_end)]
            given = _given_on_cost_center(cc, p_start, p_end)
            requested, req_count = _pending_requests_value(names, p_start, p_end)
            data.append(
                {
                    "cost_center": cc,
                    "period": f"{p_start} – {p_end}",
                    "budget": budget,
                    "given": given,
                    "requested": requested,
                    "pending_requests": req_count,
                    "remaining": budget - given - requested,
                }
            )

    columns = [
        {
            "label": _("Cost Center"),
            "fieldname": "cost_center",
            "fieldtype": "Link",
            "options": "Cost Center",
            "width": 190,
        },
        {
            "label": _("Period"),
            "fieldname": "period",
            "fieldtype": "Data",
            "width": 190,
        },
        {
            "label": _("Budget"),
            "fieldname": "budget",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("Given"),
            "fieldname": "given",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("Requested"),
            "fieldname": "requested",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("Pending Requests"),
            "fieldname": "pending_requests",
            "fieldtype": "Int",
            "width": 130,
        },
        {
            "label": _("Remaining"),
            "fieldname": "remaining",
            "fieldtype": "Currency",
            "width": 120,
        },
    ]
    return columns, data
