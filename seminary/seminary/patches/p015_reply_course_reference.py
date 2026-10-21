"""Give existing portal replies the course of the message they answer
(privatedocs p015 §2).

Each reply with no reference walks ``in_reply_to`` up the thread to the first
message that carries one. When that is a Course Schedule, the reply gets it;
any other reference, or none up to the root, leaves the reply as it is.
"""

import frappe

MAX_DEPTH = 200


def execute():
    replies = frappe.get_all(
        "Communication Log",
        filters={
            "in_reply_to": ("is", "set"),
            "reference_doctype": ("is", "not set"),
        },
        pluck="name",
    )
    if not replies:
        return

    rows = {
        r.name: r
        for r in frappe.get_all(
            "Communication Log",
            filters={"in_reply_to": ("is", "set")},
            fields=["name", "in_reply_to", "reference_doctype", "reference_name"],
        )
    }

    def lookup(name):
        if name not in rows:
            rows[name] = frappe.db.get_value(
                "Communication Log",
                name,
                ["name", "in_reply_to", "reference_doctype", "reference_name"],
                as_dict=True,
            )
        return rows[name]

    for name in replies:
        seen = {name}
        parent = rows[name].in_reply_to
        reference = None
        for _depth in range(MAX_DEPTH):
            if not parent or parent in seen:
                break
            seen.add(parent)
            row = lookup(parent)
            if not row:
                break
            if row.reference_doctype:
                reference = row
                break
            parent = row.in_reply_to
        if (
            reference
            and reference.reference_doctype == "Course Schedule"
            and reference.reference_name
        ):
            frappe.db.set_value(
                "Communication Log",
                name,
                {
                    "reference_doctype": "Course Schedule",
                    "reference_name": reference.reference_name,
                },
                update_modified=False,
            )
