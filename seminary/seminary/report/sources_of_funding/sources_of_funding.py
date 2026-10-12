# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Sources of Funding (p020): tuition from the active billing app beside the
gifts and other funding other apps report through `funding_sources`. Totals
only, never names."""

from frappe import _

from seminary.seminary.financial import funding


def footnote():
    """Translated per request, not once at import."""
    return _(
        "Read from the billing and giving records, not the general ledger. Figures can differ from the "
        "audited statements by timing and by adjustments made only in the books."
    )


def execute(filters=None):
    columns, data, chart = funding.report(funding.funding, filters, funding.first_date)
    return columns, data, footnote(), chart
