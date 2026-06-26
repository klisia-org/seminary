# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Public-holiday lookups via the Open World Holidays Framework.

Seminary is a global app, so it can't depend on ERPNext's manually-maintained
Holiday List doctype (and won't have it on a Frappe-only install). Instead this
module computes public holidays from the `holidays` PyPI package
(https://github.com/vacanza/holidays), which covers ~150 countries with
subdivisions — zero manual data entry.

The country is taken from the system default (set during site setup) unless an
explicit country name/ISO code is passed. Used by attendance/leave to avoid
counting public holidays as absences.
"""

import frappe
from frappe.utils import getdate


def is_holiday(date, country=None, subdiv=None) -> bool:
    """True if `date` is a public holiday in the given country (default: the
    site's default country). Unknown/unsupported countries return False rather
    than raising, so callers never need to guard."""
    if not date:
        return False
    d = getdate(date)
    code = _iso_code(country or frappe.db.get_default("country"))
    if not code:
        return False
    cal = _calendar(code, d.year, subdiv)
    return d in cal if cal is not None else False


def _iso_code(country):
    """Map a country name (Frappe Country doctype) or raw code to the uppercase
    ISO-3166 alpha-2 code the holidays library expects."""
    if not country:
        return None
    # Already a 2-letter code?
    if len(country) == 2:
        return country.upper()
    code = frappe.db.get_value("Country", country, "code")
    return code.upper() if code else None


def _calendar(code, year, subdiv=None):
    """Return a holidays calendar for the country/year, or None if unsupported."""
    import holidays as holidays_lib

    try:
        return holidays_lib.country_holidays(code, subdiv=subdiv, years=year)
    except (KeyError, NotImplementedError, AttributeError):
        # Country (or subdivision) not covered by the framework.
        return None
