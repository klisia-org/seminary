# Copyright (c) 2026, Klisia, Frappe Technologies and contributors
# For license information, please see license.txt

"""Salary Slip integration for Seminary instructors.

Gated by ``Seminary Settings.hrms_enable``. Populates:

* ``computed_instructor_pay`` — single Currency field that the stock
  "Instructor Pay" Salary Component reads verbatim as its formula.
* ``instructor_log_summary`` — child table with per (category, event) rows for
  audit (category, courses, students, event, portion, rate, subtotal).
* Pilot fields ``courses_<slug>`` / ``students_<slug>`` — kept for reports.

On submit, mirrors every ``instructor_log_summary`` row into ``Instructor Log
Payment`` so re-runs of Payroll Entry do not double-pay. On cancel, removes
those rows.
"""

from collections import defaultdict

import frappe
from frappe.utils import flt, getdate

from seminary.seminary.doctype.instructor_category.instructor_category import (
    resolve_rate,
)


BASE_CUSTOM_FIELDS = {
    "Salary Slip": [
        {
            "fieldname": "instructor_section",
            "fieldtype": "Section Break",
            "label": "Instructor Pay Inputs",
            "insert_after": "employee_name",
            "collapsible": 1,
        },
        {
            "fieldname": "instructor",
            "fieldtype": "Link",
            "label": "Instructor",
            "options": "Instructor",
            "insert_after": "instructor_section",
            "read_only": 1,
        },
        {
            "fieldname": "computed_instructor_pay",
            "fieldtype": "Currency",
            "label": "Computed Instructor Pay",
            "insert_after": "instructor",
            "read_only": 1,
            "description": (
                "Sum of rate × count for every Instructor Log row paid on this "
                "slip. Referenced verbatim by the 'Instructor Pay' Salary "
                "Component formula."
            ),
        },
        {
            "fieldname": "instructor_log_summary",
            "fieldtype": "Table",
            "label": "Instructor Log Summary",
            "options": "Salary Slip Instructor Summary",
            "insert_after": "computed_instructor_pay",
            "read_only": 1,
            "description": (
                "Read-only audit: one row per (category, event) paid on this "
                "slip, with the rate applied and subtotal."
            ),
        },
    ],
}


INSTRUCTOR_PAY_COMPONENT = {
    "doctype": "Salary Component",
    "name": "Instructor Pay",
    "salary_component": "Instructor Pay",
    "salary_component_abbr": "IPAY",
    "type": "Earning",
    "depends_on_payment_days": 0,
    "is_tax_applicable": 0,
    "condition": "",
    "formula": "computed_instructor_pay",
    "amount_based_on_formula": 1,
    "disabled": 0,
    "description": (
        "Auto-created by Seminary when HRMS is enabled. Reads "
        "computed_instructor_pay populated from Instructor Log × Instructor "
        "Category rates. Safe to rename or tune; Seminary will not overwrite."
    ),
}


# ---------------------------------------------------------------------------
# Lifecycle hooks registered in hooks.py
# ---------------------------------------------------------------------------


def populate_instructor_summary(doc, method=None):
    """Salary Slip before_validate hook — compute per-category pay and audit rows.

    Runs before HRMS's own ``validate`` so Salary Component formulas can read
    ``computed_instructor_pay`` during ``calculate_net_pay``.
    """
    if not _hrms_enabled():
        return
    if not getattr(doc, "employee", None):
        return

    instructor = frappe.db.get_value("Instructor", {"employee": doc.employee}, "name")
    if not instructor:
        return

    doc.instructor = instructor

    settings = frappe.get_cached_doc("Seminary Settings")
    split_policy = settings.instructor_payment_split or "End of period"
    cutoff = getdate(settings.hrms_live_date) if settings.hrms_live_date else None
    slip_start = getdate(doc.start_date)
    slip_end = getdate(doc.end_date)

    log_rows = _fetch_instructor_log_rows(instructor, cutoff)

    # Reset flat counters so stale values don't leak between runs.
    for category in frappe.get_all("Instructor Category", pluck="name"):
        slug = frappe.scrub(category)
        doc.set(f"courses_{slug}", 0)
        doc.set(f"students_{slug}", 0)
    doc.set("instructor_log_summary", [])

    # Pilot flat counters — "coursework in period" semantics: count every log
    # row whose term overlaps the slip period, independent of whether pay is
    # released on this slip.
    totals_by_slug: dict[str, dict[str, int]] = defaultdict(
        lambda: {"courses": 0, "students": 0}
    )
    for row in log_rows:
        if not _term_overlaps_slip(row, slip_start, slip_end):
            continue
        slug = frappe.scrub(row.instructor_category)
        totals_by_slug[slug]["courses"] += 1
        totals_by_slug[slug]["students"] += int(row.n_students or 0)
    for slug, totals in totals_by_slug.items():
        doc.set(f"courses_{slug}", totals["courses"])
        doc.set(f"students_{slug}", totals["students"])

    # Event-based pay: one Instructor Log × event → (potentially multiple)
    # summary rows (one per applicable pay_mode). Anti-double-pay via
    # Instructor Log Payment means the first qualifying slip sweeps in
    # anything that was missed on earlier runs.
    grand_total = 0.0
    for row in log_rows:
        events = _events_for_row(row, split_policy, slip_start, slip_end)
        if not events:
            continue
        paid_events = _events_already_paid_excluding_self(row.name, doc.name)
        for event, portion in events:
            if event in paid_events:
                continue
            rate_lines = _rate_lines_for_category(row.instructor_category, row)
            if not rate_lines:
                continue
            for pay_mode, amount, count in rate_lines:
                subtotal = flt(amount) * count * (portion / 100.0)
                if not subtotal:
                    continue
                grand_total += subtotal
                doc.append(
                    "instructor_log_summary",
                    {
                        "instructor_log": row.name,
                        "course": row.course,
                        "instructor_category": row.instructor_category,
                        "pay_mode": pay_mode,
                        "courses_count": 1 if pay_mode == "Per-Course" else 0,
                        "students_count": (
                            row.n_students if pay_mode == "Per-Student" else 0
                        ),
                        "payment_event": event,
                        "portion": portion,
                        "rate_applied": amount,
                        "subtotal": subtotal,
                    },
                )

    doc.computed_instructor_pay = grand_total


