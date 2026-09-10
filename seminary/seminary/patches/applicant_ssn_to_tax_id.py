"""ADR 071 — `Student Applicant.social_security_number` becomes `tax_id`.

The field was called Social Security Number, was required on the public
application form, and had no validation of any kind. Outside the United States
that is not what anybody typed into it: a Brazilian applicant put a CPF there,
because it was the only box on the form that would take one. It was also not in
the shared-attribute registry, so whatever was typed stayed on the applicant
record and never reached the Person — a registrar re-keyed it, or nobody did.

Renaming rather than adding a second field is ADR 068 §7's rule: one spelling
per attribute. A `tax_id` alongside an `ssn` is two homes for one fact, and the
unvalidated one is the one still wired to the public form.

Runs pre-model-sync and renames the column for real. A dropped docfield does
not drop its column — Frappe leaves it until `bench trim-tables` — so a
copy-and-abandon version leaves a populated `social_security_number` that still
answers raw SQL and still looks authoritative.
"""

import frappe

TABLE = "tabStudent Applicant"


def execute():
    if not frappe.db.table_exists("Student Applicant"):
        return
    columns = {c.get("Field") or c.get("column_name") for c in _describe()}
    if "social_security_number" not in columns:
        return
    if "tax_id" in columns:
        # sync_all got here first (a patch re-run after a failed migrate, or a
        # site that pulled the JSON before the patch). Keep whichever value a
        # human typed, then leave the orphan for trim-tables — dropping it here
        # would discard the only copy if this patch is the thing that just
        # failed.
        frappe.db.sql(
            "update `%s` set tax_id = social_security_number "
            "where (tax_id is null or tax_id = '') "
            "and social_security_number is not null" % TABLE
        )
        print("  copied Student Applicant.social_security_number into tax_id")
        return
    frappe.db.sql_ddl(
        "alter table `%s` change column `social_security_number` `tax_id` varchar(140)"
        % TABLE
    )
    print("  renamed Student Applicant.social_security_number to tax_id")


def _describe():
    return frappe.db.sql("describe `%s`" % TABLE, as_dict=True)
