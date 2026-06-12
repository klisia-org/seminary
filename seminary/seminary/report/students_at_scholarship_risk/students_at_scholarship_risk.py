# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Students at Scholarship Risk.

Lists active Scholarship Awards against their retention criteria — current GPA
and current-term credits versus the scholarship's required minimums — ranked so
the students furthest below a threshold (proportionally) appear first. Mirrors the
daily retention review's measures, but on demand and sortable for the registrar.
"""

import frappe
from frappe import _
from frappe.utils import flt

from seminary.seminary.scholarship import _retention_term, _term_credits

# Sentinel so a missing requirement never makes a student look "at risk".
_SAFE = float("inf")


def execute(filters=None):
    filters = frappe._dict(filters or {})
    term = _retention_term()

    award_filters = {"workflow_state": "Active"}
    if filters.scholarship:
        award_filters["scholarship"] = filters.scholarship
    if filters.program:
        award_filters["program"] = filters.program

    awards = frappe.get_all(
        "Scholarship Award",
        filters=award_filters,
        fields=[
            "name",
            "student",
            "student_name",
            "program",
            "scholarship",
            "program_enrollment",
            "retention_status",
        ],
    )

    data = []
    for a in awards:
        crit = (
            frappe.db.get_value(
                "Scholarships",
                a.scholarship,
                ["retain_min_gpa", "retain_min_credits_per_term"],
                as_dict=True,
            )
            or frappe._dict()
        )
        min_gpa = flt(crit.retain_min_gpa or 0)
        min_credits = int(crit.retain_min_credits_per_term or 0)
        current_gpa = flt(
            frappe.db.get_value(
                "Program Enrollment", a.program_enrollment, "current_gpa"
            )
        )
        current_credits = _term_credits(a.program_enrollment, term)

        gpa_gap = round(current_gpa - min_gpa, 2) if min_gpa else None
        credits_gap = (current_credits - min_credits) if min_credits else None

        # Proportional shortfall (gap as a fraction of the requirement) makes GPA and
        # credits comparable for ranking; smallest (most negative) = most at risk.
        gpa_norm = (gpa_gap / min_gpa) if min_gpa else _SAFE
        credits_norm = (credits_gap / min_credits) if min_credits else _SAFE
        risk = min(gpa_norm, credits_norm)
        below = (gpa_gap is not None and gpa_gap < 0) or (
            credits_gap is not None and credits_gap < 0
        )

        if filters.only_at_risk and not below:
            continue

        data.append(
            {
                "student": a.student,
                "student_name": a.student_name,
                "program": a.program,
                "scholarship": a.scholarship,
                "current_gpa": current_gpa,
                "min_gpa": min_gpa or None,
                "gpa_gap": gpa_gap,
                "current_credits": current_credits,
                "min_credits": min_credits or None,
                "credits_gap": credits_gap,
                "retention_status": a.retention_status,
                "_risk": risk,
            }
        )

    data.sort(key=lambda r: r["_risk"])
    for r in data:
        r.pop("_risk", None)

    columns = [
        {
            "label": _("Student"),
            "fieldname": "student",
            "fieldtype": "Link",
            "options": "Student",
            "width": 110,
        },
        {
            "label": _("Name"),
            "fieldname": "student_name",
            "fieldtype": "Data",
            "width": 170,
        },
        {
            "label": _("Program"),
            "fieldname": "program",
            "fieldtype": "Link",
            "options": "Program",
            "width": 160,
        },
        {
            "label": _("Scholarship"),
            "fieldname": "scholarship",
            "fieldtype": "Link",
            "options": "Scholarships",
            "width": 200,
        },
        {
            "label": _("Current GPA"),
            "fieldname": "current_gpa",
            "fieldtype": "Float",
            "precision": 2,
            "width": 100,
        },
        {
            "label": _("Min GPA"),
            "fieldname": "min_gpa",
            "fieldtype": "Float",
            "precision": 2,
            "width": 90,
        },
        {
            "label": _("GPA Gap"),
            "fieldname": "gpa_gap",
            "fieldtype": "Float",
            "precision": 2,
            "width": 90,
        },
        {
            "label": _("Credits / Term"),
            "fieldname": "current_credits",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": _("Min Credits"),
            "fieldname": "min_credits",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": _("Credits Gap"),
            "fieldname": "credits_gap",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": _("Retention"),
            "fieldname": "retention_status",
            "fieldtype": "Data",
            "width": 100,
        },
    ]
    return columns, data