def post_submit_instructor_log_payments(doc, method=None):
    """Salary Slip on_submit — create Instructor Log Payment rows for audit/anti-double-pay."""
    if not _hrms_enabled():
        return
    if not getattr(doc, "instructor", None):
        return

    # One Instructor Log Payment per (log_row, event). Summary rows with the
    # same (log_row, event) but different pay_modes (Per-Course + Per-Student)
    # collapse into a single payment whose amount is the sum.
    collapsed: dict[tuple[str, str], dict] = {}
    for summary in doc.get("instructor_log_summary", []):
        if not summary.instructor_log:
            continue
        event = summary.payment_event or "Full"
        key = (summary.instructor_log, event)
        entry = collapsed.setdefault(
            key,
            {
                "amount": 0.0,
                "portion": summary.portion or 100,
            },
        )
        entry["amount"] += flt(summary.subtotal)

    for (log_row, event), entry in collapsed.items():
        if frappe.db.exists(
            "Instructor Log Payment",
            {"instructor_log": log_row, "payment_event": event},
        ):
            continue
        frappe.get_doc(
            {
                "doctype": "Instructor Log Payment",
                "instructor_log": log_row,
                "salary_slip": doc.name,
                "payment_event": event,
                "portion": entry["portion"],
                "amount": entry["amount"],
                "currency": doc.currency,
                "posting_date": doc.posting_date or doc.end_date,
            }
        ).insert(ignore_permissions=True)


def cancel_instructor_log_payments(doc, method=None):
    """Salary Slip on_cancel — drop Instructor Log Payment rows for this slip."""
    frappe.db.delete("Instructor Log Payment", {"salary_slip": doc.name})


# ---------------------------------------------------------------------------
# Setup helpers (called from Seminary Settings.on_update)
# ---------------------------------------------------------------------------


def ensure_custom_fields():
    """Provision Salary Slip custom fields required by the instructor pay pipeline."""
    if "hrms" not in frappe.get_installed_apps():
        frappe.throw(
            "The HRMS app is not installed. Install it before enabling HRMS payroll."
        )

    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields(_build_custom_fields(), update=True)


def ensure_salary_components():
    """Create the 'Instructor Pay' Salary Component if missing. Idempotent."""
    if "hrms" not in frappe.get_installed_apps():
        return
    if frappe.db.exists("Salary Component", INSTRUCTOR_PAY_COMPONENT["name"]):
        return
    frappe.get_doc(dict(INSTRUCTOR_PAY_COMPONENT)).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _build_custom_fields() -> dict:
    fields = [dict(f) for f in BASE_CUSTOM_FIELDS["Salary Slip"]]
    previous = "instructor_log_summary"
    for category in frappe.get_all(
        "Instructor Category", pluck="name", order_by="creation"
    ):
        slug = frappe.scrub(category)
        fields.append(
            {
                "fieldname": f"courses_{slug}",
                "fieldtype": "Int",
                "label": f"Courses — {category}",
                "insert_after": previous,
                "read_only": 1,
                "non_negative": 1,
                "default": "0",
            }
        )
        previous = f"courses_{slug}"
        fields.append(
            {
                "fieldname": f"students_{slug}",
                "fieldtype": "Int",
                "label": f"Students — {category}",
                "insert_after": previous,
                "read_only": 1,
                "non_negative": 1,
                "default": "0",
            }
        )
        previous = f"students_{slug}"
    return {"Salary Slip": fields}


