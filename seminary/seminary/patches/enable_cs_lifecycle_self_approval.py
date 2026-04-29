"""Enable self-approval on Course Schedule Lifecycle workflow transitions.

Without allow_self_approval, an Academics User who created a Course Schedule
cannot trigger the workflow buttons (Open Enrollment, Close Enrollment,
Begin Grading) on that document — Frappe's form silently hides them.

Run via bench migrate (registered in patches.txt) or directly:
    bench --site <site> execute seminary.seminary.patches.enable_cs_lifecycle_self_approval.execute
"""

import frappe


WORKFLOW_NAME = "Course Schedule Lifecycle"
ACTIONS = {"Open Enrollment", "Close Enrollment", "Begin Grading"}


def execute():
    if not frappe.db.exists("Workflow", WORKFLOW_NAME):
        print(f"{WORKFLOW_NAME} not found. Skipping.")
        return

    workflow = frappe.get_doc("Workflow", WORKFLOW_NAME)
    changed = False
    for transition in workflow.transitions:
        if transition.action in ACTIONS and not transition.allow_self_approval:
            transition.allow_self_approval = 1
            changed = True

    if not changed:
        print("Self-approval already enabled. Skipping.")
        return

    workflow.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"Enabled self-approval on {WORKFLOW_NAME} transitions.")
