# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""`Cohort Type.automation_rule` becomes the `plannable` Check (ADR 067 section 2).

The Select held two axes at once. Its only offered value, `On Program
Enrollment`, was a trigger -- withdrawn, because at the moment one enrollment is
created nobody can know whether the cohort will hold. Its deferred values (`Per
intake term`, `Per site`, ...) were cuts, not triggers, and they now live in the
planner's own pool step.

Nothing ever read the field, so this carries an intent rather than behaviour: a
type someone had marked for automation is a type they want the planner to offer.

Frappe drops the docfield but leaves the column until `bench trim-tables`, so the
old value is read with raw SQL -- through the meta it no longer exists.
"""

import frappe


def execute():
    if not frappe.db.has_column("Cohort Type", "automation_rule"):
        return

    rows = frappe.db.sql(
        """
        SELECT name FROM `tabCohort Type`
        WHERE automation_rule IS NOT NULL AND automation_rule != ''
        """,
        as_dict=True,
    )
    for row in rows:
        # db.set_value, not a save: the controller now refuses a plannable type
        # with no mentor_unit, and no such unit exists yet on a site being
        # migrated. The chair picks one the first time they open the planner --
        # which is a setting to complete, not a record to repair.
        frappe.db.set_value(
            "Cohort Type", row.name, "plannable", 1, update_modified=False
        )
