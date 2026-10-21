# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Bible book alias table (integrations/bible_books.py).

The lookup is built with setdefault, so an alias that normalizes to a key another book already
owns is dropped without a word, and one placed earlier steals that key. These tests catch it when
a language's names are added.
"""

from frappe.tests import UnitTestCase

from seminary.seminary.integrations.bible_books import (
    _BOOKS,
    BOOK_ALIASES,
    BOOK_ORDER,
    normalize,
)


class TestBibleBooks(UnitTestCase):
    def test_every_alias_resolves_to_its_own_book(self):
        clashes = [
            (alias, osis, BOOK_ALIASES[normalize(alias)])
            for osis, aliases in _BOOKS
            for alias in aliases
            if BOOK_ALIASES[normalize(alias)] != osis
        ]
        self.assertEqual(clashes, [], "alias, its book, the book that owns the key")

    def test_protestant_canon(self):
        self.assertEqual(len(BOOK_ORDER), 66)

    def test_spanish_names(self):
        for name, osis in {
            "Jueces": "JDG",
            "1 Reyes": "1KI",
            "Hechos": "ACT",
            "Hch": "ACT",
            "Santiago": "JAS",
            "Stg": "JAS",
            "1 Juan": "1JN",
            "Apocalipsis": "REV",
        }.items():
            self.assertEqual(BOOK_ALIASES[normalize(name)], osis, name)

    def test_ambiguous_jo_stays_out(self):
        self.assertNotIn("jo", BOOK_ALIASES)
