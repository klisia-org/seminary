"""ADR 068 phase 3 — stop keying role records on the person's own data.

`Instructor` autonamed `format:{instructor_name}`, `Alumni Profile`
`field:email`, `Student Applicant` `{academic_term}-{first_name}-{###}`. So the
primary key was the very data ADR 042 created the spine to make
non-authoritative: a marriage, a legal name change or a corrected typo meant a
rename cascading through every link table, which is why `propagate_to_roles`
skipped `instructor_name` outright and left it stale forever.

`frappe.rename_doc` updates Link fields (including those on child doctypes and
Table MultiSelects), Dynamic Links, Versions, Attachments and passwords, and it
finds them by querying `tabDocField` rather than scanning per app — so
aretenic's eight `Link → Instructor` fields are carried without naming them
here. `Student` keeps its already-opaque `{YY}-{#####}`, which is what keeps
oikonomos out of this entirely.

Runs after the doctype JSONs are synced (post_model_sync), so `allow_rename`
and the new `autoname` are already in place.
"""

import frappe
from frappe.model.naming import make_autoname

# doctype -> the new naming series
TARGETS = {
    "Instructor": "INST-.#####",
    "Alumni Profile": "ALUM-.#####",
    "Student Applicant": "APP-.#####",
}


def execute():
    _backfill_applicant_access_keys()
    for doctype, series in TARGETS.items():
        if not frappe.db.exists("DocType", doctype):
            continue
        prefix = series.split(".", 1)[0]
        stale = [
            name
            for name in frappe.get_all(doctype, pluck="name")
            if not str(name).startswith(prefix)
        ]
        for old in stale:
            frappe.rename_doc(
                doctype,
                old,
                make_autoname(series, doctype),
                # force=True covers `allow_rename`; the patch runs as
                # Administrator so there is no permission to bypass. (The
                # `frappe.rename_doc` wrapper does not forward
                # ignore_permissions — only the inner model function takes it.)
                force=True,
                merge=False,
                show_alert=False,
            )
        if stale:
            print("  renamed %d %s records to %s" % (len(stale), doctype, prefix))


def _backfill_applicant_access_keys():
    """Give existing applicants the key the payment page now requires.

    Without this every application submitted before the rename would meet
    "this payment link is invalid" — a security fix that quietly breaks the
    thank-you page for real people is not a fix.
    """
    names = frappe.get_all(
        "Student Applicant", filters={"access_key": ["is", "not set"]}, pluck="name"
    )
    for name in names:
        frappe.db.set_value(
            "Student Applicant",
            name,
            "access_key",
            frappe.generate_hash(length=32),
            update_modified=False,
        )
    if names:
        print("  issued access keys to %d Student Applicant records" % len(names))
