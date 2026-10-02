# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from seminary.seminary.doctype.academic_unit.academic_unit import (
    governance_lock_applies,
)

# Fields the governance record keeps on a governing body's memberships (p014). Roster
# order and capabilities stay with seminary.
GOVERNED_FIELDS = ("unit", "person", "is_active")


class AcademicUnitMembership(Document):
    def validate(self):
        self._validate_governance_lock()
        self._sync_instructor_from_person()
        self._validate_unique_membership()
        self._validate_instructor_for_capabilities()

    def on_trash(self):
        if governance_lock_applies(self.unit):
            frappe.throw(_governed_message().format(self.unit))

    def _validate_governance_lock(self):
        """A governing body's members follow its seats (p014): only the sync may add one,
        move one or change whether it is active."""
        units = {self.unit}
        before = None if self.is_new() else self.get_doc_before_save()
        if before:
            units.add(before.unit)
        for unit in units:
            if not governance_lock_applies(unit):
                continue
            if before is None or any(
                self.get(f) != before.get(f) for f in GOVERNED_FIELDS
            ):
                frappe.throw(_governed_message().format(unit))

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
        """Capabilities flagged ``requires_instructor`` need a faculty record (ADR 062);
        organizational capacities (the flag cleared, e.g. Committee/Board Member,
        Oversees Unit Training) may be held by a plain Person."""
        if self.instructor:
            return
        for row in self.capabilities:
            if frappe.db.get_value(
                "Faculty Capability", row.capability, "requires_instructor"
            ):
                frappe.throw(
                    _(
                        "Capability {0} routes academic work and needs an Instructor — "
                        "set the Instructor, or use only organizational capacities "
                        "(those that do not require an instructor) for a non-instructor "
                        "member."
                    ).format(row.capability)
                )


def _governed_message():
    return _(
        "The members of {0} follow its seats in the governance record. "
        "Add, end or change the seat there."
    )
