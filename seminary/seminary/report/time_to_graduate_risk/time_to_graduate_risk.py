"""Time-to-Graduate Risk report.

Lists active program enrollments that have a max graduation date, showing
remaining credits, remaining time, and the minimum credits-per-year pace
the student needs to keep to make their cap. Ordered by required pace
descending so the most at-risk students surface first.

Excludes ongoing programs (no graduation concept) and graduated enrollments.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

# Sentinel used to keep overdue rows at the very top of the sort.
_OVERDUE_SENTINEL = 99_999.0


def execute(filters=None):
    if not filters:
        filters = {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "fieldname": "student",
            "label": _("Student"),
            "fieldtype": "Link",
            "options": "Student",
            "width": 160,
        },
        {
            "fieldname": "student_name",
            "label": _("Student Name"),
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "fieldname": "program",
            "label": _("Program"),
            "fieldtype": "Link",
            "options": "Program",
            "width": 150,
        },
        {
            "fieldname": "credits_earned",
            "label": _("Credits Earned"),
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "fieldname": "remaining_credits",
            "label": _("Remaining Credits"),
            "fieldtype": "Int",
            "width": 130,
        },
        {
            "fieldname": "max_graduation_date",
            "label": _("Max Graduation Date"),
            "fieldtype": "Date",
            "width": 140,
        },
        {
            "fieldname": "remaining_years",
            "label": _("Remaining Time (yrs)"),
            "fieldtype": "Float",
            "precision": 2,
            "width": 140,
        },
        {
            "fieldname": "min_credits_per_year",
            "label": _("Min Credits/Year"),
            "fieldtype": "Float",
            "precision": 2,
            "width": 140,
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "fieldname": "program_enrollment",
            "label": _("Program Enrollment"),
            "fieldtype": "Link",
            "options": "Program Enrollment",
            "width": 180,
        },
    ]


def get_data(filters):
    conditions = ["pe.docstatus = 1", "pe.max_graduation_date IS NOT NULL"]
    params = {}

    if filters.get("active_only"):
        conditions.append("pe.pgmenrol_active = 1")
        conditions.append("pe.date_of_conclusion IS NULL")

    if filters.get("program"):
        conditions.append("pe.program = %(program)s")
        params["program"] = filters["program"]

    where = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""SELECT pe.name AS program_enrollment,
                  pe.student,
                  pe.student_name,
                  pe.program,
                  COALESCE(pe.totalcredits, 0) AS credits_earned,
                  pe.max_graduation_date,
                  COALESCE(pgm.credits_complete, 0) AS credits_required
           FROM `tabProgram Enrollment` pe
           INNER JOIN `tabProgram` pgm ON pgm.name = pe.program
           WHERE {where}
             AND COALESCE(pgm.is_ongoing, 0) = 0""",
        params,
        as_dict=True,
    )

    today = getdate()
    data = []

    for row in rows:
        remaining_credits = max(0, row.credits_required - row.credits_earned)
        days_left = (getdate(row.max_graduation_date) - today).days
        remaining_years = max(0.0, days_left / 365.25)

        if remaining_credits <= 0:
            status = "Done"
            min_credits_per_year = 0.0
        elif remaining_years <= 0:
            status = "Overdue"
            min_credits_per_year = _OVERDUE_SENTINEL
        else:
            status = "Active"
            min_credits_per_year = remaining_credits / remaining_years

        data.append(
            {
                "student": row.student,
                "student_name": row.student_name,
                "program": row.program,
                "credits_earned": int(row.credits_earned),
                "remaining_credits": int(remaining_credits),
                "max_graduation_date": row.max_graduation_date,
                "remaining_years": flt(remaining_years, 2),
                "min_credits_per_year": flt(min_credits_per_year, 2),
                "status": status,
                "program_enrollment": row.program_enrollment,
            }
        )

    data.sort(key=lambda r: r["min_credits_per_year"], reverse=True)
    return data
