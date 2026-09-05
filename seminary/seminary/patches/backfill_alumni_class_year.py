"""ADR 069 — fill `class_year` on graduation rows that never got one.

It was derived only in `AlumniProfile.record_graduation`, the path from a
completed Program Enrollment. A row added by hand in Desk — an alumnus of
another institution, or one whose studies predate this system — got nothing,
and because `class_year` is an `Int` (Frappe stores those `NOT NULL DEFAULT 0`)
the field did not read as empty. It read as **Class of 0**.

The derivation now lives in the parent's `validate`, so every path shares it.
This fills the rows written before that.
"""

import frappe

from seminary.alumni.doctype.alumni_profile.alumni_profile import class_year_for


def execute():
    rows = frappe.get_all(
        "Alumni Graduation",
        filters={"class_year": ["in", (0, None)]},
        fields=["name", "parent", "academic_year", "conclusion_date"],
    )
    filled = stranded = 0
    for row in rows:
        year = class_year_for(row.academic_year, row.conclusion_date)
        if not year:
            # Neither an academic year nor a conclusion date: nothing to derive
            # from. Left alone and named, rather than guessed at — `validate`
            # refuses to save such a row from now on, so these are historical.
            stranded += 1
            print(
                "  %s (%s): no academic year or conclusion date, class year "
                "left unset" % (row.name, row.parent)
            )
            continue
        frappe.db.set_value(
            "Alumni Graduation", row.name, "class_year", year, update_modified=False
        )
        filled += 1

    if filled or stranded:
        print("  class years filled: %d, stranded: %d" % (filled, stranded))
