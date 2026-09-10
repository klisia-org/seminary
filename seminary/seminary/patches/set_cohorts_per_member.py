# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Give existing Cohort Types the same answer a new one starts with.

`Cohort Type.max_lineages_per_member` defaults to 1, and a Frappe default only
reaches documents created after the field exists -- so without this every type
that already existed would sit at 0, meaning no limit, while every type made
tomorrow limits to one. Two schools' worth of behaviour in one install, decided
by when somebody happened to create the record.

Course-scoped types are set to 0 instead, which is not an exception so much as
the same answer read out: that category forms one cohort per course and a
student takes several at once, so a limit of one would refuse the second
course's seeding.

Nothing is broken by this. The limit is checked when a membership is opened, so
anyone already in two cohorts of a type stays in both.
"""

import frappe

COURSE_SCOPED = "Course scoped"


def execute():
    for name, category in frappe.get_all(
        "Cohort Type", fields=["name", "category"], as_list=True
    ):
        frappe.db.set_value(
            "Cohort Type",
            name,
            "max_lineages_per_member",
            0 if category == COURSE_SCOPED else 1,
            update_modified=False,
        )
