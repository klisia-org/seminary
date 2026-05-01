"""Backfill workflow_state on existing Course Enrollment Individual rows.

The Course Enrollment Lifecycle workflow was added in 2026-05. Existing
rows had no `workflow_state` value before this. We map them as follows:

- docstatus 1 + withdrawn=1  → "Withdrawn"
- docstatus 1 + withdrawn=0  → "Submitted" (assume legacy CEIs are enrolled)
- docstatus 0                 → "Draft"

The forward-only assumption: legacy CEIs that may have unpaid invoices
should NOT be moved to "Awaiting Payment" — they were submitted under the
old non-gated model and are functionally enrolled.

Idempotent: only updates rows whose workflow_state is empty or null.
"""

import frappe


def execute():
    rows = frappe.db.sql(
        """SELECT name, docstatus, COALESCE(withdrawn, 0) AS withdrawn
           FROM `tabCourse Enrollment Individual`
           WHERE workflow_state IS NULL OR workflow_state = ''""",
        as_dict=True,
    )
    if not rows:
        print("No CEI rows need workflow_state backfill.")
        return

    counts = {"Draft": 0, "Submitted": 0, "Withdrawn": 0}
    for row in rows:
        if row.docstatus == 0:
            target = "Draft"
        elif row.withdrawn:
            target = "Withdrawn"
        else:
            target = "Submitted"
        frappe.db.set_value(
            "Course Enrollment Individual",
            row.name,
            "workflow_state",
            target,
            update_modified=False,
        )
        counts[target] += 1

    frappe.db.commit()
    print(
        f"Backfilled CEI workflow_state: "
        f"Draft={counts['Draft']}, Submitted={counts['Submitted']}, "
        f"Withdrawn={counts['Withdrawn']}."
    )
