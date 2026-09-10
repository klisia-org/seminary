"""ADR 053 phase 4 / ADR 070 — link alumni to the partner organizations they name.

`Alumni Profile.current_organization` is free text the alumnus wrote, and it
stays that way: this only fills the new `current_partner_organization` Link
beside it, and only on an exact case-insensitive name match. A near match is
left alone deliberately — "Grace Church" is not evidence for any particular
Grace Church, and a wrong badge on someone's profile is worse than no badge.
"""

import frappe


def execute():
    profiles = frappe.get_all(
        "Alumni Profile",
        filters={
            "current_organization": ("is", "set"),
            "current_partner_organization": ("is", "not set"),
        },
        fields=["name", "current_organization"],
    )
    if not profiles:
        return

    orgs = frappe.get_all("Partner Organization", fields=["name", "organization_name"])
    by_name = {}
    for org in orgs:
        key = (org.organization_name or "").strip().lower()
        if not key:
            continue
        # An ambiguous name matches nothing rather than the first one seen.
        by_name[key] = None if key in by_name else org.name

    matched = 0
    for profile in profiles:
        org = by_name.get((profile.current_organization or "").strip().lower())
        if not org:
            continue
        frappe.db.set_value(
            "Alumni Profile",
            profile.name,
            "current_partner_organization",
            org,
            update_modified=False,
        )
        matched += 1

    print(
        "  alumni linked to a partner organization: %d of %d" % (matched, len(profiles))
    )
