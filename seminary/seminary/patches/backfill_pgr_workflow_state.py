"""Backfill workflow_state on existing Program Graduation Requirement rows.

The 'Program Graduation Requirement Versioning' workflow (Draft -> Active ->
Superseded) was added in 2026-05. Existing rows had no `workflow_state`. We
map them from their current docstatus/active flag so the workflow engine shows
the right state and the 'Change Version' action becomes available:

- docstatus 1 + active 1  -> "Active"     (the live policy)
- docstatus 1 + active 0  -> "Superseded"  (already retired)
- docstatus 0             -> "Draft"
- docstatus 2 (cancelled) -> "Superseded"  (legacy cancellations = retired)

Authoritative reconciliation: the target is derived purely from
docstatus/active and applied unconditionally. A submitted-and-active policy
must be 'Active', never 'Draft' — so we overwrite any stale value (adding the
new `workflow_state` field can leave submitted rows defaulted to "Draft").
Idempotent: re-running yields the same mapping.
"""

import frappe


def execute():
    rows = frappe.db.sql(
        """SELECT name, docstatus, COALESCE(active, 0) AS active, workflow_state
           FROM `tabProgram Graduation Requirement`""",
        as_dict=True,
    )
    if not rows:
        print("No Program Graduation Requirement rows to reconcile.")
        return

    counts = {"Draft": 0, "Active": 0, "Superseded": 0}
    for row in rows:
        if row.docstatus == 0:
            target = "Draft"
        elif row.docstatus == 1 and row.active:
            target = "Active"
        else:  # submitted-but-inactive, or cancelled
            target = "Superseded"
        counts[target] += 1
        if row.workflow_state == target:
            continue
        frappe.db.set_value(
            "Program Graduation Requirement",
            row.name,
            "workflow_state",
            target,
            update_modified=False,
        )

    frappe.db.commit()
    print(
        f"Backfilled PGR workflow_state: "
        f"Draft={counts['Draft']}, Active={counts['Active']}, "
        f"Superseded={counts['Superseded']}."
    )
