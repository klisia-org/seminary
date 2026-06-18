# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Move Internship Type Advisor Slot rows into Academic Unit capabilities (ADR 059).

Each slot (instructor + max/current students) becomes an Internship Advisor
capability on the instructor's membership in the type's advisor unit. The slot
child is retained one release for safety; this patch is idempotent.

A type whose advisor unit cannot be resolved (no explicit Advisor Pool Unit and
no backing-course unit) is skipped and logged — an admin sets the unit and the
pool re-forms; auto-assign for that type stays inert until then.
"""

import frappe

from seminary.partner.doctype.internship_type.internship_type import advisor_unit

ROUTE = "Internship Advisor"


def execute():
    if not frappe.db.exists("DocType", "Academic Unit Membership"):
        return

    capability = frappe.db.get_value("Faculty Capability", {"routes_to": ROUTE}, "name")
    if not capability:
        return

    skipped = []
    migrated = 0
    types = frappe.get_all(
        "Internship Type", filters={"auto_assign_faculty": 1}, pluck="name"
    )
    for type_name in types:
        slots = frappe.get_all(
            "Internship Type Advisor Slot",
            filters={"parent": type_name},
            fields=["instructor", "max_students", "current_students"],
        )
        if not slots:
            continue

        unit = advisor_unit(type_name)
        if not unit:
            skipped.append(type_name)
            continue

        for slot in slots:
            person = frappe.db.get_value("Instructor", slot.instructor, "person")
            if not person:
                continue
            if _ensure_capability(unit, person, slot, capability):
                migrated += 1

    frappe.db.commit()
    print(f"Internship advisor slots migrated into capabilities: {migrated}.")
    if skipped:
        print(
            "Skipped (no resolvable Advisor Pool Unit — set one on the type): "
            + ", ".join(skipped)
        )


def _ensure_capability(unit, person, slot, capability):
    """Upsert the membership and its Internship Advisor capability row, carrying
    the slot's caps. Returns True when a capability row was added."""
    name = frappe.db.get_value(
        "Academic Unit Membership", {"unit": unit, "person": person}, "name"
    )
    membership = (
        frappe.get_doc("Academic Unit Membership", name)
        if name
        else frappe.get_doc(
            {
                "doctype": "Academic Unit Membership",
                "unit": unit,
                "person": person,
                "is_active": 1,
            }
        )
    )
    if any(c.capability == capability for c in membership.capabilities):
        return False
    membership.append(
        "capabilities",
        {
            "capability": capability,
            "max_students": slot.max_students or 0,
            "current_students": slot.current_students or 0,
        },
    )
    membership.save(ignore_permissions=True)
    return True
