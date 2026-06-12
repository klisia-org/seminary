"""Pre-sync: stash legacy Payers Fee Category PE → Scholarships links.

Scholarships become first-class Scholarship Awards (ADR 047). The legacy
`scholarship` Link field on Payers Fee Category PE is dropped this release, so we
must capture its values BEFORE the schema sync removes the column. The companion
post-sync patch (migrate_scholarships_to_awards) reads this scratch table to
create the awards, then drops it.

Idempotent: re-runs find the column already gone (nothing to stash).
"""

import frappe

STASH = "__scholarship_link_stash"


def execute():
    # Column still present only on the first run of this release.
    has_col = frappe.db.sql(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tabPayers Fee Category PE'
          AND column_name = 'scholarship'
          AND table_schema = DATABASE()
        """
    )
    if not has_col:
        print("No legacy scholarship column to stash.")
        return

    frappe.db.sql_ddl(
        f"""
        CREATE TABLE IF NOT EXISTS `{STASH}` (
            pfc VARCHAR(140),
            pf_pe VARCHAR(140),
            scholarship VARCHAR(140)
        )
        """
    )

    frappe.db.sql(
        f"""
        INSERT INTO `{STASH}` (pfc, pf_pe, scholarship)
        SELECT name, pf_pe, scholarship
        FROM `tabPayers Fee Category PE`
        WHERE scholarship IS NOT NULL AND scholarship != ''
        """
    )
    count = frappe.db.sql(f"SELECT COUNT(*) FROM `{STASH}`")[0][0]
    frappe.db.commit()
    print(f"Stashed {count} scholarship link(s) for award migration.")
