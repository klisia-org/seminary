# Copyright (c) 2026, Klisia, Frappe Technologies and contributors
# For license information, please see license.txt

"""Unpaid Instructor Log — surfaces teaching rows that haven't been fully paid.

A row is "unpaid" when the sum of non-cancelled Salary Slip portions across
Instructor Log Payment is less than 100 AND the course's academic term has
ended. This report is the reconciliation backstop for the instructor pay
pipeline: it catches missed Payroll Entry runs, instructors without an
Employee link, and courses with missing Instructor Category.
"""

import frappe
from frappe import _
from frappe.utils import getdate, today


def execute(filters=None):
    filters = filters or {}
    columns = _columns()
    data = _rows(filters)
    return columns, data


def _columns():
    return [
        {
            "label": _("Instructor"),
            "fieldtype": "Link",
            "options": "Instructor",
            "fieldname": "instructor",
            "width": 160,
        },
        {
            "label": _("Course"),
            "fieldtype": "Link",
            "options": "Course Schedule",
            "fieldname": "course",
            "width": 200,
        },
        {
            "label": _("Academic Term"),
            "fieldtype": "Link",
            "options": "Academic Term",
            "fieldname": "academic_term",
            "width": 140,
        },
        {
            "label": _("Category"),
            "fieldtype": "Link",
            "options": "Instructor Category",
            "fieldname": "instructor_category",
            "width": 140,
        },
        {
            "label": _("Students"),
            "fieldtype": "Int",
            "fieldname": "n_students",
            "width": 80,
        },
        {
            "label": _("Term End"),
            "fieldtype": "Date",
            "fieldname": "term_end_date",
            "width": 100,
        },
        {
            "label": _("% Paid"),
            "fieldtype": "Percent",
            "fieldname": "paid_portion",
            "width": 80,
        },
        {
            "label": _("Log Row"),
            "fieldtype": "Data",
            "fieldname": "log_name",
            "width": 220,
        },
    ]


def _rows(filters):
    conditions = ["term.term_end_date < %(today)s"]
    params = {"today": filters.get("as_of") or today()}

    if filters.get("instructor"):
        conditions.append("log.parent = %(instructor)s")
        params["instructor"] = filters["instructor"]
    if filters.get("academic_term"):
        conditions.append("log.academic_term = %(academic_term)s")
        params["academic_term"] = filters["academic_term"]
    if filters.get("instructor_category"):
        conditions.append("log.instructor_category = %(instructor_category)s")
        params["instructor_category"] = filters["instructor_category"]

    where = " and ".join(conditions)

    return frappe.db.sql(
        f"""
        select
            log.parent as instructor,
            log.course,
            log.academic_term,
            log.instructor_category,
            log.n_students,
            term.term_end_date,
            coalesce((
                select sum(ilp.portion)
                from `tabInstructor Log Payment` ilp
                join `tabSalary Slip` ss on ss.name = ilp.salary_slip
                where ilp.instructor_log = log.name and ss.docstatus != 2
            ), 0) as paid_portion,
            log.name as log_name
        from `tabInstructor Log` log
        join `tabAcademic Term` term on term.name = log.academic_term
        where {where}
        having paid_portion < 100
        order by term.term_end_date desc, log.parent asc
        """,
        params,
        as_dict=True,
    )
