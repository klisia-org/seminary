"""Soft integration with frappe_giving (an optional app).

seminary owns the Donor <-> Person link; frappe_giving never references
seminary. The canonical FK is the Custom Field `Donor.person` (created in
seminary.install.setup_donor_person_field). `Person.donor` is a read-only
reverse mirror maintained here.

These handlers are wired via doc_events on "Donor" in hooks.py. A doc_events
entry for a doctype that doesn't exist simply never fires, so when
frappe_giving is absent this module is inert -- keeping the dependency soft
and one-directional. The has_column guards cover the window between installing
frappe_giving and running `bench migrate` (which creates the fields).
"""

import frappe


def link_donor(person_name, donor):
    """Set the canonical Donor.person and mirror Person.donor, first-link-wins
    on each side (never overwrites an existing link). Used by the backfill
    patch and any other server-side linker."""
    if not person_name or not donor:
        return
    if frappe.db.has_column("Donor", "person") and not frappe.db.get_value(
        "Donor", donor, "person"
    ):
        frappe.db.set_value(
            "Donor", donor, "person", person_name, update_modified=False
        )
    if frappe.db.has_column("Person", "donor") and not frappe.db.get_value(
        "Person", person_name, "donor"
    ):
        frappe.db.set_value(
            "Person", person_name, "donor", donor, update_modified=False
        )


def on_donor_update(doc, method=None):
    """Mirror the canonical Donor.person link onto Person.donor."""
    if not frappe.db.has_column("Person", "donor"):
        return

    person = doc.get("person")

    # If this Donor was re-pointed to a different Person, clear the stale mirror.
    before = doc.get_doc_before_save()
    old_person = before.get("person") if before else None
    if old_person and old_person != person:
        if frappe.db.get_value("Person", old_person, "donor") == doc.name:
            frappe.db.set_value(
                "Person", old_person, "donor", None, update_modified=False
            )

    if person and frappe.db.get_value("Person", person, "donor") != doc.name:
        frappe.db.set_value("Person", person, "donor", doc.name, update_modified=False)


def on_donor_trash(doc, method=None):
    """Drop the reverse mirror when its Donor is deleted."""
    if not frappe.db.has_column("Person", "donor"):
        return
    person = doc.get("person")
    if person and frappe.db.get_value("Person", person, "donor") == doc.name:
        frappe.db.set_value("Person", person, "donor", None, update_modified=False)
