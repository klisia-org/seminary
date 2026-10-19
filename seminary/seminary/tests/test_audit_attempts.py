# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""Which attempt speaks for a repeated course in the program audit. Rows are
not chronological, so a passed (or exempted) course must not show as failed
because the failed row happened to come last. From PR #243."""

import frappe
from frappe.tests import UnitTestCase

from seminary.seminary.api import _best_attempt_per_course


def _pec(course, status, grade=None, section=None):
    return frappe._dict(
        course=section or f"{course}-section-{status}",
        course_name=course,
        academic_term=None,
        credits=3,
        pec_finalgradecode=grade,
        pec_finalgradenum=None,
        status=status,
    )


def _status(rows, course="CS101"):
    return _best_attempt_per_course(rows)[course]["status"]


class TestBestAttemptPerCourse(UnitTestCase):
    def test_pass_beats_fail_in_either_order(self):
        self.assertEqual(
            _status([_pec("CS101", "Pass", "C-"), _pec("CS101", "Fail", "F")]), "Pass"
        )
        self.assertEqual(
            _status([_pec("CS101", "Fail", "F"), _pec("CS101", "Pass", "C-")]), "Pass"
        )

    def test_exempt_beats_fail_in_either_order(self):
        self.assertEqual(
            _status([_pec("CS101", "Exempt"), _pec("CS101", "Fail", "F")]), "Exempt"
        )
        self.assertEqual(
            _status([_pec("CS101", "Fail", "F"), _pec("CS101", "Exempt")]), "Exempt"
        )

    def test_open_retake_beats_earlier_fail(self):
        self.assertEqual(
            _status([_pec("CS101", "Enrolled"), _pec("CS101", "Fail", "F")]), "Enrolled"
        )

    def test_pass_beats_later_withdrawal(self):
        self.assertEqual(
            _status([_pec("EL1", "Pass", "A"), _pec("EL1", "Withdrawn", "W")], "EL1"),
            "Pass",
        )

    def test_single_attempts_are_untouched(self):
        best = _best_attempt_per_course(
            [_pec("CS101", "Fail", "F"), _pec("MATH101", "Pass", "B")]
        )
        self.assertEqual(best["CS101"]["status"], "Fail")
        self.assertEqual(best["MATH101"]["status"], "Pass")

    def test_equal_rank_keeps_the_later_row(self):
        rows = [
            _pec("CS101", "Fail", "F", section="first"),
            _pec("CS101", "Fail", "FA", section="second"),
        ]
        self.assertEqual(
            _best_attempt_per_course(rows)["CS101"]["course_schedule"], "second"
        )
