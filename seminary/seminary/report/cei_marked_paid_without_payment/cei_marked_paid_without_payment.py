# Copyright (c) 2026, Klisia, Frappe Technologies and contributors
# For license information, please see license.txt

"""CEI Marked Paid Without Payment — audit report.

Surfaces Course Enrollment Individuals that reached "Submitted" because someone
explicitly clicked the "Mark as Paid" workflow action, but whose linked Sales
Invoices contain no actually-paid receivable.

Detection signal (robust against stale `is_free` / `require_pay_submit`
fields on older docs):

  1. CEI is Submitted or Concluded (docstatus=1). Concluded is included so an
     unpaid balance is not hidden once the course ends: Send Grades moves the
     CEI Submitted -> Concluded via `db.set_value` (leaving no workflow
     comment), so the "Mark as Paid" signal in steps 2-3 is unaffected.
  2. A Workflow Comment with content='Awaiting Payment' exists on the doc —
     the CEI passed through Awaiting Payment at some point.
  3. A later Workflow Comment with content='Submitted' exists — the only
     way a CEI moves out of Awaiting Payment via the workflow is the
     "Mark as Paid" action. The system-driven threshold advance in
     `cei_lifecycle._advance_cei_to_submitted` uses `db.set_value` and
     therefore leaves NO workflow comment, so this filter cleanly
     isolates manual overrides.
  4. No Sales Invoice linked via `custom_cei` is submitted, non-refund,
     and fully paid (outstanding_amount <= 0). Cancelled, deleted, return,
     or still-outstanding SIs all count as "no paid SI".

The `marked_paid_by` / `marked_paid_on` columns come from the owner and
creation timestamp of the latest 'Submitted' workflow comment — i.e. who
clicked "Mark as Paid", and when.
"""

import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}
    return _columns(), _rows(filters)


def _columns():
    return [
        {
            "label": _("CEI"),
            "fieldtype": "Link",
            "options": "Course Enrollment Individual",
            "fieldname": "cei",
            "width": 200,
        },
        {
            "label": _("Student"),
            "fieldtype": "Link",
            "options": "Student",
            "fieldname": "student",
            "width": 160,
        },
        {
            "label": _("Course"),
            "fieldtype": "Data",
            "fieldname": "course",
            "width": 160,
        },
        {
            "label": _("Program"),
            "fieldtype": "Data",
            "fieldname": "program",
            "width": 140,
        },
        {
            "label": _("Marked Paid By"),
            "fieldtype": "Link",
            "options": "User",
            "fieldname": "marked_paid_by",
            "width": 200,
        },
        {
            "label": _("Marked Paid On"),
            "fieldtype": "Datetime",
            "fieldname": "marked_paid_on",
            "width": 160,
        },
        {
            "label": _("Invoiced"),
            "fieldtype": "Currency",
            "fieldname": "total_invoiced",
            "width": 110,
        },
        {
            "label": _("Paid"),
            "fieldtype": "Currency",
            "fieldname": "total_paid",
            "width": 110,
        },
        {
            "label": _("Paid %"),
            "fieldtype": "Percent",
            "fieldname": "paid_percent",
            "width": 80,
        },
        {
            "label": _("SIs (Submitted)"),
            "fieldtype": "Int",
            "fieldname": "si_submitted",
            "width": 110,
        },
        {
            "label": _("SIs (Cancelled)"),
            "fieldtype": "Int",
            "fieldname": "si_cancelled",
            "width": 110,
        },
        {
            "label": _("SIs (Returns)"),
            "fieldtype": "Int",
            "fieldname": "si_returns",
            "width": 100,
        },
        # Hidden field used by the dashboard Number Card (Sum of 1-per-row).
        {
            "label": _("Count"),
            "fieldtype": "Int",
            "fieldname": "row_count",
            "width": 1,
            "hidden": 1,
        },
    ]


def _rows(filters):
    conditions = [
        "cei.workflow_state IN ('Submitted', 'Concluded')",
        "cei.docstatus = 1",
    ]
    params = {}

    if filters.get("from_date"):
        conditions.append("mark.creation >= %(from_date)s")
        params["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        # Include the entire to_date day.
        conditions.append("mark.creation < DATE_ADD(%(to_date)s, INTERVAL 1 DAY)")
        params["to_date"] = filters["to_date"]
    if filters.get("marked_paid_by"):
        conditions.append("mark.owner = %(marked_paid_by)s")
        params["marked_paid_by"] = filters["marked_paid_by"]
    if filters.get("program"):
        conditions.append("cei.program_data = %(program)s")
        params["program"] = filters["program"]

    where = " AND ".join(conditions)

    # `mark` is the latest 'Submitted' workflow comment on the CEI — its
    # owner/creation identify the "Mark as Paid" actor. `EXISTS (...ap...)`
    # ensures the CEI sat in Awaiting Payment beforehand, so this isn't a
    # plain Draft → Submitted transition on a free / no-pay-required doc.
    sql = f"""
        SELECT
            cei.name AS cei,
            cei.student_ce AS student,
            cei.course_data AS course,
            cei.program_data AS program,
            mark.owner AS marked_paid_by,
            mark.creation AS marked_paid_on,
            cei.total_invoiced,
            cei.total_paid,
            cei.paid_percent,
            (
                SELECT COUNT(*) FROM `tabSales Invoice` si
                WHERE si.custom_cei = cei.name
                  AND si.docstatus = 1
                  AND si.is_return = 0
            ) AS si_submitted,
            (
                SELECT COUNT(*) FROM `tabSales Invoice` si
                WHERE si.custom_cei = cei.name
                  AND si.docstatus = 2
            ) AS si_cancelled,
            (
                SELECT COUNT(*) FROM `tabSales Invoice` si
                WHERE si.custom_cei = cei.name
                  AND si.is_return = 1
            ) AS si_returns,
            1 AS row_count
        FROM `tabCourse Enrollment Individual` cei
        JOIN (
            SELECT c.reference_name, c.owner, c.creation
            FROM `tabComment` c
            JOIN (
                SELECT reference_name, MAX(creation) AS max_creation
                FROM `tabComment`
                WHERE comment_type = 'Workflow'
                  AND reference_doctype = 'Course Enrollment Individual'
                  AND content = 'Submitted'
                GROUP BY reference_name
            ) latest
              ON latest.reference_name = c.reference_name
             AND latest.max_creation = c.creation
            WHERE c.comment_type = 'Workflow'
              AND c.reference_doctype = 'Course Enrollment Individual'
              AND c.content = 'Submitted'
        ) mark ON mark.reference_name = cei.name
        WHERE {where}
          AND EXISTS (
              SELECT 1 FROM `tabComment` ap
              WHERE ap.comment_type = 'Workflow'
                AND ap.reference_doctype = 'Course Enrollment Individual'
                AND ap.reference_name = cei.name
                AND ap.content = 'Awaiting Payment'
                AND ap.creation < mark.creation
          )
          AND NOT EXISTS (
              SELECT 1 FROM `tabSales Invoice` si
              WHERE si.custom_cei = cei.name
                AND si.docstatus = 1
                AND si.is_return = 0
                AND si.outstanding_amount <= 0
          )
        ORDER BY mark.creation DESC
    """

    return frappe.db.sql(sql, params, as_dict=True)
