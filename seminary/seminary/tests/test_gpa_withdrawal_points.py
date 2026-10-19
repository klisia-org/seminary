# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""WF / FA grade points. A scale's own interval for the code wins; without
one, the wf_gpa / fa_gpa flag decides whether the code counts as zero (a
Descriptive scale cannot give WF its own 0, F already holds it). From PR #244."""

import frappe
from frappe.tests import UnitTestCase

from seminary.seminary.gpa import _points_from_code


def _scale(wf_gpa=0, fa_gpa=0, extra=()):
    return frappe._dict(
        grscale_type="Descriptive",
        wf_code="WF",
        wf_gpa=wf_gpa,
        fa_code="FA",
        fa_gpa=fa_gpa,
        intervals=[
            frappe._dict(grade_code="A", threshold=4.0),
            frappe._dict(grade_code="F", threshold=0.0),
            *extra,
        ],
    )


def _points(code, scale):
    return _points_from_code(frappe._dict(pec_finalgradecode=code), scale, 4.0)


class TestWithdrawalFailingPoints(UnitTestCase):
    def test_wf_counts_as_zero_when_flagged(self):
        self.assertEqual(_points("WF", _scale(wf_gpa=1)), 0.0)

    def test_wf_stays_out_when_not_flagged(self):
        self.assertIsNone(_points("WF", _scale(wf_gpa=0)))

    def test_fa_follows_its_own_flag(self):
        self.assertEqual(_points("FA", _scale(fa_gpa=1)), 0.0)
        self.assertIsNone(_points("FA", _scale(fa_gpa=0)))
        self.assertIsNone(_points("FA", _scale(wf_gpa=1)))

    def test_a_wf_interval_keeps_its_value(self):
        wf = frappe._dict(grade_code="WF", threshold=0.5)
        self.assertEqual(_points("WF", _scale(wf_gpa=1, extra=[wf])), 0.5)

    def test_ordinary_codes_still_read_the_interval(self):
        self.assertEqual(_points("A", _scale(wf_gpa=1)), 4.0)
        self.assertIsNone(_points("B", _scale(wf_gpa=1)))