def _hrms_enabled() -> bool:
    if "hrms" not in frappe.get_installed_apps():
        return False
    return bool(frappe.db.get_single_value("Seminary Settings", "hrms_enable"))


def _fetch_instructor_log_rows(instructor: str, cutoff=None) -> list:
    """Return one canonical log row per (course, instructor_category).

    - Uses Course Schedule's own ``c_datestart`` / ``c_dateend`` when
      populated (for intensives inside a term); falls back to Academic Term.
    - Applies the ``hrms_live_date`` cutoff on the resolved course start.
    - Dedups duplicate log rows from stale ``update_instructorlog`` runs,
      keeping the row with the greatest ``n_students`` (most recent roster).
    """
    rows = frappe.db.sql(
        """
        select log.name, log.course, log.instructor_category,
               coalesce(log.n_students, 0) as n_students,
               term.name as academic_term,
               term.term_start_date, term.term_end_date,
               cs.c_datestart, cs.c_dateend
        from `tabInstructor Log` log
        join `tabAcademic Term` term on term.name = log.academic_term
        left join `tabCourse Schedule` cs on cs.name = log.course
        where log.parent = %s
          and log.instructor_category is not null
          and log.instructor_category != ''
        """,
        instructor,
        as_dict=True,
    )

    # Resolve effective course dates — Course Schedule wins over Academic Term
    # so intensives with their own run dates compute correctly.
    cutoff_date = getdate(cutoff) if cutoff else None
    resolved: dict[tuple[str, str], frappe._dict] = {}
    for r in rows:
        course_start = r.c_datestart or r.term_start_date
        course_end = r.c_dateend or r.term_end_date or course_start
        if not course_start:
            continue
        if cutoff_date and getdate(course_start) < cutoff_date:
            continue

        r.course_start = course_start
        r.course_end = course_end

        key = (r.course, r.instructor_category)
        existing = resolved.get(key)
        if existing is None or (r.n_students or 0) > (existing.n_students or 0):
            resolved[key] = r

    return list(resolved.values())


def _term_overlaps_slip(row, slip_start, slip_end) -> bool:
    """True if the course's effective date range overlaps the slip period."""
    start = getdate(row.course_start) if row.course_start else None
    end = getdate(row.course_end) if row.course_end else start
    if not start and not end:
        return False
    start = start or end
    end = end or start
    return start <= slip_end and end >= slip_start


def _events_for_row(
    row, split_policy: str, slip_start, slip_end
) -> list[tuple[str, float]]:
    """Return list of (event, portion) tuples applicable to this slip.

    Semantics: an event "qualifies" on a slip whose ``end_date`` is at or past
    the triggering course date. Anti-double-pay (via Instructor Log Payment)
    ensures each event is only emitted on the first qualifying slip, so a
    payroll run that follows a missed month naturally catches up. The
    ``hrms_live_date`` cutoff already filtered rows earlier, so "catch-up"
    only covers post-cutoff courses.
    """
    course_start = getdate(row.course_start) if row.course_start else None
    course_end = getdate(row.course_end) if row.course_end else course_start

    events: list[tuple[str, float]] = []
    if split_policy == "50% at start + 50% at end":
        if course_start and course_start <= slip_end:
            events.append(("Start", 50.0))
        if course_end and course_end <= slip_end:
            events.append(("End", 50.0))
    else:  # "End of period" — default
        if course_end and course_end <= slip_end:
            events.append(("End", 100.0))
    return events


def _rate_lines_for_category(category: str, log_row) -> list[tuple[str, float, int]]:
    """Return list of (pay_mode, amount, count) for the rate historically
    active on the course's effective start date."""
    if not category:
        return []
    target = getdate(log_row.course_start)
    lines: list[tuple[str, float, int]] = []
    for pay_mode in ("Per-Course", "Per-Student"):
        rate = resolve_rate(category, pay_mode, target)
        if not rate:
            continue
        count = 1 if pay_mode == "Per-Course" else int(log_row.n_students or 0)
        if count <= 0:
            continue
        lines.append((pay_mode, float(rate["amount"] or 0), count))
    return lines


def _events_already_paid_excluding_self(
    log_row: str, slip_name: str | None
) -> set[str]:
    """Events already posted for log_row on a non-cancelled slip other than this one."""
    rows = frappe.db.sql(
        """
        select ilp.payment_event
        from `tabInstructor Log Payment` ilp
        join `tabSalary Slip` ss on ss.name = ilp.salary_slip
        where ilp.instructor_log = %s
          and ss.docstatus != 2
          and (ss.name != %s or %s is null)
        """,
        (log_row, slip_name or "", slip_name),
    )
    return {r[0] for r in rows}
