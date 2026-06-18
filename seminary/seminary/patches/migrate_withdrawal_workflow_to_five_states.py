"""Migrate in-flight Withdrawal Requests to the streamlined 5-state workflow.

The Course Withdrawal workflow was collapsed from 8 states to 5:

    Draft -> Academic Review -> Financial Review -> Completed (+ Rejected)

The retired states (Submitted, Academically Approved, Financially Approved) and
the new ``refund_due`` gate field mean existing submitted requests must be
reconciled, or they'd be stranded in a state the workflow no longer defines and
the new Academic Review fork (Approve Academically vs. Conclude) would mis-route
on a defaulted refund_due=0.

State remap (side effects already applied on the old path are NOT re-run):
  - Submitted            -> Academic Review   (both pre-academic; nothing lost)
  - Academically Approved-> Financial Review  (academic already applied; let
                            finance conclude. For no-refund docs an Approve
                            Financially is a harmless no-op that then completes.)
  - Financially Approved -> Completed          (financial already applied; only
                            completion remains, so run process_completion to
                            finalize any program separation — the new model fires
                            it together with financial approval.)
  - Academic Review / Financial Review / Completed / Rejected / Draft: unchanged.

refund_due is recomputed for every non-terminal request (mirrors
WithdrawalRequest.set_refund_due) so the new transition conditions route
correctly. Idempotent: states already mapped match nothing; refund_due is
authoritative.
"""

import frappe

_NON_TERMINAL = (
    "Draft",
    "Submitted",
    "Academic Review",
    "Academically Approved",
    "Financial Review",
    "Financially Approved",
)


def _compute_refund_due(row):
    """1 when a refund is possible: a rule with refunds applies and not free."""
    if row.is_free or not row.withdrawal_rule:
        return 0
    has_refund = frappe.db.get_value(
        "Withdrawal Rules", row.withdrawal_rule, "has_refund"
    )
    if not has_refund:
        return 0
    refund_rows = frappe.db.count("Withdrawal Refunds", {"parent": row.withdrawal_rule})
    return 1 if refund_rows else 0


def execute():
    rows = frappe.db.sql(
        """SELECT name, workflow_state, is_free, withdrawal_rule
           FROM `tabWithdrawal Request`""",
        as_dict=True,
    )
    if not rows:
        print("No Withdrawal Request rows to migrate.")
        return

    remap = {
        "Submitted": "Academic Review",
        "Academically Approved": "Financial Review",
        "Financially Approved": "Completed",
    }
    counts = {"refund_due": 0, "remapped": 0, "completed_finalized": 0}

    for row in rows:
        # Recompute the gate field for anything still in flight.
        if row.workflow_state in _NON_TERMINAL:
            refund_due = _compute_refund_due(row)
            if refund_due:
                counts["refund_due"] += 1
            frappe.db.set_value(
                "Withdrawal Request",
                row.name,
                "refund_due",
                refund_due,
                update_modified=False,
            )

        target = remap.get(row.workflow_state)
        if not target:
            continue
        frappe.db.set_value(
            "Withdrawal Request",
            row.name,
            "workflow_state",
            target,
            update_modified=False,
        )
        counts["remapped"] += 1

        # A 'Financially Approved' request had its refund applied but never ran
        # completion. Finalize it now (idempotent for program separations).
        if target == "Completed":
            from seminary.seminary.withdrawal import process_completion

            doc = frappe.get_doc("Withdrawal Request", row.name)
            process_completion(doc)
            counts["completed_finalized"] += 1

    frappe.db.commit()
    print(
        f"Withdrawal workflow migration: remapped={counts['remapped']}, "
        f"refund_due set on {counts['refund_due']} in-flight request(s), "
        f"finalized {counts['completed_finalized']} completed separation(s)."
    )
