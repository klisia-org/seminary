# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Academic Unit Faculty Audit (ADR 059).

Memberships, capabilities, and capacity grouped by Academic Unit, with an Issue
column flagging gaps a Seminary Manager should fix: a unit with no chair, a
member wired with no capability, and a capability that is over capacity.
"""

import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}
    only_issues = filters.get("only_issues")
    unit_filter = filters.get("academic_unit")

    columns = [
        {
            "label": _("Academic Unit"),
            "fieldname": "academic_unit",
            "fieldtype": "Link",
            "options": "Academic Unit",
            "width": 200,
        },
        {
            "label": _("Type"),
            "fieldname": "unit_type",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": _("Member"),
            "fieldname": "member",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Capability"),
            "fieldname": "capability",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Capacity"),
            "fieldname": "capacity",
            "fieldtype": "Data",
            "width": 90,
        },
        {"label": _("Issue"), "fieldname": "issue", "fieldtype": "Data", "width": 150},
    ]

    unit_cond = {"name": unit_filter} if unit_filter else {}
    units = frappe.get_all(
        "Academic Unit",
        filters=unit_cond,
        fields=["name", "unit_type", "chair"],
        order_by="name",
    )

    rows = []
    for u in units:
        if not u.chair:
            rows.append(
                {
                    "academic_unit": u.name,
                    "unit_type": u.unit_type,
                    "member": "",
                    "capability": "",
                    "capacity": "",
                    "issue": _("No chair"),
                }
            )
        memberships = frappe.get_all(
            "Academic Unit Membership",
            filters={"unit": u.name, "is_active": 1},
            fields=["name", "person_name", "instructor"],
            order_by="person_name",
        )
        for m in memberships:
            caps = frappe.get_all(
                "Academic Unit Capability",
                filters={"parent": m.name},
                fields=["capability", "max_students", "current_students"],
            )
            if not caps:
                rows.append(
                    {
                        "academic_unit": u.name,
                        "unit_type": u.unit_type,
                        "member": m.person_name,
                        "capability": "",
                        "capacity": "",
                        "issue": _("No capability"),
                    }
                )
                continue
            for c in caps:
                cur = c.current_students or 0
                over = c.max_students and cur >= c.max_students
                rows.append(
                    {
                        "academic_unit": u.name,
                        "unit_type": u.unit_type,
                        "member": m.person_name,
                        "capability": c.capability,
                        "capacity": (
                            f"{cur}/{c.max_students}" if c.max_students else f"{cur}/∞"
                        ),
                        "issue": _("Over capacity") if over else "",
                    }
                )

    if only_issues:
        rows = [r for r in rows if r["issue"]]
    return columns, rows
