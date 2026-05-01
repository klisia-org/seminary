import frappe

DEMO_TAG = "Seminary Demo Data"

# Order matters — delete children before parents

DEMO_DOCTYPES = [
    # 1. Deepest children first
    "Course Enrollment Individual",  # ← first
    "Course Schedule",
    "Program Enrollment",
    "Student",
    # 2. Auto-created by scripts/hooks
    "Customer",
    # 3. Core demo records
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

    # Sales Invoices are auto-created when CEIs are submitted (not tagged as demo).
    # Delete them first so CEI deletion isn't blocked by FK references.
    demo_ceis = frappe.get_all(
        "Tag Link",
        filters={"document_type": "Course Enrollment Individual", "tag": DEMO_TAG},
        pluck="document_name",
    )
    if demo_ceis:
        linked_invoices = frappe.get_all(
            "Sales Invoice",
            filters={"custom_cei": ("in", demo_ceis)},
            pluck="name",
        )
        si_count = 0
        for inv_name in linked_invoices:
            try:
                # Force docstatus=2 directly to bypass GL validations / payment checks
                frappe.db.set_value(
                    "Sales Invoice", inv_name, "docstatus", 2, update_modified=False
                )
                frappe.delete_doc(
                    "Sales Invoice",
                    inv_name,
                    force=True,
                    ignore_permissions=True,
                    delete_permanently=True,
                )
                si_count += 1
            except Exception:
                frappe.log_error(f"Failed to delete Sales Invoice {inv_name}")
        if si_count:
            deleted_counts["Sales Invoice"] = si_count

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
