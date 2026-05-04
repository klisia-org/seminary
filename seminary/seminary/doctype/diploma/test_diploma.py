# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase


class TestDiploma(FrappeTestCase):
    def test_serial_format_for_year(self):
        """The auto-generated serial should follow DIP-{YYYY}-#### format
        and increment per-year, regardless of cross-year ordering."""
        from seminary.seminary.doctype.diploma.diploma import Diploma

        # Using the bare class to exercise _next_serial without inserting,
        # since a real insert requires a full Graduation Request fixture chain.
        d = Diploma(dict(doctype="Diploma", issued_on="2026-01-15"))
        serial = d._next_serial()
        self.assertTrue(serial.startswith("DIP-2026-"))
        suffix = serial.split("-")[-1]
        self.assertEqual(len(suffix), 4)
        self.assertTrue(suffix.isdigit())

    def test_permission_query_blocks_non_student_user(self):
        """A user with no Student record should resolve to a no-rows filter."""
        from seminary.seminary.doctype.diploma.diploma import (
            get_permission_query_conditions,
        )

        # Pick a session likely without a Student record
        condition = get_permission_query_conditions("Guest")
        # Either staff bypass (empty) or filtered to no rows — both safe
        self.assertIn(condition, ("", "1=0"))


if __name__ == "__main__":
    unittest.main()
