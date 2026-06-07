"""Backfill the program-status spine on existing Program Enrollments.

For every PE with an empty `status`, derive the lifecycle status from the
legacy `pgmenrol_active` flag (Active when 1, else Withdrawn — the only legacy
terminal cause was Full Program Withdrawal) and seed one Status History row.

Idempotent: skips PEs that already have a `status` or any history row.
See ADR 030.
"""

import frappe


def execute():
    rows = frappe.db.sql(
        """SELECT pe.name AS pe_name,
                  pe.pgmenrol_active,
                  pe.modified
           FROM `tabProgram Enrollment` pe
           WHERE (pe.status IS NULL OR pe.status = '')""",
        as_dict=True,
    )
    if not rows:
        print("No Program Enrollments need status backfill.")
        return

    seeded = 0
    for row in rows:
        status = "Active" if row.pgmenrol_active else "Withdrawn"

        frappe.db.set_value(
            "Program Enrollment",
            row.pe_name,
            "status",
            status,
            update_modified=False,
        )

        # Seed a single history row only when none exists yet.
        has_history = frappe.db.exists(
            "Program Enrollment Status History",
            {"parent": row.pe_name, "parentfield": "status_history"},
        )
        if has_history:
            continue

        idx = (
            frappe.db.count(
                "Program Enrollment Status History",
                {"parent": row.pe_name, "parentfield": "status_history"},
            )
            + 1
        )
        history = frappe.get_doc(
            {
                "doctype": "Program Enrollment Status History",
                "parent": row.pe_name,
                "parenttype": "Program Enrollment",
                "parentfield": "status_history",
                "idx": idx,
                "effective_date": frappe.utils.getdate(row.modified),
                "from_status": "",
                "to_status": status,
                "category": "System",
                "reason": "Backfilled from pgmenrol_active",
                "actor": "Administrator",
            }
        )
        history.db_insert()
        seeded += 1

    frappe.db.commit()
    print(
        f"Backfilled status on {len(rows)} Program Enrollment(s); "
        f"seeded {seeded} history row(s)."
    )
