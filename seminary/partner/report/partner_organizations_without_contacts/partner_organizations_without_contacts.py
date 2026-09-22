# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Partner Organizations with nobody actively representing them (ADR 077).

When the last portal contact leaves, the organization is deliberately left in
place: it may be perfectly real and merely between people, and auto-removing it
would destroy a listing, its job openings and its history on a timing
coincidence. Resolving it is staff's call, exactly as approving a listing is —
this report is how they find the ones waiting on that call.

"Without contacts" means no contact row in `Active` relationship status. A row
left as `Former` still records who acted for the organization and does not keep
it off this list.
"""

import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}
    return _columns(), _data(filters)


def _columns():
    return [
        {
            "label": _("Organization"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Partner Organization",
            "width": 220,
        },
        {
            "label": _("Name"),
            "fieldname": "organization_name",
            "fieldtype": "Data",
            "width": 240,
        },
        {
            "label": _("Listing Status"),
            "fieldname": "listing_status",
            "fieldtype": "Data",
            "width": 140,
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 110,
        },
        {"label": _("City"), "fieldname": "city", "fieldtype": "Data", "width": 140},
        {
            "label": _("Former Contacts"),
            "fieldname": "former_contacts",
            "fieldtype": "Int",
            "width": 130,
        },
        {
            "label": _("Last Contact Left"),
            "fieldname": "last_left",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": _("Open Job Openings"),
            "fieldname": "open_openings",
            "fieldtype": "Int",
            "width": 150,
        },
    ]


def _data(filters):
    conditions = {}
    if filters.get("listing_status"):
        conditions["listing_status"] = filters["listing_status"]

    orgs = frappe.get_all(
        "Partner Organization",
        filters=conditions,
        fields=["name", "organization_name", "listing_status", "status", "city"],
        order_by="modified desc",
    )
    if not orgs:
        return []

    names = [o.name for o in orgs]
    rows = frappe.get_all(
        "Partner Contact",
        filters={"parent": ["in", names], "parenttype": "Partner Organization"},
        fields=["parent", "relationship_status", "modified"],
    )
    active, former, last_left = set(), {}, {}
    for r in rows:
        if r.relationship_status == "Active":
            active.add(r.parent)
        else:
            former[r.parent] = former.get(r.parent, 0) + 1
            # The most recent row touched is the best available proxy for when
            # the relationship ended; Partner Contact carries no `left_on`.
            if r.parent not in last_left or r.modified > last_left[r.parent]:
                last_left[r.parent] = r.modified

    orphaned = [o for o in orgs if o.name not in active]
    if not orphaned:
        return []

    # Openings still live on an org nobody represents are the urgent case: an
    # applicant can apply and there is no one to answer.
    openings = frappe.get_all(
        "Partner Job Opening",
        filters={
            "partner_org": ["in", [o.name for o in orphaned]],
            "status": "Open",
        },
        fields=["partner_org"],
    )
    open_count = {}
    for o in openings:
        open_count[o.partner_org] = open_count.get(o.partner_org, 0) + 1

    for o in orphaned:
        o["former_contacts"] = former.get(o.name, 0)
        left = last_left.get(o.name)
        o["last_left"] = frappe.utils.format_datetime(left, "medium") if left else ""
        o["open_openings"] = open_count.get(o.name, 0)
    return orphaned
