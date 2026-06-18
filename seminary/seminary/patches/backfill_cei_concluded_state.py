"""Backfill the new 'Concluded' terminal state on Course Enrollment Individual.

The Course Enrollment Lifecycle workflow gained a 'Concluded' state in 2026-06.
Going forward, Send Grades transitions each active enrollment Submitted ->
Concluded when its Course Schedule closes (see seminary.api.send_grades). Before
this change, graded enrollments stayed in 'Submitted' forever, so 'Submitted'
conflated "currently enrolled" with "finished long ago".

This reconciles existing rows: any submitted (docstatus 1) CEI still sitting in
'Submitted' whose Course Schedule is already 'Closed' is historical and must be
'Concluded'. After this, "currently enrolled" == workflow_state == 'Submitted'
holds for the whole table, not just new records.

Scope notes — mirrors the live transition exactly:
- Only 'Submitted' rows move. Withdrawn / Waitlisted / Awaiting Payment /
  Unseated are deliberately left as-is; they never became active enrollments.
- Audit enrollments also sit in 'Submitted' and are concluded once their
  section closes, same as the live path.
- Gated on Course Schedule == 'Closed', so enrollments in sections that are
  still Open/Grading stay 'Submitted' (correctly still "currently enrolled").

Idempotent: re-running matches nothing once rows are concluded.
"""

import frappe


def execute():
    rows = frappe.db.sql(
        """
        SELECT cei.name
        FROM `tabCourse Enrollment Individual` cei
        JOIN `tabCourse Schedule` cs ON cs.name = cei.coursesc_ce
        WHERE cei.docstatus = 1
          AND cei.workflow_state = 'Submitted'
          AND cs.workflow_state = 'Closed'
        """,
        as_dict=True,
    )
    if not rows:
        print("No Course Enrollment Individual rows to conclude.")
        return

    for row in rows:
        frappe.db.set_value(
            "Course Enrollment Individual",
            row.name,
            "workflow_state",
            "Concluded",
            update_modified=False,
        )

    frappe.db.commit()
    print(f"Concluded {len(rows)} historical Course Enrollment Individual row(s).")
