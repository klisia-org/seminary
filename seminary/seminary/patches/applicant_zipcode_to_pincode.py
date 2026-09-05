"""ADR 068 §7 — `Student Applicant.zipcode` becomes `pincode`.

Person and Student both spell the postal code `pincode`. The applicant spelled
it `zipcode`, and the second spelling was not harmless: `api.enroll_student`
maps applicant to student by matching field *names*, so the postal code was
silently dropped at admission, and the shared web-form script had to special-
case it when filling an autocompleted address.

Runs pre-model-sync and renames the column for real, rather than copying values
post-sync and leaving `zipcode` behind. A dropped docfield does not drop its
column — Frappe leaves it until `bench trim-tables` — so the copy-and-abandon
version would leave a populated `zipcode` column that still answers raw SQL and
still looks authoritative, which is the exact failure mode ADR 068 keeps
running into.
"""

import frappe

TABLE = "tabStudent Applicant"


def execute():
    if not frappe.db.table_exists("Student Applicant"):
        return
    columns = {c.get("Field") or c.get("column_name") for c in _describe()}
    if "zipcode" not in columns:
        return
    if "pincode" in columns:
        # sync_all got here first (a patch re-run after a failed migrate).
        # Keep whichever value a human typed, then leave the orphan behind for
        # trim-tables — dropping it here would discard the only copy if this
        # patch is the thing that just failed.
        frappe.db.sql(
            "update `%s` set pincode = zipcode "
            "where (pincode is null or pincode = '') and zipcode is not null" % TABLE
        )
        return
    frappe.db.sql_ddl(
        "alter table `%s` change column `zipcode` `pincode` varchar(140)" % TABLE
    )
    print("  renamed Student Applicant.zipcode to pincode")


def _describe():
    return frappe.db.sql("describe `%s`" % TABLE, as_dict=True)
