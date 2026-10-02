# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from seminary.seminary.doctype.program_level.program_level import (
    SEEDED,
    programs_in_tier,
    seed_program_levels,
    tier_of_program,
)


class TestProgramLevel(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        seed_program_levels()

    def test_seeded_levels_exist_with_their_tier(self):
        for name, tier in SEEDED.items():
            self.assertEqual(
                frappe.db.get_value("Program Level", name, "degree_tier"), tier
            )

    def test_a_seeded_level_cannot_be_cancelled_deleted_or_renamed(self):
        doc = frappe.get_doc("Program Level", "Master of Divinity")
        self.assertRaises(frappe.ValidationError, doc.cancel)
        self.assertRaises(
            frappe.ValidationError, frappe.delete_doc, "Program Level", doc.name
        )
        self.assertRaises(
            frappe.ValidationError,
            frappe.rename_doc,
            "Program Level",
            doc.name,
            "MDiv Level",
        )

    def test_a_seeded_level_keeps_its_tier_but_not_its_policies(self):
        doc = frappe.get_doc("Program Level", "Master of Divinity")
        doc.min_graduation_gpa = 2.5
        doc.save()
        doc.degree_tier = "Doctoral"
        self.assertRaises(frappe.ValidationError, doc.save)

    def test_a_school_level_is_its_own(self):
        doc = frappe.get_doc(
            {
                "doctype": "Program Level",
                "pgm_level": "ZZ Diploma",
                "degree_tier": "Certificate",
            }
        )
        doc.insert()
        doc.submit()
        doc.cancel()
        frappe.delete_doc("Program Level", doc.name)
        self.assertFalse(frappe.db.exists("Program Level", "ZZ Diploma"))

    def test_programs_in_a_tier(self):
        program = frappe.get_doc(
            {
                "doctype": "Program",
                "program_name": "ZZ Tier MACL",
                "program_abbreviation": "ZZTMACL",
                "program_level": "Master of Arts",
            }
        ).insert(ignore_permissions=True)
        self.assertEqual(tier_of_program(program.name), "Master's")
        self.assertIn(program.name, programs_in_tier("Master's"))
        self.assertNotIn(program.name, programs_in_tier("Doctoral"))
