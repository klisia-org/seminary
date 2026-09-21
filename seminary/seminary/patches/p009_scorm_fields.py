# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Drop the three dead SCORM path fields from Course Schedule Chapter (p009 S1).

``scorm_package_path``, ``manifest_file`` and ``launch_file`` recorded where a
package had been extracted to. p008 F8 stopped extracting and its teardown patch
cleared all three on every row, so they have been permanently NULL since; the
only reader left was ``delete_scorm_package``, which goes with them, and
``get_course_outline``, which selected ``launch_file`` out of habit.

They are dropped rather than left in place because a path-shaped column on a
chapter is an invitation: SCORM delivery (p009) addresses objects by a
server-built key under ``scorm/<package id>/`` and has no filesystem path
anywhere in it, and the next author should not find one here to reuse.

Idempotent. Nothing is read from the columns before they go -- p008's teardown
already established they are empty -- but a row that somehow still carries a
value is logged rather than silently dropped.
"""

import frappe

DOCTYPE = "Course Schedule Chapter"
DEAD_FIELDS = ("scorm_package_path", "manifest_file", "launch_file")


def execute():
    if not frappe.db.exists("DocType", DOCTYPE):
        return

    present = [f for f in DEAD_FIELDS if frappe.db.has_column(DOCTYPE, f)]

    # Anything left in them is a surprise worth a line in the log: it would mean
    # a row was written after the p008 teardown by something that still knew
    # these fields. Nothing depends on the value; we are recording that it
    # existed, because the column is about to stop existing.
    for field in present:
        stragglers = frappe.get_all(
            DOCTYPE, filters={field: ["is", "set"]}, pluck="name", limit=20
        )
        if stragglers:
            frappe.log_error(
                f"{field} still set on: {', '.join(stragglers)}",
                "p009_scorm_fields: dropping a column that was not empty",
            )

    # Custom Fields and Property Setters first: a Property Setter pointing at a
    # field that no longer exists makes every subsequent reload of the doctype
    # noisy, and neither is removed by dropping the column.
    for field in DEAD_FIELDS:
        frappe.db.delete("Property Setter", {"doc_type": DOCTYPE, "field_name": field})
        frappe.db.delete("Custom Field", {"dt": DOCTYPE, "fieldname": field})

    frappe.reload_doc("seminary", "doctype", "course_schedule_chapter")
    frappe.reload_doc("seminary", "doctype", "course_lesson")

    table = f"`tab{DOCTYPE}`"
    for field in present:
        # Re-checked after the reload: `reload_doc` on a doctype whose JSON no
        # longer declares the field does not drop the column, but a concurrent
        # migrate might have.
        if frappe.db.has_column(DOCTYPE, field):
            frappe.db.sql_ddl(f"ALTER TABLE {table} DROP COLUMN `{field}`")

    frappe.db.commit()
