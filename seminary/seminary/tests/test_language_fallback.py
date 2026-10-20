# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Per-language rows fall back to the parent language (aretenic decision 071).

A `pt` Communication Template version serves a `pt-BR` reader, an exact match still wins, and a
language with neither falls to the blank version. The template is built in memory, not saved.
"""

import frappe
from frappe.tests import UnitTestCase

from seminary.language import language_candidates


class TestLanguageFallback(UnitTestCase):
    def test_candidates(self):
        self.assertEqual(language_candidates("pt-BR"), ["pt-BR", "pt"])
        self.assertEqual(language_candidates("pt_BR"), ["pt_BR", "pt"])
        self.assertEqual(language_candidates("es"), ["es"])
        self.assertEqual(language_candidates(None), [])

    def _template(self, *languages):
        doc = frappe.new_doc("Communication Template")
        for lang in languages:
            doc.append(
                "versions",
                {"channel": "Email", "language": lang, "body": lang or "blank"},
            )
        return doc

    def test_parent_language_serves_variant(self):
        doc = self._template("", "pt")
        self.assertEqual(doc.get_version("Email", "pt-BR").language, "pt")

    def test_exact_language_wins_over_parent(self):
        doc = self._template("", "pt", "pt-BR")
        self.assertEqual(doc.get_version("Email", "pt-BR").language, "pt-BR")

    def test_unmatched_language_gets_blank_version(self):
        doc = self._template("", "pt")
        self.assertEqual(doc.get_version("Email", "es").body, "blank")
