"""Move Graduation Requirement Item off submit/cancel onto an Active/Retired workflow.

The Library was submittable (an earlier patch pushed every row to docstatus=1),
but cancellation is impossible while programs and student snapshots still
reference a row. It is now non-submittable with a Workflow (Active <-> Retired);
Retired hides a requirement from the Program Graduation Requirement picker
without breaking existing references.

This reconciles existing rows:
- docstatus 2 (any legacy cancellation) -> docstatus 0, workflow_state "Retired"
- docstatus 1 (the normal submitted rows) -> docstatus 0
- any row still without a workflow_state -> "Active"

Idempotent; never overwrites a row that is already Retired.
"""

import frappe


def execute():
    if not frappe.db.table_exists("Graduation Requirement Item"):
        return

    # Legacy cancellations become Retired (and drop to draft docstatus).
    frappe.db.sql(
        """UPDATE `tabGraduation Requirement Item`
           SET docstatus = 0, workflow_state = 'Retired'
           WHERE docstatus = 2"""
    )
    # Submitted rows drop back to draft — submit/cancel no longer exist.
    frappe.db.sql(
        "UPDATE `tabGraduation Requirement Item` SET docstatus = 0 WHERE docstatus = 1"
    )
    # Default everything still unset to Active (leaves Retired rows untouched).
    frappe.db.sql(
        """UPDATE `tabGraduation Requirement Item`
           SET workflow_state = 'Active'
           WHERE workflow_state IS NULL OR workflow_state = ''"""
    )
    frappe.db.commit()
    frappe.cache().delete_value("_seminary_grad_link_doctypes")
    print("Graduation Requirement Item: reset to draft and defaulted workflow_state.")
