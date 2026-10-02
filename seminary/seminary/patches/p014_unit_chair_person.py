"""Academic Unit.chair now names a Person, not an Instructor (p014).

Each stored chair is an Instructor name; it becomes that Instructor's Person.
Instructor.person is mandatory, so every chair has one. A value that is already a
Person (a rerun) is kept, and one that matches neither is cleared and logged.
"""

import frappe


def execute():
    for unit, chair in frappe.get_all(
        "Academic Unit",
        filters={"chair": ("is", "set")},
        fields=["name", "chair"],
        as_list=True,
    ):
        person = frappe.db.get_value("Instructor", chair, "person")
        if not person and frappe.db.exists("Person", chair):
            person = chair
        if person == chair:
            continue
        if not person:
            print(
                f"p014: cleared chair {chair!r} of {unit!r}, which matches no Instructor or Person"
            )
        frappe.db.set_value(
            "Academic Unit",
            unit,
            {
                "chair": person,
                "chair_name": (
                    frappe.db.get_value("Person", person, "full_name")
                    if person
                    else None
                ),
            },
            update_modified=False,
        )
