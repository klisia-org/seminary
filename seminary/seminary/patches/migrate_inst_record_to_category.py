"""Migrate legacy ``inst_record`` Check field to ``instructor_category`` link.

Must run BEFORE DocType sync (which drops the old column). Registered in
``patches.txt`` as ``pre_model_sync``.

``inst_record = 1`` rows are mapped to the default "Instructor of Record"
Instructor Category on both Course Schedule Instructors and Instructor Log.
"""

import frappe


IOR_NAME = "Instructor of Record"


def execute():
    # Seed the default IoR category so the backfill has a target.
    if not frappe.db.exists("Instructor Category", IOR_NAME):
        frappe.get_doc(
            {
                "doctype": "Instructor Category",
                "category_name": IOR_NAME,
                "is_instructor_of_record": 1,
                "description": (
                    "Primary instructor responsible for the course for accreditation "
                    "purposes."
                ),
            }
        ).insert(ignore_permissions=True)

    for table in ("Course Schedule Instructors", "Instructor Log"):
        if not _column_exists(table, "inst_record"):
            continue
        if not _column_exists(table, "instructor_category"):
            continue
        frappe.db.sql(
            f"""
            update `tab{table}`
            set instructor_category = %s
            where inst_record = 1 and (instructor_category is null or instructor_category = '')
            """,
            IOR_NAME,
        )

    frappe.db.commit()


def _column_exists(doctype: str, column: str) -> bool:
    table = f"tab{doctype}"
    return bool(
        frappe.db.sql(
            """
            select 1
            from information_schema.columns
            where table_schema = database()
              and table_name = %s
              and column_name = %s
            """,
            (table, column),
        )
    )
