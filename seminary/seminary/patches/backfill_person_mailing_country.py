"""ADR 070 — repair postal country on people who edited it from the portal.

`get_my_communication_preferences` showed `Person.country` as the mailing
country and wrote the submitted value straight back to it. But `Person.country`
is the comms provider selector — `pick_account(channel, person_doc.country)`
reads it to pick which account can reach someone — and ADR 046 introduced
`mailing_country` precisely so a postal edit could not reach it. So correcting
an address on the portal could quietly move a person's messaging region.

Both sides now read and write `mailing_country`. This fills the field for
anyone whose postal address arrived before the fix.

`country` is never cleared. For most people the two are the same anyway, and
where they differ the stored value may well have been right for routing all
along — there is no way to tell after the fact, and guessing wrong would break
delivery rather than a mailing label.
"""

import frappe


def execute():
    rows = frappe.get_all(
        "Person",
        filters={
            "mailing_country": ("is", "not set"),
            "country": ("is", "set"),
        },
        fields=["name", "country", "address_line_1", "city"],
    )
    filled = 0
    for row in rows:
        # Only where a postal address actually exists: a country on its own is
        # the routing selector doing its job, not an unfilled mailing field.
        if not (row.address_line_1 or row.city):
            continue
        frappe.db.set_value(
            "Person",
            row.name,
            "mailing_country",
            row.country,
            update_modified=False,
        )
        filled += 1

    if filled:
        print("  mailing country filled from routing country: %d" % filled)
