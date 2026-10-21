"""Fill who graded and when on submissions graded before the fields existed
(privatedocs p015 §1).

The first Version that moved the status to Graded gives both: its owner and
its creation. A submission with no such Version keeps the fields as they are;
its grading time is unknown. Reruns skip anything already filled.
"""

import json

import frappe

DOCTYPES = ("Assignment Submission", "Discussion Submission")


def first_graded_versions(doctype):
    """{docname: (owner, creation)} of the first Version that set status to Graded."""
    found = {}
    for name, owner, creation, data in frappe.get_all(
        "Version",
        filters={"ref_doctype": doctype, "data": ("like", '%"Graded"%')},
        fields=["docname", "owner", "creation", "data"],
        order_by="creation asc",
        as_list=True,
    ):
        if name in found:
            continue
        try:
            changed = (json.loads(data or "{}") or {}).get("changed") or []
        except ValueError:
            continue
        if any(
            len(row) >= 3 and row[0] == "status" and row[2] == "Graded"
            for row in changed
        ):
            found[name] = (owner, creation)
    return found


def execute():
    for doctype in DOCTYPES:
        if not frappe.db.has_column(doctype, "graded_on"):
            continue
        pending = frappe.get_all(
            doctype,
            filters={"status": "Graded", "graded_on": ("is", "not set")},
            pluck="name",
        )
        if not pending:
            continue
        versions = first_graded_versions(doctype)
        for name in pending:
            hit = versions.get(name)
            if not hit:
                continue
            frappe.db.set_value(
                doctype,
                name,
                {"evaluator": hit[0], "graded_on": hit[1]},
                update_modified=False,
            )
