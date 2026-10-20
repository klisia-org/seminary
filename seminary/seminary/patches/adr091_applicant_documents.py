"""decisions/091 §10: Student Applicant's two Attach fields become rows.

`document_id` and `education_docs` left the doctype; Frappe keeps their columns,
so the files are still readable here. Each file becomes a row in the applicant's
`documents` table and, when the applicant has a Person, a Person Document --
Accepted for an Admitted applicant (the school already took them), Submitted
otherwise. Nothing is dropped. The two Document Types are created only if there
is a file to put in them.

Custom web forms on Student Applicant lose the two fields and gain `documents`.
"""

import frappe

FIELDS = (
    ("document_id", "Identity document"),
    ("education_docs", "Education documents"),
)


def execute():
    _migrate_files()
    _migrate_web_forms()


def _columns():
    return set(frappe.db.get_table_columns("Student Applicant"))


def _ensure_type(name):
    if not frappe.db.exists("Document Type", name):
        frappe.get_doc(
            {
                "doctype": "Document Type",
                "type_name": name,
                "needs_review": 1,
                "is_active": 1,
            }
        ).insert(ignore_permissions=True)
    return name


def _migrate_files():
    from seminary.seminary.requirements import create_person_document

    columns = _columns()
    present = [(f, t) for f, t in FIELDS if f in columns]
    if not present:
        return
    select = ", ".join(f"`{f}`" for f, _t in present)
    where = " or ".join(f"ifnull(`{f}`, '') != ''" for f, _t in present)
    rows = frappe.db.sql(
        f"select name, person, application_status, {select} "  # nosec B608 -- columns are the FIELDS constants above
        f"from `tabStudent Applicant` where {where}",
        as_dict=True,
    )
    for app in rows:
        existing = set(
            frappe.get_all(
                "Student Applicant Document",
                filters={"parent": app.name, "parenttype": "Student Applicant"},
                pluck="file",
            )
        )
        idx = len(existing)
        for field, type_name in present:
            url = app.get(field)
            if not url or url in existing:
                continue
            document_type = _ensure_type(type_name)
            person_document = None
            if app.person and frappe.db.exists("Person", app.person):
                person_document = create_person_document(
                    app.person,
                    document_type,
                    url,
                    accepted=app.application_status == "Admitted",
                    by="Administrator",
                ).name
            idx += 1
            frappe.get_doc(
                {
                    "doctype": "Student Applicant Document",
                    "parent": app.name,
                    "parenttype": "Student Applicant",
                    "parentfield": "documents",
                    "idx": idx,
                    "document_type": document_type,
                    "file": url,
                    "person_document": person_document,
                }
            ).db_insert()


def _migrate_web_forms():
    for name in frappe.get_all(
        "Web Form", filters={"doc_type": "Student Applicant"}, pluck="name"
    ):
        wf = frappe.get_doc("Web Form", name)
        names = [r.fieldname for r in wf.web_form_fields]
        if not ({"document_id", "education_docs"} & set(names)):
            continue
        keep, anchor = [], None
        for r in wf.web_form_fields:
            if r.fieldname in ("document_id", "education_docs"):
                anchor = anchor if anchor is not None else len(keep)
                continue
            keep.append(r)
        wf.web_form_fields = keep
        if "documents" not in names:
            row = wf.append(
                "web_form_fields",
                {
                    "fieldname": "documents",
                    "fieldtype": "Table",
                    "label": "Documents",
                    "options": "Student Applicant Document",
                },
            )
            wf.web_form_fields.remove(row)
            wf.web_form_fields.insert(anchor, row)
        for i, r in enumerate(wf.web_form_fields, start=1):
            r.idx = i
        wf.flags.ignore_permissions = True
        wf.save()
