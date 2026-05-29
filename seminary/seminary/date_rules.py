# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Unified anchor + offset date resolver.

One place to turn an anchor date and a signed offset into a concrete date. This
is the single resolver behind every dated rule in the app (ADR 025):
- Culminating Project milestone due dates (`culminating_project.snapshot_milestones`)
- Course Schedule enrollment/grade windows (`cs_lifecycle.resolve_window_dates`)
- Term withdrawal deadlines (`withdrawal.calculate_dynamic_date`)
- Graduation requirement Time-Offset due dates (`graduation`)

`context` is a plain dict supplied by the caller:
    {
        "anchors": {"Project Start": date, "Enrollment Date": date, ...},
        "term": "Academic Term name",   # base term for term offsets (optional)
        "holidays": {date, ...},          # optional, for holiday_adjust
    }

Term offsets ("...Term" unit) walk whole Academic Terms: from `context["term"]`
when supplied, otherwise from the term that contains the resolved anchor date
(so a "-1 Term" offset from an arbitrary anchor lands on a real term start, not
a day approximation).
"""

from datetime import timedelta

import frappe
from frappe.utils import add_days, getdate

WEEKDAY_INDEX = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}


def resolve(
    anchor,
    offset_value,
    offset_unit,
    context,
    *,
    weekday=None,
    weekday_strict=False,
    holiday_adjust=None,
    clamp_to=None,
):
    """Return the resolved date, or None when the anchor can't be resolved.

    - term offset (offset_unit contains "Term"): walk `offset_value` Academic
      Terms from `context["term"]` (or the term containing the anchor date) and
      take that term's start date.
    - day offset (anything else): add `offset_value` days to the anchor date.

    Optional post-processing, applied in order: snap to `weekday` (set
    `weekday_strict=True` to always advance past the current weekday), nudge off
    a holiday (`context["holidays"]`), clamp to a max date.
    """
    offset_value = int(offset_value or 0)

    if offset_unit and "Term" in offset_unit:
        base_term = (context or {}).get("term")
        if not base_term:
            anchor_date = resolve_anchor(anchor, context)
            base_term = term_for_date(anchor_date) if anchor_date else None
        if not base_term:
            return None
        target_term = shift_term(base_term, offset_value)
        start = (
            frappe.db.get_value("Academic Term", target_term, "term_start_date")
            if target_term
            else None
        )
        result = getdate(start) if start else None
    else:  # day offset
        anchor_date = resolve_anchor(anchor, context)
        if not anchor_date:
            return None
        result = add_days(getdate(anchor_date), offset_value)

    if result is None:
        return None

    if weekday and weekday != "Any":
        result = snap_to_weekday(result, weekday, strict=weekday_strict)
    if holiday_adjust and holiday_adjust != "No adjustment":
        result = adjust_for_holidays(result, holiday_adjust, context)
    if clamp_to:
        clamp = getdate(clamp_to)
        if result > clamp:
            result = clamp
    return result


def resolve_anchor(anchor, context):
    """Look up an anchor's base date from the caller-supplied context dict."""
    anchors = (context or {}).get("anchors") or {}
    value = anchors.get(anchor)
    return getdate(value) if value else None


def snap_to_weekday(date_val, weekday, strict=False):
    """Move forward to the next occurrence of `weekday`.

    With `strict=False` (default) a date already on `weekday` stays put; with
    `strict=True` it advances a full week (matching the withdrawal-rule rule
    that the deadline falls on the *following* weekday)."""
    target = WEEKDAY_INDEX.get(weekday)
    if target is None:
        return date_val
    days_ahead = target - date_val.weekday()
    if days_ahead < 0 or (strict and days_ahead == 0):
        days_ahead += 7
    return date_val + timedelta(days=days_ahead)


def adjust_for_holidays(date_val, mode, context):
    """Nudge off a holiday by one day. Holidays come from `context['holidays']`."""
    holidays = (context or {}).get("holidays") or set()
    if date_val not in holidays:
        return date_val
    if mode == "Subtract one day":
        return date_val - timedelta(days=1)
    if mode == "Add one day":
        return date_val + timedelta(days=1)
    return date_val


def shift_term(term_name, n):
    """Walk `n` Academic Terms forward (n>0) or backward (n<0) by start date."""
    if not term_name or not n:
        return term_name
    ascending = n > 0
    remaining = abs(n)
    cursor = term_name
    while remaining > 0:
        nxt = next_term(cursor, ascending=ascending)
        if not nxt:
            break
        cursor = nxt
        remaining -= 1
    return cursor


def next_term(term_name, ascending=True):
    """The adjacent Academic Term by start date, or None at the boundary."""
    current_start = frappe.db.get_value("Academic Term", term_name, "term_start_date")
    if not current_start:
        return None
    operator, direction = (">", "asc") if ascending else ("<", "desc")
    row = frappe.get_all(
        "Academic Term",
        filters={"term_start_date": (operator, current_start)},
        order_by=f"term_start_date {direction}",
        limit=1,
        pluck="name",
    )
    return row[0] if row else None


def term_for_date(date_val):
    """The Academic Term whose [start, end] window covers `date_val`, or None.

    Used as the base term for a term offset when the caller doesn't pin an
    explicit `context["term"]`. Deliberately returns None (rather than guessing
    the nearest term) when no term covers the date — e.g. an anchor years out
    with no terms defined that far — so the caller yields no date instead of a
    misleading one."""
    if not date_val:
        return None
    date_val = getdate(date_val)
    covering = frappe.get_all(
        "Academic Term",
        filters={
            "term_start_date": ("<=", date_val),
            "term_end_date": (">=", date_val),
        },
        order_by="term_start_date desc",
        limit=1,
        pluck="name",
    )
    return covering[0] if covering else None
