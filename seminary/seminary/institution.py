# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""What kind of institution runs this site.

The app was written for seminaries, and a few features only make sense in one:
chapel, the doctrinal statement, the Bible integration. A school that is not a
seminary turns `Seminary Settings.seminary_features` off and those features
leave Desk navigation and the public site. Nothing is removed: the doctypes,
their data and their hooks stay, so turning the switch back on restores them.
"""

import frappe
from frappe.utils import cint

# Doctypes a non-seminary has no use for. Child tables are not listed: they are
# never a navigation target.
SEMINARY_ONLY_DOCTYPES = (
    "Bible API Settings",
    "Chapel",
    "Chapel Attendance",
    "Chapel Team",
    "Doctrinal Statement",
)


def seminary_features_enabled():
    """True unless the school has turned seminary features off. A site that has
    not migrated the field yet reads as a seminary, which is what it was."""
    # Read the stored row, not get_single_value: that casts a Check that was
    # never saved to 0, which would turn every existing seminary off on migrate.
    rows = frappe.db.sql(
        "select value from tabSingles where doctype = %s and field = %s",
        ("Seminary Settings", "seminary_features"),
    )
    return True if not rows or rows[0][0] is None else bool(cint(rows[0][0]))
