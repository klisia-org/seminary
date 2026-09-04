"""ADR 068 phase 2 — move the shared human attributes onto the spine.

`date_of_birth`, `nationality`, `phonetic_name`, the postal address and the
sensitive block existed only on the role records. Person is the system of
record for identity data (ADR 042), so they belong here — and phase 4 deletes
the Student columns, so the values have to be lifted first.

Fill-blanks only, and Student before Student Applicant: an admitted student's
record is the more current of the two, which is the same precedence
`create_person_spine` used when it built the spine in the first place.

Everything is derived from `person_fields.SPEC`, so an attribute added to the
registry later is carried by this patch without editing it.
"""

import frappe

from seminary.seminary import person_fields as registry
from seminary.seminary.person import update_person

# Student first: the richer, more current record for anyone admitted.
SOURCES = (registry.STUDENT, registry.APPLICANT)


def execute():
    _seed_mailing_country()
    for doctype in SOURCES:
        _lift(doctype)


def _seed_mailing_country():
    """`country` served as both the messaging region and the postal country.

    Phase 2 splits them, and `Alumni Profile.mailing_country` now fetches the
    new field — so without this every alumni address would render blank on the
    next save. Copy the old conflated value across; from here the two fields
    diverge only when someone edits them apart.
    """
    rows = frappe.get_all(
        "Person",
        filters={"country": ["is", "set"], "mailing_country": ["is", "not set"]},
        fields=["name", "country"],
    )
    for row in rows:
        frappe.db.set_value(
            "Person", row.name, "mailing_country", row.country, update_modified=False
        )
    if rows:
        print("  seeded mailing_country on %d Person rows" % len(rows))


def _lift(doctype):
    pairs = [
        (spec, binding)
        for spec, binding in registry.bindings_for(doctype)
        if spec.settable
    ]
    if not pairs:
        return

    meta = frappe.get_meta(doctype)
    pairs = [(s, b) for s, b in pairs if meta.get_field(b.fieldname)]
    fields = ["name", "person"] + [b.fieldname for _, b in pairs]

    moved = 0
    for row in frappe.get_all(
        doctype, filters={"person": ["is", "set"]}, fields=fields
    ):
        values = {
            spec.arg: row.get(binding.fieldname)
            for spec, binding in pairs
            if row.get(binding.fieldname)
        }
        if not values:
            continue
        # overwrite=False: an existing spine value always wins. A Select
        # literal that is not a valid Link target (an applicant's gender on a
        # localised site) is dropped by `_apply`'s guard rather than taking the
        # whole patch down.
        update_person(row.person, **values)
        moved += 1
    if moved:
        print("  lifted attributes from %d %s rows" % (moved, doctype))
