"""ADR 068 §1 — one record per role per person, enforced in the database.

Many roles per person is the whole point of the spine: the same human can be a
Student *and* an Instructor *and* an alumnus, and each of those is a different
doctype. What must not happen is two `Student` records — or two `Instructor`
records — for one human, which is the duplication ADR 042 exists to prevent.

Until now that rule was enforced only by accident and only in two of the three
places. A second Student or Alumni Profile collided on its unique *email*
mirror; a second Instructor was created happily, because `prof_email` is not
unique and neither is `Instructor.user`.

Setting `unique: 1` on the docfield is not enough on its own. The column
already carried a plain index from being a Link, and Frappe's schema updater
leaves it alone rather than converting it — so the flag showed in the meta
while the database still accepted duplicates. The index is created here
explicitly.

Two humans' records merged onto one identity is not something a patch should
guess at, so a pre-existing duplicate hard-fails for manual resolution — the
same call ADR 042's own backfill made about email collisions.
"""

import frappe
from frappe import _

DOCTYPES = ("Student", "Instructor", "Alumni Profile")
CONSTRAINT = "unique_person"


def execute():
    problems = []
    for doctype in DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            continue
        # `has_column` takes the doctype and prepends `tab` itself — passing a
        # scrubbed table name looks for `tabstudent` and raises TableMissing.
        if not frappe.db.has_column(doctype, "person"):
            continue
        for row in frappe.db.sql(
            """
            select person, count(*) as n, group_concat(name) as names
            from `tab{doctype}`
            where person is not null and person != ''
            group by person having n > 1
            """.format(
                doctype=doctype
            ),
            as_dict=True,
        ):
            problems.append("%s: %s share person %s" % (doctype, row.names, row.person))

    if problems:
        frappe.throw(
            _(
                "One record per role per person (ADR 068), but these already "
                "share one:\n\n{0}\n\nDecide which record is the person's and "
                "either delete or re-point the others, then migrate again."
            ).format("\n".join(problems))
        )

    for doctype in DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            continue
        if not frappe.db.has_column(doctype, "person"):
            continue
        frappe.db.add_unique(doctype, ["person"], constraint_name=CONSTRAINT)
