"""Term advancement moves to Send Grades (decisions/084).

- The Registrar's Advance Students block is retired: delete it and drop it
  from every Workspace that places it.
- `cohort_failure_policy` now has two options; every earlier value meant
  "nothing happens yet", which is the new default.
- A Time-based program may no longer be Self-paced. Such programs are listed
  in the Error Log for a person to decide, not changed here.
"""

import json

import frappe

BLOCK = "Registrar - Advance Students"
DEFAULT_POLICY = "Stay in the current cohort"
POLICIES = (DEFAULT_POLICY, "Remove from the current program cohort")


def execute():
    _retire_block()
    frappe.db.sql(
        "UPDATE `tabProgram` SET cohort_failure_policy = %s"
        " WHERE COALESCE(cohort_failure_policy, '') NOT IN %s",
        (DEFAULT_POLICY, POLICIES),
    )
    clash = frappe.get_all(
        "Program",
        filters={"program_type": "Time-based", "pacing_mode": "Self-paced"},
        pluck="name",
    )
    if clash:
        frappe.log_error(
            "These Time-based programs are Self-paced, which is now allowed only in "
            "Credits-based programs. Change the program type or the pacing mode: "
            + ", ".join(clash),
            "Self-paced Time-based programs",
        )


def _retire_block():
    for ws in frappe.get_all(
        "Workspace Custom Block", filters={"custom_block_name": BLOCK}, pluck="parent"
    ):
        doc = frappe.get_doc("Workspace", ws)
        doc.custom_blocks = [
            b for b in doc.custom_blocks if b.custom_block_name != BLOCK
        ]
        content = json.loads(doc.content or "[]")
        doc.content = json.dumps(
            [
                c
                for c in content
                if (c.get("data") or {}).get("custom_block_name") != BLOCK
            ]
        )
        doc.flags.ignore_permissions = True
        doc.save()
    if frappe.db.exists("Custom HTML Block", BLOCK):
        frappe.delete_doc(
            "Custom HTML Block", BLOCK, ignore_permissions=True, force=True
        )
