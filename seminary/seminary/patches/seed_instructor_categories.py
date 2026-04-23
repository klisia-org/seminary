"""Seed default Instructor Category records on existing sites.

New installs get these via ``seminary.install.setup_fixtures``; this patch covers
sites that were already running before the Instructor Category doctype landed.

Run via::

    bench --site <site> execute seminary.seminary.patches.seed_instructor_categories.execute
"""

import frappe

DEFAULTS = [
    {
        "category_name": "Instructor of Record",
        "is_instructor_of_record": 1,
        "description": (
            "Primary instructor responsible for the course for accreditation purposes."
        ),
    },
    {
        "category_name": "Co-Instructor",
        "description": "Shares teaching duties with the Instructor of Record.",
    },
    {
        "category_name": "Graduate Teaching Assistant",
        "description": (
            "Graduate student assisting with teaching and grading under faculty supervision."
        ),
    },
    {
        "category_name": "Grader",
        "description": "Grades assignments and assessments only.",
    },
]


def execute():
    created = 0
    for row in DEFAULTS:
        if frappe.db.exists("Instructor Category", row["category_name"]):
            continue
        doc = frappe.get_doc({"doctype": "Instructor Category", **row})
        doc.insert(ignore_permissions=True)
        created += 1
    frappe.db.commit()
    print(f"Seeded {created} Instructor Category records.")
