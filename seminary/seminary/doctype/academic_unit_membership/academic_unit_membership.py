# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# routes_to value that does NOT require an Instructor record — a board/committee
# seat may be held by a plain Person. Every other capability routes academic work
# that needs a faculty record.
NON_FACULTY_ROUTE = "Committee/Board Member"


class AcademicUnitMembership(Document):
    def validate(self):
        self._sync_instructor_from_person()
        self._validate_unique_membership()
        self._validate_instructor_for_capabilities()

    def _sync_instructor_from_person(self):
        """Instructor is derived, not entered — it reflects the Person's Instructor
        record (single source: the Instructor.person link). A person with no
        Instructor record is a non-instructor (board/committee only)."""
        self.instructor = (
            frappe.db.get_value("Instructor", {"person": self.person}, "name")
            if self.person
            else None
        )

    def _validate_unique_membership(self):
        """One membership per (unit, person) — Frappe has no declarative composite
        unique, so enforce it here."""
        if not (self.unit and self.person):
            return
        dupe = frappe.db.exists(
            "Academic Unit Membership",
            {
                "unit": self.unit,
                "person": self.person,
                "name": ("!=", self.name),
            },
        )
        if dupe:
            frappe.throw(
                _("{0} already has a membership in {1}.").format(
                    self.person_name or self.person, self.unit
                )
            )

    def _validate_instructor_for_capabilities(self):
        """Academic-routing capabilities require an Instructor record; only a
        Committee/Board Member seat may be held by a person without one."""
        if self.instructor:
            return
        for row in self.capabilities:
            routes_to = frappe.db.get_value(
                "Faculty Capability", row.capability, "routes_to"
            )
            if routes_to and routes_to != NON_FACULTY_ROUTE:
                frappe.throw(
                    _(
                        "Capability {0} routes academic work and needs an Instructor — "
                        "set the Instructor, or use only Committee/Board Member for a "
                        "non-instructor member."
                    ).format(row.capability)
                )
