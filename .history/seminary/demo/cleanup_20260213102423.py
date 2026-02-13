import frappe

DEMO_TAG = "Seminary Demo Data"

# Order matters — delete children before parents

DEMO_DOCTYPES = [
    "Course Enrollment Individual",  # ← first
    "Course Schedule",
    "Program Enrollment",
    "Student",
    "Customer",
    "Instructor",
    "Course",
    "Program",
    "Academic Term",
    "Academic Year",
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

    for doctype in DEMO_DOCTYPES:
        # Find all docs with the demo tag
        tagged_docs = frappe.get_all(
            "Tag Link",
            filters={
                "document_type": doctype,
                "tag": DEMO_TAG
            },
            pluck="document_name"
        )

        count = 0
        for doc_name in tagged_docs:
            try:
                doc = frappe.get_doc(doctype, doc_name)

                # Cancel if submittable and submitted
                if doc.meta.is_submittable and doc.docstatus == 1:
                    doc.flags.ignore_permissions = True
                    doc.cancel()

                frappe.delete_doc(
                    doctype,
                    doc_name,
                    force=True,
                    ignore_permissions=True,
                    delete_permanently=True
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