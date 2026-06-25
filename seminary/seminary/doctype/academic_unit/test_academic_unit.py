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
