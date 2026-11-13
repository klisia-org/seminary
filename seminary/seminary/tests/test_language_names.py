# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Language names: English ISO names stored for editors, native names derived for readers."""

import frappe
from frappe.tests import IntegrationTestCase as FrappeTestCase

from seminary import language as languages


class TestLanguageNames(FrappeTestCase):
    def setUp(self):
        self.kept = frappe.db.get_value("Language", "kn", "language_name")

    def tearDown(self):
        frappe.db.set_value("Language", "kn", "language_name", self.kept)

    def test_english_names(self):
        self.assertEqual(languages.english_name("kn"), "Kannada")
        self.assertEqual(languages.english_name("pt-BR"), "Portuguese (Brazil)")
        self.assertEqual(languages.english_name("sw"), "Swahili")
        self.assertEqual(languages.english_name("sr-CS"), "Serbian (Latin)")
        self.assertEqual(languages.english_name("grc"), "Ancient Greek (to 1453)")
        self.assertIsNone(languages.english_name("zz"))

    def test_native_names(self):
        # Frappe's own name first, then Babel's, then the stored one.
        self.assertEqual(languages.native_name("kn"), "ಕನ್ನಡ")
        self.assertEqual(languages.native_name("sr-CS"), "Srpski")
        self.assertEqual(languages.native_name("xh"), "IsiXhosa")
        self.assertEqual(
            languages.native_name("grc", "Ancient Greek (to 1453)"),
            "Ancient Greek (to 1453)",
        )

    def test_rename_only_frappe_names(self):
        frappe.db.set_value("Language", "kn", "language_name", "ಕನ್ನಡ")
        languages.rename_frappe_languages()
        self.assertEqual(
            frappe.db.get_value("Language", "kn", "language_name"), "Kannada"
        )
        # A site's own name stays.
        frappe.db.set_value("Language", "kn", "language_name", "Kannada (Karnataka)")
        languages.rename_frappe_languages()
        self.assertEqual(
            frappe.db.get_value("Language", "kn", "language_name"),
            "Kannada (Karnataka)",
        )

    def test_in_context_translation_untouched(self):
        languages.rename_frappe_languages()
        if frappe.db.exists("Language", "eo"):
            self.assertEqual(
                frappe.db.get_value("Language", "eo", "language_name"),
                languages.frappe_names()["eo"],
            )

    def test_native_choices_sorted_by_native_name(self):
        choices = languages.native_choices(["de", "kn", "pt"])
        self.assertEqual([c for c, _ in choices], ["de", "pt", "kn"])
        self.assertEqual(dict(choices)["de"], "Deutsch")
