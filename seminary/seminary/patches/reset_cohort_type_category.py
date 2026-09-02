# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Reset Cohort Type.category to Unrestricted (ADR 066 section 2).

The old options -- Student / Pastor-Mentoring / Alumni-Peer / Mixed -- described
who was *in* a cohort and were never wired to anything. The new ones describe
what binds a cohort and what ends it, and every one of them makes something
happen. There is no honest mapping between the two: `Student` says nothing about
whether that cohort advances with the term, runs to graduation, or is formed by
a course.

So every existing type becomes `Unrestricted`, which is what they all behave
like today -- no lifecycle, no automation, nothing fires. A chair reclassifies
deliberately, and until they do, no cohort starts moving on its own. The
`graduates_to` values are left in place rather than cleared: they are hidden
under `Unrestricted` and come back intact the moment a type is reclassified into
a program category.
"""

import frappe

# The four values the Select carried before this ADR.
RETIRED = ("Student", "Pastor-Mentoring", "Alumni-Peer", "Mixed")


def execute():
    if not frappe.db.has_column("Cohort Type", "category"):
        return
    stale = frappe.get_all(
        "Cohort Type", filters={"category": ("in", RETIRED)}, pluck="name"
    )
    if not stale:
        return
    frappe.db.set_value(
        "Cohort Type",
        {"category": ("in", RETIRED)},
        "category",
        "Unrestricted",
        update_modified=False,
    )
    frappe.db.commit()
    print(
        "Cohort Type: reset %d type(s) to Unrestricted for reclassification: %s"
        % (len(stale), ", ".join(stale))
    )
