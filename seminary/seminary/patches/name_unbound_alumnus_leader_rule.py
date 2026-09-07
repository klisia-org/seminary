# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""An unbound `Alumnus of the bound program or level` type meant any alumnus.

Before the rule required a binding, a type carrying it with neither a program
nor a level accepted a graduate of anywhere: `Cohort Membership` returned True
as soon as it found an enabled profile. `Any alumnus` is that behaviour said out
loud, so the old rows move onto it -- otherwise the same configuration would
become a type nobody can save and a rule that refuses every candidate.

Not a widening or a narrowing: each row keeps exactly the leaders it had.
"""

import frappe

ALUMNUS = "Alumnus of the bound program or level"
ANY_ALUMNUS = "Any alumnus"


def execute():
    unbound = frappe.get_all(
        "Cohort Type",
        filters={
            "leader_eligibility": ALUMNUS,
            "program": ["is", "not set"],
            "program_level": ["is", "not set"],
        },
        pluck="name",
    )
    for name in unbound:
        # `db.set_value`, not a save: the row is being brought up to the rule,
        # and running the rest of validation on a type nobody has opened would
        # refuse the correction for some unrelated setting.
        frappe.db.set_value(
            "Cohort Type",
            name,
            "leader_eligibility",
            ANY_ALUMNUS,
            update_modified=False,
        )
