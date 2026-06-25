# Copyright (c) 2026, Frappe Technologies and contributors
# See license.txt

"""Person-keyed unit capability engine (ADR 062):

- an organizational capacity ("Oversees Unit Training") is held by a non-instructor Person and is
  found by the person-keyed helpers but NOT by the instructor-keyed ones;
- academic routing still resolves through the instructor-bearing subset (regression);
- membership validation requires an Instructor only for requires_instructor capabilities.
"""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import faculty

UNIT = "ZZ Cap Unit"
UNIT_B = "ZZ Cap Unit B"
ORG_ROUTE = faculty.TRAINING_OVERSIGHT_ROUTE  # "Oversees Unit Training"
ACAD_ROUTE = "Thesis/CP Advisor"


class IntegrationTestFacultyCapability(IntegrationTestCase):
    def setUp(self):
        for u in (UNIT, UNIT_B):
            if not frappe.db.exists("Academic Unit", u):
                frappe.get_doc(
                    {
                        "doctype": "Academic Unit",
                        "unit_name": u,
                        "unit_type": "Administrative Office",
                    }
                ).insert(ignore_permissions=True)
        self.overseer = self._person("orgoverseer_test@example.com", "Overseer")
        self.advisor_person = self._person("advisorperson_test@example.com", "Advisor")
        self.advisor_instructor = self._instructor(
            self.advisor_person, "advisorperson_test@example.com", "Advisor Faculty"
        )

    def tearDown(self):
        for code in (UNIT, UNIT_B):
            for m in frappe.get_all(
                "Academic Unit Membership", filters={"unit": code}, pluck="name"
            ):
                frappe.delete_doc(
                    "Academic Unit Membership", m, force=1, ignore_permissions=True
                )
        for u in (UNIT, UNIT_B):
            if frappe.db.exists("Academic Unit", u):
                frappe.delete_doc("Academic Unit", u, force=1, ignore_permissions=True)

    # --- fixtures ---------------------------------------------------------------
    def _person(self, user, first_name):
        if not frappe.db.exists("User", user):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": user,
                    "first_name": first_name,
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)
        p = frappe.db.get_value("Person", {"user": user}, "name")
        return (
            p
            or frappe.get_doc(
                {
                    "doctype": "Person",
                    "first_name": first_name,
                    "user": user,
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def _instructor(self, person, user, name):
        existing = frappe.db.get_value("Instructor", {"person": person}, "name")
        if existing:
            return existing
        return (
            frappe.get_doc(
                {
                    "doctype": "Instructor",
                    "instructor_name": name,
                    "person": person,
                    "user": user,
                    "prof_email": user,
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def _membership(self, unit, person, capability):
        return frappe.get_doc(
            {
                "doctype": "Academic Unit Membership",
                "unit": unit,
                "person": person,
                "is_active": 1,
                "capabilities": [{"capability": capability}],
            }
        ).insert(ignore_permissions=True)

    # --- tests ------------------------------------------------------------------
    def test_org_capacity_is_person_keyed(self):
        """A non-instructor overseer is resolvable by person, invisible to instructor helpers."""
        self._membership(UNIT, self.overseer, "Unit Training Overseer")
        self.assertTrue(faculty.holds_unit_capacity(self.overseer, ORG_ROUTE, UNIT))
        self.assertIn(self.overseer, faculty.persons_with_capacity(UNIT, ORG_ROUTE))
        self.assertIn(UNIT, faculty.units_with_capacity(self.overseer, ORG_ROUTE))
        # instructor-keyed view sees nobody (the overseer has no Instructor record)
        self.assertEqual(faculty.wired_instructors(UNIT, ORG_ROUTE), set())

    def test_academic_routing_unchanged(self):
        """An instructor with an academic capability still resolves through the instructor subset."""
        self._membership(UNIT, self.advisor_person, ACAD_ROUTE)
        self.assertIn(
            self.advisor_instructor, faculty.wired_instructors(UNIT, ACAD_ROUTE)
        )
        self.assertTrue(
            faculty.holds_capability(self.advisor_instructor, ACAD_ROUTE, UNIT)
        )
        # and the person-keyed view also sees them (one engine)
        self.assertIn(
            self.advisor_person, faculty.persons_with_capacity(UNIT, ACAD_ROUTE)
        )

    def test_membership_validation_requires_instructor_only_when_flagged(self):
        # org capacity: no instructor needed → accepted
        self._membership(UNIT_B, self.overseer, "Unit Training Overseer")
        # academic capacity held by a non-instructor → rejected
        bad = frappe.get_doc(
            {
                "doctype": "Academic Unit Membership",
                "unit": UNIT_B,
                "person": self.overseer,
                "is_active": 1,
                "capabilities": [{"capability": "Thesis/CP Advisor"}],
            }
        )
        # (different unit avoids the unique (unit, person) collision with the row above)
        bad.unit = UNIT
        self.assertRaises(frappe.ValidationError, bad.insert)
