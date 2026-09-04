"""ADR 069 — move the alumni academic block into rows.

`Alumni Profile` recorded one completed program in three flat fields, so a
person who graduated twice had nowhere to put the second. What actually
happened was worse than an overwrite: `alumni.api.mark_as_alumni` returned
early on the existing profile, so the second degree was recorded nowhere *and*
the second enrollment never got its `date_of_conclusion` — the early return sat
above that line.

The flat columns are read straight from the table here rather than through the
meta, because the docfields are gone by the time this runs (patches are
post-model-sync) even though Frappe leaves the columns in place.
"""

import frappe

LEGACY = ("program_completed", "class_year", "graduated_from_enrollment")


def execute():
    if not frappe.db.exists("DocType", "Alumni Profile"):
        return
    present = [c for c in LEGACY if frappe.db.has_column("Alumni Profile", c)]
    if "program_completed" not in present:
        return

    rows = frappe.db.sql(
        "select name, {cols} from `tabAlumni Profile` "
        "where program_completed is not null and program_completed != ''".format(
            cols=", ".join("`%s`" % c for c in present)
        ),
        as_dict=True,
    )

    moved = 0
    for row in rows:
        profile = frappe.get_doc("Alumni Profile", row.name)
        if profile.graduations:
            continue  # already migrated, or already recorded a graduation
        from seminary.alumni.doctype.alumni_profile.alumni_profile import (
            class_year_for,
        )

        enrollment = row.get("graduated_from_enrollment") or None
        pe = (
            frappe.db.get_value(
                "Program Enrollment",
                enrollment,
                ["date_of_conclusion", "academic_term"],
                as_dict=True,
            )
            if enrollment
            else None
        )
        academic_year = (
            frappe.db.get_value("Academic Term", pe.academic_term, "academic_year")
            if pe and pe.academic_term
            else None
        )
        conclusion_date = pe.date_of_conclusion if pe else None
        # Recompute rather than carrying the stored Int across: it was
        # `getdate(date_of_conclusion).year`, which labels every autumn
        # graduate a year early (ADR 069).
        profile.append(
            "graduations",
            {
                "program": row.get("program_completed"),
                "academic_year": academic_year,
                "class_year": class_year_for(academic_year, conclusion_date)
                or row.get("class_year")
                or None,
                "program_enrollment": enrollment,
                "conclusion_date": conclusion_date,
            },
        )
        profile.save(ignore_permissions=True)
        moved += 1

    if moved:
        print("  moved %d alumni graduations into rows" % moved)
