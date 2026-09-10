"""ADR 070 — turn the new cohort-invitation opt-out on for existing alumni.

`open_to_cohort_invites` is an opt-*out* introduced default-on: nobody has said
they want to be left alone yet, so everybody stays invitable until they do.
Frappe's column default reaches rows created from here on, but the rows already
in the table would land on the `Check` field's `NOT NULL DEFAULT 0` — reading
as "every existing alumnus has opted out", which is the opposite of what the
field means.
"""

import frappe


def execute():
    updated = frappe.db.sql(
        """
        UPDATE `tabAlumni Profile`
        SET open_to_cohort_invites = 1
        WHERE IFNULL(open_to_cohort_invites, 0) = 0
        """
    )
    frappe.db.commit()
    count = frappe.db.count("Alumni Profile", {"open_to_cohort_invites": 1})
    print("  alumni open to cohort invitations: %d" % count)
