"""Backfill the Donor <-> Person link (ADR 048).

Creates the cross-app custom fields if missing, then links each frappe_giving
Donor to an *existing* Person by shared Customer first, then by User/email
(reusing Person's own match heuristic). Only unambiguous matches are linked;
never creates a Person and never overwrites an existing link (first-link-wins).
Unmatched Donors are reported for manual resolution. No-op when frappe_giving
isn't installed.
"""

import frappe

from seminary.install import setup_donor_person_field
from seminary.seminary.integrations.giving import link_donor
from seminary.seminary.person import find_person


def _match_person(d):
    """Return the single matching Person name, or None when there is no match
    or the match is ambiguous (left for manual resolution)."""
    if d.customer:
        matches = frappe.get_all(
            "Person", filters={"customer": d.customer}, pluck="name"
        )
        if len(matches) == 1:
            return matches[0]
        # 0 or >1: fall through to the email/user heuristic.
    person = find_person(email=d.email, user=d.user)
    if not person and d.alternate_email:
        person = find_person(email=d.alternate_email)
    return person


def execute():
    if not frappe.db.exists("DocType", "Donor"):
        return

    setup_donor_person_field()

    linked = 0
    skipped = []
    for d in frappe.get_all(
        "Donor",
        filters={"person": ("is", "not set")},
        fields=["name", "customer", "user", "email", "alternate_email"],
    ):
        person = _match_person(d)
        if person:
            link_donor(person, d.name)
            linked += 1
        else:
            skipped.append(d.name)

    frappe.db.commit()
    print(f"Donor.person backfilled: {linked} linked, {len(skipped)} unmatched.")
    if skipped:
        print("  Unmatched Donors (link manually): " + ", ".join(skipped))
