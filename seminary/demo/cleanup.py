import frappe

DEMO_TAG = "Seminary Demo Data"

# Order matters — delete children before parents

DEMO_DOCTYPES = [
    # 1. Deepest children first
    "Course Enrollment Individual",  # ← first
    "Course Schedule",
    "Program Enrollment",
    "Student",
    # 2. Core demo records
    "Instructor",
    "Program",
    "Course",
    "Academic Term",
    "Academic Year",
    "User",
]

# These get deleted automatically with their parents:
# - Program Course (child of Program)
# - Course Schedule Instructors (child of Course Schedule)
# - Scheduled Course Assess Criteria (child of Course Schedule)
# - coursesc_ce child table (child of Course Enrollment Individual)


def remove_demo_data():
    """Remove all records tagged as demo data."""
    frappe.only_for(["Administrator", "System Manager"])

    deleted_counts = {}

    # Billing demo records (Sales Invoices, Customers) are owned by the financial
    # bridge and reference the academic docs below. Let oikonomos tear its own
    # down first via the seminary_demo_cleanup hook; a no-op on a Frappe-only
    # seminary, which has no billing records.
    for fn in frappe.get_hooks("seminary_demo_cleanup"):
        try:
            frappe.get_attr(fn)(deleted_counts)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "seminary_demo_cleanup")

    for doctype in DEMO_DOCTYPES:
        # Find all docs with the demo tag
        tagged_docs = frappe.get_all(
            "Tag Link",
            filters={"document_type": doctype, "tag": DEMO_TAG},
            pluck="document_name",
        )

        meta = frappe.get_meta(doctype) if tagged_docs else None

        count = 0
        for doc_name in tagged_docs:
            try:
                # For submittable docs, force docstatus=2 directly to bypass
                # before_cancel / on_cancel hooks (e.g. CEI blocks cancellation
                # after course start date and cascades to Sales Invoices).
                if meta and meta.is_submittable:
                    frappe.db.set_value(
                        doctype, doc_name, "docstatus", 2, update_modified=False
                    )

                frappe.delete_doc(
                    doctype,
                    doc_name,
                    force=True,
                    ignore_permissions=True,
                    delete_permanently=True,
                )
                count += 1
            except Exception:
                frappe.log_error(f"Failed to delete {doctype} {doc_name}")

        if count:
            deleted_counts[doctype] = count

    # Mark demo as uninstalled
    frappe.db.set_single_value("Seminary Settings", "demo_data_installed", 0)
    frappe.db.set_single_value("Seminary Settings", "no_more_demo", 1)
    frappe.db.commit()

    summary = "\n".join(f"  • {dt}: {c} deleted" for dt, c in deleted_counts.items())
    frappe.msgprint(f"✅ Demo data removed:\n{summary}", title="Cleanup Complete")

    return deleted_counts
