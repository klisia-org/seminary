# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Make Program.program_abbreviation and Course.coursecode slug-safe, present and unique.

These codes now flow into aretenic PLO/CLO codes and URLs, so they become mandatory,
unique and URL-safe (aretenic ADR 029/030). This runs **pre_model_sync** — before the
unique index + reqd are applied — so existing data is cleaned first and the schema change
lands without violating the new constraints. Already-clean, unique values are left
untouched (MDIV stays MDIV); blanks, dirty values and duplicates get a sanitized or
derived unique value the institution can refine later.
"""

import re

import frappe

from seminary.seminary.utils import url_safe_code


def execute():
    _backfill("Program", "program_abbreviation", "program_name")
    _backfill("Course", "coursecode", "course_name")
    frappe.db.commit()


def _acronym(name):
    """Best-effort short code from a name: initials of multi-word names, else the
    sanitized single word, capped to keep it abbreviation-sized."""
    words = re.findall(r"[A-Za-z0-9]+", name or "")
    if not words:
        return ""
    if len(words) == 1:
        return url_safe_code(words[0])[:12]
    return "".join(w[0] for w in words).upper()[:12]


def _backfill(doctype, field, name_field):
    if not frappe.db.has_column(doctype, field):
        return
    rows = frappe.get_all(doctype, fields=["name", field, name_field])

    used = set()
    pending = []
    # Pass 1: reserve values that are already clean, non-empty and not yet taken.
    for row in rows:
        raw = row.get(field) or ""
        clean = url_safe_code(raw)
        if clean and clean == raw and clean not in used:
            used.add(clean)
        else:
            pending.append(row)

    # Pass 2: assign a sanitized/derived, unique value to everything else.
    for row in pending:
        base = url_safe_code(row.get(field)) or _acronym(row.get(name_field)) or "CODE"
        value = base
        count = 1
        while value in used:
            count += 1
            value = f"{base}-{count}"
        used.add(value)
        if value != (row.get(field) or ""):
            frappe.db.set_value(
                doctype, row["name"], field, value, update_modified=False
            )
