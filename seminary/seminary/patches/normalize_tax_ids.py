"""ADR 071 — store tax IDs in the canonical form the registry defines.

Values that predate the registry were typed into a free-text box, so they carry
whatever punctuation the applicant used. `tax_ids` stores the stripped form so
an export, a future duplicate check and the Asaas bridge all see one shape.

Rewrites only what the country's rule actually validates. A value that does not
validate is left exactly as typed and counted: some of it is junk from a public
form, and a patch that refuses to migrate over junk is worse than a field
carrying it — `tax_ids.assert_on` already warns rather than throws on a legacy
value until someone edits it, which is when it gets fixed by a human who knows
what the right number is.

Never throws, never blanks.
"""

import frappe

from seminary.seminary import tax_ids

DOCTYPES = ("Person", "Student Applicant", "Partner Organization")


def execute():
    normalized = left_alone = 0

    for doctype in DOCTYPES:
        if not _has_tax_id(doctype):
            continue

        fields = ["name", "tax_id", *tax_ids.COUNTRY_FIELDS.get(doctype, ())]
        subject = tax_ids.SUBJECTS.get(doctype, tax_ids.BOTH)

        for row in frappe.get_all(
            doctype, filters={"tax_id": ("is", "set")}, fields=fields
        ):
            country = next(
                (row.get(f) for f in tax_ids.COUNTRY_FIELDS[doctype] if row.get(f)),
                None,
            )
            if tax_ids.problem_with(row.tax_id, country, subject):
                left_alone += 1
                continue

            cleaned = tax_ids.clean_tax_id(row.tax_id, country, subject)
            if cleaned and cleaned != row.tax_id:
                frappe.db.set_value(
                    doctype, row.name, "tax_id", cleaned, update_modified=False
                )
                normalized += 1

    if normalized:
        print("  tax ids normalized: %d" % normalized)
    if left_alone:
        print(
            "  tax ids left as typed (no rule, or would not validate): %d" % left_alone
        )


def _has_tax_id(doctype):
    return bool(
        frappe.db.exists("DocType", doctype)
        and frappe.get_meta(doctype).get_field("tax_id")
    )
