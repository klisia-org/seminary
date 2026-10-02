# Copyright (c) 2026, Frappe Technologies and contributors
# See license.txt

"""Org-unit hierarchy: parent_unit tree helpers + cycle guard (ADR 062)."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.doctype.academic_unit.academic_unit import (
    ancestor_units,
    descendant_units,
)

_UNITS = ("ZZ Leaf", "ZZ Mid", "ZZ Root", "ZZ Cyc B", "ZZ Cyc A")


class IntegrationTestAcademicUnit(IntegrationTestCase):
    def _unit(self, name, parent=None):
        if frappe.db.exists("Academic Unit", name):
            doc = frappe.get_doc("Academic Unit", name)
            doc.parent_unit = parent
            doc.save(ignore_permissions=True)
            return name
        return (
            frappe.get_doc(
                {
                    "doctype": "Academic Unit",
                    "unit_name": name,
                    "unit_type": "Administrative Office",
                    "parent_unit": parent,
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def tearDown(self):
        for n in _UNITS:  # children before parents
            if frappe.db.exists("Academic Unit", n):
                frappe.delete_doc("Academic Unit", n, force=1, ignore_permissions=True)

    def test_descendant_and_ancestor_units(self):
        root = self._unit("ZZ Root")
        self._unit("ZZ Mid", parent=root)
        self._unit("ZZ Leaf", parent="ZZ Mid")
        self.assertEqual(descendant_units("ZZ Root"), {"ZZ Root", "ZZ Mid", "ZZ Leaf"})
        self.assertEqual(descendant_units("ZZ Mid"), {"ZZ Mid", "ZZ Leaf"})
        self.assertEqual(descendant_units("ZZ Leaf"), {"ZZ Leaf"})
        self.assertEqual(ancestor_units("ZZ Leaf"), ["ZZ Mid", "ZZ Root"])
        self.assertEqual(ancestor_units("ZZ Root"), [])

    def test_parent_unit_rejects_self(self):
        self._unit("ZZ Cyc A")
        doc = frappe.get_doc("Academic Unit", "ZZ Cyc A")
        doc.parent_unit = "ZZ Cyc A"
        self.assertRaises(frappe.ValidationError, doc.save)

    def test_parent_unit_rejects_cycle(self):
        self._unit("ZZ Cyc A")
        self._unit("ZZ Cyc B", parent="ZZ Cyc A")  # B -> A
        doc = frappe.get_doc("Academic Unit", "ZZ Cyc A")
        doc.parent_unit = "ZZ Cyc B"  # A -> B -> A
        self.assertRaises(frappe.ValidationError, doc.save)


class IntegrationTestGovernanceLock(IntegrationTestCase):
    """A governing body's chair and members follow Aretenic's seats (p014)."""

    def setUp(self):
        if "aretenic" not in frappe.get_installed_apps():
            self.skipTest("the lock applies only with Aretenic installed")
        self.person = (
            frappe.get_doc(
                {"doctype": "Person", "first_name": "ZZ Board", "last_name": "Chair"}
            )
            .insert(ignore_permissions=True)
            .name
        )
        self.other = (
            frappe.get_doc(
                {"doctype": "Person", "first_name": "ZZ Board", "last_name": "Member"}
            )
            .insert(ignore_permissions=True)
            .name
        )
        self.unit = (
            frappe.get_doc(
                {
                    "doctype": "Academic Unit",
                    "unit_name": "ZZ Board " + frappe.generate_hash(length=6),
                    "unit_type": "Board",
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def tearDown(self):
        frappe.flags.in_governance_sync = False

    def _lock(self):
        frappe.db.set_value("Academic Unit", self.unit, "kept_by_governance_record", 1)

    def _membership(self, person):
        return frappe.get_doc(
            {
                "doctype": "Academic Unit Membership",
                "unit": self.unit,
                "person": person,
                "is_active": 1,
            }
        )

    def test_chair_is_a_person(self):
        doc = frappe.get_doc("Academic Unit", self.unit)
        doc.chair = self.person
        doc.save(ignore_permissions=True)
        self.assertEqual(doc.chair_name, "ZZ Board Chair")

    def test_unlocked_unit_is_edited_by_hand(self):
        self._membership(self.other).insert(ignore_permissions=True)
        doc = frappe.get_doc("Academic Unit", self.unit)
        doc.chair = self.person
        doc.save(ignore_permissions=True)

    def test_locked_chair_and_members_reject_direct_edits(self):
        m = self._membership(self.other).insert(ignore_permissions=True)
        self._lock()
        doc = frappe.get_doc("Academic Unit", self.unit)
        doc.chair = self.person
        self.assertRaises(frappe.ValidationError, doc.save, ignore_permissions=True)
        self.assertRaises(
            frappe.ValidationError,
            self._membership(self.person).insert,
            ignore_permissions=True,
        )
        m.reload()
        m.is_active = 0
        self.assertRaises(frappe.ValidationError, m.save, ignore_permissions=True)
        self.assertRaises(
            frappe.ValidationError,
            frappe.delete_doc,
            "Academic Unit Membership",
            m.name,
            ignore_permissions=True,
        )

    def test_display_fields_stay_editable_when_locked(self):
        m = self._membership(self.other).insert(ignore_permissions=True)
        self._lock()
        m.reload()
        m.web_order = 3
        m.save(ignore_permissions=True)
        doc = frappe.get_doc("Academic Unit", self.unit)
        doc.web_order = 2
        doc.kept_by_governance_record = 0  # only the sync may lift the lock
        doc.save(ignore_permissions=True)
        self.assertEqual(doc.kept_by_governance_record, 1)

    def test_the_sync_passes_through(self):
        self._lock()
        frappe.flags.in_governance_sync = True
        self._membership(self.person).insert(ignore_permissions=True)
        doc = frappe.get_doc("Academic Unit", self.unit)
        doc.chair = self.person
        doc.save(ignore_permissions=True)
