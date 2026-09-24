"""Rename the release mode `Per activity (current rules)` to `Ungated` (ADR 079
decision 7), on frameworks and on section overrides alike.

`cbe.content_release_mode` already treats any non-gated value as ungated, so a
site is correct before this runs; the patch makes the stored value match the
option the form now offers.
"""

import frappe

OLD = "Per activity (current rules)"
NEW = "Ungated"


def execute():
    frappe.db.sql(
        "UPDATE `tabCompetency Framework` SET content_release_mode = %s "
        "WHERE content_release_mode = %s",
        (NEW, OLD),
    )
    frappe.db.sql(
        "UPDATE `tabCourse Schedule` SET content_release_override = %s "
        "WHERE content_release_override = %s",
        (NEW, OLD),
    )
