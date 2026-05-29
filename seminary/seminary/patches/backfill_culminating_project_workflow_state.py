"""Map existing Culminating Project rows onto the slimmed lifecycle (ADR 025).

The 9-state workflow (Proposal Submitted / Drafting / Revisions Required /
Approved / Defended / ...) collapsed to a type-agnostic lifecycle:
Draft -> Active -> Under Review -> Completed (+ Rejected / Withdrawn). The rich
proposal/drafting/defense detail now lives in milestones, not workflow states.

Mapping:
- Draft                                              -> Draft
- Proposal Submitted / Proposal Approved /
  Drafting / Revisions Required                      -> Active
- Under Review / Approved / Defended                 -> Under Review
- Completed                                          -> Completed
- Rejected                                           -> Rejected

Existing projects predate milestones, so `milestones_complete` is set to 1 (no
mandatory milestones to satisfy) — otherwise their Complete action would be
gated until the next save recomputes it. Idempotent.
"""

import frappe

_MAP = {
    "Proposal Submitted": "Active",
    "Proposal Approved": "Active",
    "Drafting": "Active",
    "Revisions Required": "Active",
    "Approved": "Under Review",
    "Defended": "Under Review",
}


def execute():
    rows = frappe.db.sql(
        "SELECT name, workflow_state FROM `tabCulminating Project`",
        as_dict=True,
    )
    for row in rows:
        target = _MAP.get(row.workflow_state)
        if target and target != row.workflow_state:
            frappe.db.set_value(
                "Culminating Project",
                row.name,
                "workflow_state",
                target,
                update_modified=False,
            )

    # Projects created before the milestone model have no mandatory milestones.
    frappe.db.sql(
        """UPDATE `tabCulminating Project` cp
           SET cp.milestones_complete = 1
           WHERE NOT EXISTS (
               SELECT 1 FROM `tabCulminating Project Milestone` m
               WHERE m.parent = cp.name AND m.parenttype = 'Culminating Project'
           )"""
    )
    frappe.db.commit()
    print(f"Reconciled {len(rows)} Culminating Project workflow states.")
