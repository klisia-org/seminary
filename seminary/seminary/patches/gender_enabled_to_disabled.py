"""ADR 068 §9 — `Gender.enabled` becomes `Gender.disabled`, so pickers filter.

The custom field was `enabled`, and **nothing filtered on it**. Every Gender
picker in the app, the public application form included, offered all seven rows
Frappe's setup wizard seeds. `install.setup_genders()` diligently maintained a
flag no reader consulted.

The fix is the field's *name*: `frappe/desk/search.py` drops rows from every
Link search when the target doctype has a Check field called `disabled`. That
is Frappe's own convention, so it survives upgrades, needs no per-field wiring,
and — unlike `link_filters`, which `Web Form Field` does not have a column for
— reaches Web Forms too.

Carries the values across inverted, then removes the old field so there is one
answer to "is this gender offered" rather than two that can disagree.
"""

import frappe


def execute():
    from seminary.install import ensure_gender_disabled_field, setup_genders

    ensure_gender_disabled_field()

    if frappe.db.has_column("Gender", "enabled"):
        # Inverted carry-over: a row nobody had enabled becomes disabled.
        frappe.db.sql("update `tabGender` set disabled = if(ifnull(enabled, 0), 0, 1)")
        old = frappe.db.exists("Custom Field", {"dt": "Gender", "fieldname": "enabled"})
        if old:
            frappe.delete_doc("Custom Field", old, force=True, ignore_permissions=True)
        print("  carried Gender.enabled across to Gender.disabled")
    else:
        # No prior flag on this site (the field was never created in code, so
        # only potestas ever had one): fall back to the first-run default.
        setup_genders()

    offered = frappe.get_all("Gender", filters={"disabled": 0}, pluck="name")
    print("  genders offered: %s" % ", ".join(sorted(offered)))

    _report_dangling_genders()


def _report_dangling_genders():
    """`Student Applicant.gender` was a Select of the literals Male/Female and
    is now a Link to Gender, matching Person and the web form (which already
    rendered a Link, which is how the two drifted).

    The values carry across untouched — a Select stored the same strings — but
    a site set up in another language has genders named in that language, so
    the literal may match no row. Say so rather than leave a dangling link to
    surface later as an unsaveable applicant.
    """
    known = set(frappe.get_all("Gender", pluck="name"))
    for doctype in ("Student Applicant", "Person"):
        values = frappe.db.sql_list(
            "select distinct gender from `tab%s` where ifnull(gender, '') != ''"
            % doctype
        )
        missing = [v for v in values if v not in known]
        if missing:
            print(
                "  WARNING: %s holds gender value(s) with no Gender record: %s"
                % (doctype, ", ".join(missing))
            )
