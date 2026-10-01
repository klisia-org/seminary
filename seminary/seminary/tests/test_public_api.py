# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Two public entry points for other apps: program_audit and grade_points."""

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from seminary.seminary import api, gpa


class TestProgramAudit(UnitTestCase):
    def test_it_is_the_private_audit_without_a_gate(self):
        with patch.object(api, "_program_audit", return_value={"ok": 1}) as private:
            self.assertEqual(api.program_audit("PE-1"), {"ok": 1})
        private.assert_called_once_with("PE-1")


class TestGradePoints(UnitTestCase):
    def letters(self):
        return frappe._dict(
            grscale_type="Descriptive",
            intervals=[
                frappe._dict(grade_code="A", threshold=4.0),
                frappe._dict(grade_code="D", threshold=1.0),
                frappe._dict(grade_code="F", threshold=0.0),
            ],
        )

    def points(self):
        return frappe._dict(grscale_type="Points", maxnumgrade=100, intervals=[])

    def row(self, code, num=None):
        return frappe._dict(pec_finalgradecode=code, pec_finalgradenum=num, course="CS-1")

    def test_a_letter_scale_reads_the_code_alone(self):
        with patch.object(gpa, "_resolve_grading_scale", return_value=self.letters()):
            self.assertEqual(gpa.grade_points(self.row("D"), 4.0), 1.0)
            self.assertEqual(gpa.grade_points(self.row("F"), 4.0), 0.0)

    def test_a_points_scale_needs_the_number(self):
        with patch.object(gpa, "_resolve_grading_scale", return_value=self.points()):
            self.assertEqual(gpa.grade_points(self.row("A", 75), 4.0), 3.0)
            self.assertIsNone(gpa.grade_points(self.row("A"), 4.0))

    def test_no_code_no_basis_or_no_scale_is_none(self):
        with patch.object(gpa, "_resolve_grading_scale", return_value=None):
            self.assertIsNone(gpa.grade_points(self.row("A"), 4.0))
        self.assertIsNone(gpa.grade_points(self.row(None), 4.0))
        self.assertIsNone(gpa.grade_points(self.row("A"), 0))
