"""Backfill `max_graduation_date` on existing Program Enrollments.

For every submitted PE whose Program has `max_time_enrolled > 0` but where
`max_graduation_date` is empty, compute and set it from
`enrollment_date + (max_time_enrolled × 365.25) days`. Skips ongoing programs
(no graduation concept) and rows that already have a value.

Idempotent.
"""

import frappe
from frappe.utils import add_days


def execute():
    rows = frappe.db.sql(
        """SELECT pe.name AS pe_name,
                  pe.enrollment_date,
                  pgm.max_time_enrolled
           FROM `tabProgram Enrollment` pe
           INNER JOIN `tabProgram` pgm ON pgm.name = pe.program
           WHERE pe.docstatus = 1
             AND (pe.max_graduation_date IS NULL OR pe.max_graduation_date = '')
             AND COALESCE(pgm.max_time_enrolled, 0) > 0
             AND COALESCE(pgm.is_ongoing, 0) = 0
             AND pe.enrollment_date IS NOT NULL""",
        as_dict=True,
    )
    if not rows:
        print("No Program Enrollments need max_graduation_date backfill.")
        return

    for row in rows:
        years = float(row.max_time_enrolled or 0)
        days = int(round(years * 365.25))
        max_date = add_days(row.enrollment_date, days)
        frappe.db.set_value(
            "Program Enrollment",
            row.pe_name,
            "max_graduation_date",
            max_date,
            update_modified=False,
        )

    frappe.db.commit()
    print(f"Backfilled max_graduation_date on {len(rows)} Program Enrollment(s).")
