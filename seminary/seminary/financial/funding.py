# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Sources of funding (p020).

Tuition comes from the active financial backend: exactly one is active, so it is
never counted twice. Everything else comes from the `funding_sources` hook. Each
entry is a dotted path to a function `(start, end)` returning
`{"since": date | None, "rows": [line, ...]}` (see `report` for a line), where
`since` is the first date that app has any funding. koinonia registers gifts.

The period helpers are shared with the apps that answer the hook, so every
report covers the same dates.
"""

from __future__ import annotations

from datetime import date

import frappe
from frappe.utils import add_years, flt, getdate, today

from seminary.seminary.financial.backend import get_financial_backend

FUNDING_HOOK = "funding_sources"
EVERY_YEAR = "Every year"


def fiscal_year(on_date=None) -> tuple[date, date]:
    return get_financial_backend().fiscal_year(on_date)


def period(filters) -> tuple[date, date]:
    """The dates a report asked for, or the current fiscal year."""
    filters = filters or {}
    if filters.get("from_date") and filters.get("to_date"):
        start, end = getdate(filters["from_date"]), getdate(filters["to_date"])
        if start > end:
            frappe.throw(frappe._("The start date must be on or before the end date."))
        return start, end
    return fiscal_year()


def year_earlier(start, end) -> tuple[date, date]:
    return getdate(add_years(start, -1)), getdate(add_years(end, -1))


def fiscal_years_since(since) -> list[tuple[date, date]]:
    """Every fiscal year from the one containing `since` to the current one."""
    years = []
    start, end = fiscal_year(since or today())
    last = fiscal_year()[0]
    while start <= last:
        years.append((start, end))
        start, end = fiscal_year(add_years(start, 1))
    return years


def year_label(start, end) -> str:
    """'2026' for a calendar year, '2025–26' for one that straddles two."""
    start, end = getdate(start), getdate(end)
    if start.year == end.year:
        return str(start.year)
    return f"{start.year}–{str(end.year)[-2:]}"


def tuition(start, end) -> dict:
    return get_financial_backend().tuition_revenue(start, end)


def other_sources(start, end) -> dict:
    """Every hooked app's lines for the period, in hook order."""
    rows, since = [], []
    for path in frappe.get_hooks(FUNDING_HOOK):
        answer = frappe.get_attr(path)(start, end) or {}
        rows.extend(answer.get("rows") or [])
        if answer.get("since"):
            since.append(getdate(answer["since"]))
    return {"rows": rows, "since": min(since) if since else None}


def first_date():
    """The first date any source has funding, or None. `since` does not depend
    on the period asked for."""
    start, end = fiscal_year()
    dates = [tuition(start, end).get("since"), other_sources(start, end).get("since")]
    dates = [getdate(d) for d in dates if d]
    return min(dates) if dates else None


def funding(start, end) -> list[dict]:
    """The report's lines for one period: [{"line", "label", "amount"}]."""
    fees = tuition(start, end)
    gross, aid = flt(fees.get("gross")), flt(fees.get("scholarships"))
    lines = [
        {
            "line": "tuition_gross",
            "label": frappe._("Tuition and fees"),
            "amount": gross,
            "sort": (0, 0),
        },
        {
            "line": "scholarships",
            "label": frappe._("Less institutional scholarships"),
            "amount": -aid,
            "sort": (0, 1),
        },
        {
            "line": "tuition_net",
            "label": frappe._("Net tuition and fees"),
            "amount": gross - aid,
            "total": True,
            "chart": True,
            "sort": (0, 2),
        },
    ]
    lines.extend(other_sources(start, end)["rows"])
    return lines


# -- the two views a funding report offers -------------------------------------
#
# A line is {"line", "label", "amount"} plus, optionally, "total": True to count
# toward the Total row, "chart": True to appear in the every-year chart, and
# "sort": a tuple placing it among the others (tuition comes first).


def report(lines_for, filters, since, total_label=None):
    """(columns, data, chart) for a funding report.

    `lines_for(start, end)` gives one period's lines; `since()` the first date
    with any funding. The default view is a period beside the same dates a year
    earlier; the every-year view puts each fiscal year side by side."""
    filters = filters or {}
    if filters.get("view") == EVERY_YEAR:
        periods = fiscal_years_since(since())
        labels = [year_label(s, e) for s, e in periods]
    else:
        start, end = period(filters)
        periods = [(start, end), year_earlier(start, end)]
        labels = [_range_label(*p) for p in periods]

    keyed, order = {}, []
    for i, (start, end) in enumerate(periods):
        for line in lines_for(start, end):
            key = line["line"]
            if key not in keyed:
                keyed[key] = {**line, "values": [0.0] * len(periods)}
                order.append(key)
            keyed[key]["values"][i] += flt(line["amount"])

    order.sort(key=lambda k: keyed[k].get("sort", (9,)))
    data = [{"label": keyed[k]["label"], **_cells(keyed[k]["values"])} for k in order]
    totals = [
        sum(keyed[k]["values"][i] for k in order if keyed[k].get("total"))
        for i in range(len(periods))
    ]
    data.append(
        {"label": total_label or frappe._("Total"), "bold": 1, **_cells(totals)}
    )

    columns = [
        {
            "fieldname": "label",
            "label": frappe._("Source"),
            "fieldtype": "Data",
            "width": 300,
        }
    ]
    columns += [
        {
            "fieldname": f"p{i}",
            "label": labels[i],
            "fieldtype": "Currency",
            "width": 140,
        }
        for i in range(len(periods))
    ]
    chart = None
    if filters.get("view") == EVERY_YEAR:
        chart = {
            "data": {
                "labels": labels,
                "datasets": [
                    {"name": keyed[k]["label"], "values": keyed[k]["values"]}
                    for k in order
                    if keyed[k].get("chart")
                ],
            },
            "type": "bar",
            "barOptions": {"stacked": 1},
        }
    else:
        for row in data:
            this, before = row["p0"], row["p1"]
            row["change"] = this - before
            row["change_pct"] = (this - before) / abs(before) * 100 if before else None
        columns += [
            {
                "fieldname": "change",
                "label": frappe._("Change"),
                "fieldtype": "Currency",
                "width": 130,
            },
            {
                "fieldname": "change_pct",
                "label": frappe._("Change %"),
                "fieldtype": "Percent",
                "width": 100,
            },
        ]
    return columns, data, chart


def _cells(values):
    return {f"p{i}": v for i, v in enumerate(values)}


def _range_label(start, end):
    from frappe.utils import formatdate

    return f"{formatdate(start)} – {formatdate(end)}"


@frappe.whitelist()
def current_fiscal_year():
    """The current fiscal year, for a funding report's default dates."""
    # Who can open Sources of Funding, or koinonia's Giving by Source.
    frappe.only_for(["Advancement Officer", "Seminary Manager", "System Manager"])
    return fiscal_year()
