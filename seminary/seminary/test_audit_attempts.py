# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Which attempt speaks for a course in the program audit.

A student who fails a course and later passes it has two Program Enrollment
Course rows. The audit used to keep whichever row came last, and row order is
not chronological, so a passed course could show as failed and block
graduation. These assert the decision, not the schema."""

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


class TestBestAttemptPerCourse(UnitTestCase):
    def test_pass_wins_when_the_fail_row_comes_last(self):
        rows = [_pec("CS101", "Pass", "C-"), _pec("CS101", "Fail", "F")]
        best = _best_attempt_per_course(rows)
        self.assertEqual(best["CS101"]["status"], "Pass")
        self.assertEqual(best["CS101"]["grade_code"], "C-")

    def test_pass_wins_when_the_fail_row_comes_first(self):
        rows = [_pec("CS101", "Fail", "F"), _pec("CS101", "Pass", "C-")]
        self.assertEqual(_best_attempt_per_course(rows)["CS101"]["status"], "Pass")

    def test_open_retake_outranks_the_earlier_fail(self):
        rows = [_pec("CS101", "Enrolled"), _pec("CS101", "Fail", "F")]
        self.assertEqual(_best_attempt_per_course(rows)["CS101"]["status"], "Enrolled")

    def test_pass_outranks_a_later_withdrawal(self):
        rows = [_pec("EL1", "Pass", "A"), _pec("EL1", "Withdrawn", "W")]
        self.assertEqual(_best_attempt_per_course(rows)["EL1"]["status"], "Pass")

    def test_single_attempts_are_untouched(self):
        rows = [_pec("CS101", "Fail", "F"), _pec("MATH101", "Pass", "B")]
        best = _best_attempt_per_course(rows)
        self.assertEqual(best["CS101"]["status"], "Fail")
        self.assertEqual(best["MATH101"]["status"], "Pass")
        self.assertNotIn("_rank", best["CS101"])

    def test_same_rank_keeps_the_later_row(self):
        rows = [
            _pec("CS101", "Fail", "F", section="first"),
            _pec("CS101", "Fail", "FA", section="second"),
        ]
        self.assertEqual(
            _best_attempt_per_course(rows)["CS101"]["course_schedule"], "second"
        )
