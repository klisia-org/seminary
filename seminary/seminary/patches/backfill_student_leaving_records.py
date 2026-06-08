# Copyright (c) 2026, Murilo R. Melo and contributors
# For license information, please see license.txt
"""Backfill Student Leaving Records for Program Enrollments that went terminal
before the leaving-record feature existed (or via paths that did not record one).

For each PE in a terminal status without a Leaving Record, derive the row from
the PE's terminal status-history entry (effective date + originating Withdrawal
Request) and write it via the same upsert the live spine uses.
"""

import frappe
from seminary.seminary.program_status import TERMINAL_STATUSES, _upsert_leaving_record


def execute():
    if not frappe.db.table_exists("Student Leaving Record"):
        return

    pes = frappe.get_all(
        "Program Enrollment",
        filters={"status": ["in", list(TERMINAL_STATUSES)]},
        fields=["name", "student", "status"],
    )
    for pe in pes:
        if not pe.student:
            continue
        if frappe.db.exists(
            "Student Leaving Record",
            {
                "parent": pe.student,
                "parentfield": "leaving_records",
                "program_enrollment": pe.name,
            },
        ):
            continue

        hist = frappe.get_all(
            "Program Enrollment Status History",
            filters={"parent": pe.name, "to_status": pe.status},
            fields=["effective_date", "source_doctype", "source_name"],
            order_by="effective_date desc, idx desc",
            limit=1,
        )
        h = hist[0] if hist else {}
        pe_doc = frappe.get_doc("Program Enrollment", pe.name)
        _upsert_leaving_record(
            pe_doc,
            pe.status,
            h.get("effective_date"),
            h.get("source_doctype"),
            h.get("source_name"),
        )

    frappe.db.commit()
