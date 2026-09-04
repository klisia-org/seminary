# Copyright (c) 2025, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class StudentGroup(Document):
    """A course-scoped grading and rostering group.

    Not a cohort, and deliberately not made into one: a program cohort is a
    `Cohort` (ADR 066 section 1), which has the dated memberships, Person-keyed
    leader and lineage that grouping actually needs. What stays here is what a
    grading roster wants -- who is in the group, and since when.
    """

    def validate(self):
        self.validate_members()

    def validate_members(self):
        """Membership lifecycle, per ADR 023: child rules live on the parent.

        Mirrors `Cohort Membership` deliberately. A student who moved group is
        not a student who never joined: the row stays, dated, so the movement is
        recoverable the day the school decides what a failed competency means.
        """
        seen = {}
        for row in self.group_members:
            if row.status == "Active":
                row.left_on = None
                if not row.joined_on:
                    row.joined_on = today()
            elif not row.left_on:
                row.left_on = today()

            # getdate on both operands: one side comes back as a date from the
            # database and the other as a string from today(), and comparing
            # the two raises instead of answering.
            if (
                row.left_on
                and row.joined_on
                and getdate(row.left_on) < getdate(row.joined_on)
            ):
                frappe.throw(
                    _("Row {0}: {1} cannot leave before joining.").format(
                        row.idx, frappe.bold(row.student_name or row.student)
                    )
                )

            if row.status != "Active":
                continue
            if row.student in seen:
                frappe.throw(
                    _("Row {0}: {1} is already an active member of this group.").format(
                        row.idx, frappe.bold(row.student_name or row.student)
                    )
                )
            seen[row.student] = row.idx
