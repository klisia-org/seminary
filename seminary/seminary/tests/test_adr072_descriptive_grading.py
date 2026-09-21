# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""ADR 072: the Descriptive scale's calculation path.

`grscale_type` has three values and, until this ADR, two of them computed.
ADR 065 gave `Competency-based education` a branch and named the Points-only
guards as the enforcement points for the level-vs-percent split; `Descriptive`
kept falling off the end of both grading functions, writing nothing, while
`send_grades` copied the resulting blanks onto the transcript and awarded
credits against them.

What these tests pin is not "a number arrives" but **which units the number is
in**. A Descriptive interval's `threshold` is the grade-point value
(Distinction = 4.0), not a percentage. The Points arithmetic copied across
would build a 0-100 weighted sum and resolve it against 0-4 bands, which is not
a wrong grade for one student — it is an A for everybody.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import api

# A narrative scale as a school would actually author it: the threshold doubles
# as the GPA point value, exactly as gpa._points_from_code reads it.
LEVELS = [
    {"grade_code": "Distinction", "threshold": 4.0, "grade_pass": "Pass"},  # nosec B105
    {"grade_code": "Merit", "threshold": 3.0, "grade_pass": "Pass"},  # nosec B105
    {"grade_code": "Pass", "threshold": 2.0, "grade_pass": "Pass"},  # nosec B105
    {"grade_code": "Fail", "threshold": 0.0, "grade_pass": "Fail"},  # nosec B105
]
SCALE = "ZZT Narrative"


def cell(level, weight):
    return {"rawscore_card": level, "maximum_score": weight}


class TestDescriptiveArithmetic(IntegrationTestCase):
    """The formula, which has no frappe in it."""

    def test_a_weighted_mean_stays_in_the_scale_s_own_units(self):
        self.assertEqual(api.descriptive_fscore([cell(4, 50), cell(2, 50)]), 3.0)

    def test_the_points_arithmetic_would_have_put_everyone_in_the_top_band(self):
        """The regression this ADR exists for.

        A weighted *sum* of the same cells is 300 — every student, every time,
        above the 4.0 threshold and therefore a Distinction. The mean cannot
        leave the interval range no matter what the weights are.
        """
        rows = [cell(4, 50), cell(2, 50)]
        weighted_sum = sum(r["rawscore_card"] * r["maximum_score"] for r in rows)
        self.assertEqual(api.descriptive_fscore(rows), 3.0)
        self.assertGreater(weighted_sum, LEVELS[0]["threshold"])

        top = max(lv["threshold"] for lv in LEVELS)
        for weights in ((100, 0), (1, 99), (33, 67), (10, 10)):
            scored = [cell(4, weights[0]), cell(4, weights[1])]
            self.assertLessEqual(api.descriptive_fscore(scored), top)

    def test_weights_that_do_not_total_a_hundred_renormalise(self):
        """Dividing by the weights actually present, not by 100."""
        self.assertEqual(api.descriptive_fscore([cell(4, 10), cell(2, 10)]), 3.0)
        self.assertEqual(api.descriptive_fscore([cell(3, 7)]), 3.0)

    def test_an_ungraded_cell_leaves_the_denominator_too(self):
        """A mean has a denominator, unlike the Points sum that reads a missing
        score as 0. The query filters on graded_card; this is what that filter
        is worth."""
        graded_only = api.descriptive_fscore([cell(4, 50)])
        counted_as_zero = api.descriptive_fscore([cell(4, 50), cell(0, 50)])
        self.assertEqual(graded_only, 4.0)
        self.assertEqual(counted_as_zero, 2.0)
        self.assertNotEqual(graded_only, counted_as_zero)

    def test_nothing_to_average_is_not_a_zero(self):
        """Zero is a real level on this scale (Fail = 0.0), so "no cells" must
        not resolve to it — it must decline to produce a grade at all."""
        self.assertIsNone(api.descriptive_fscore([]))
        self.assertIsNone(api.descriptive_fscore([cell(4, 0)]))


class TestBlankGradeGuard(IntegrationTestCase):
    """Credits are awarded unless fgradepass is exactly "Fail"."""

    def test_a_computed_grade_passes(self):
        self.assertIsNone(api._assert_grade_computed("ZZT-1", "Merit", "Pass"))
        self.assertIsNone(api._assert_grade_computed("ZZT-1", "Fail", "Fail"))

    def test_a_blank_pass_fail_refuses_to_finalize(self):
        """The silence that hid this bug: no branch ran, nothing was written,
        and a blank fgradepass is not "Fail", so finalization awarded credit
        against an empty transcript row."""
        for fgrade, fgradepass in (
            ("Merit", None),
            ("Merit", ""),
            (None, "Pass"),
            (None, None),
        ):
            with self.assertRaises(frappe.ValidationError):
                api._assert_grade_computed("ZZT-1", fgrade, fgradepass)


class _BranchCase(IntegrationTestCase):
    """Drives the two grading functions over a fake Descriptive section.

    The branch is the thing under test, so the plumbing around it is faked
    rather than built: what matters is that a Descriptive scale reaches a
    calculation at all, which for the life of ADR 065 it did not.
    """

    def setUp(self):
        super().setUp()
        # get_grade/get_gradepass read this request-local cache; seeding it
        # keeps the scale's bands out of the database.
        frappe.local.grading_scale_intervals = {
            SCALE: [frappe._dict(lv) for lv in LEVELS]
        }
        self.written = {}

    def tearDown(self):
        frappe.local.grading_scale_intervals = {}
        super().tearDown()

    def _scale(self, **kw):
        return frappe._dict(
            {
                "name": SCALE,
                "grscale_type": "Descriptive",
                "maxnumgrade": 0,
                "fa_code": "FA",
                "intervals": [frappe._dict(lv) for lv in LEVELS],
            }
            | kw
        )

    def _roster(self, rows=(), failed_for_absence=0):
        roster = frappe._dict(
            {
                "name": "ZZT-ROSTER",
                "course_sc": "ZZT-CS",
                "student": "ZZT-STU",
                "failed_for_absence": failed_for_absence,
                "stdroster_grade": list(rows),
            }
        )
        roster.save = lambda *a, **k: None
        return roster

    def _run(self, fn, roster, cards=()):
        docs = {
            "Scheduled Course Roster": roster,
            "Course Schedule": frappe._dict({"gradesc_cs": SCALE, "maxnumgrade": 0}),
            "Grading Scale": self._scale(),
        }

        def set_value(doctype, name, values, *a, **k):
            self.written.setdefault(doctype, {}).setdefault(name, {}).update(
                values if isinstance(values, dict) else {values: a[0] if a else None}
            )

        with patch.object(
            frappe, "get_doc", lambda dt, *a, **k: docs[dt]
        ), patch.object(frappe, "get_all", lambda dt, **k: list(cards)), patch.object(
            frappe.db, "set_value", set_value
        ):
            return fn(roster.name)


class TestDescriptiveBranchReached(_BranchCase):
    def test_the_final_grade_is_computed_and_written(self):
        cards = [cell(4, 50), cell(2, 50)]
        self.assertEqual(self._run(api._fgrade_this_std, self._roster(), cards), "done")
        written = self.written["Scheduled Course Roster"]["ZZT-ROSTER"]
        self.assertEqual(written["fscore"], 3.0)
        self.assertEqual(written["fgrade"], "Merit")
        self.assertEqual(written["fgradepass"], "Pass")

    def test_a_roster_with_no_graded_cells_declines_rather_than_failing(self):
        """None, not Fail: nothing was assessed, so nothing is claimed. The
        blank-grade guard is what stops this reaching a transcript."""
        self.assertEqual(self._run(api._fgrade_this_std, self._roster(), []), "done")
        written = self.written["Scheduled Course Roster"]["ZZT-ROSTER"]
        self.assertIsNone(written["fscore"])
        self.assertIsNone(written["fgrade"])
        self.assertIsNone(written["fgradepass"])
        with self.assertRaises(frappe.ValidationError):
            api._assert_grade_computed(
                "ZZT-ROSTER", written["fgrade"], written["fgradepass"]
            )

    def test_fail_for_absence_still_overrides_a_passing_mean(self):
        roster = self._roster(failed_for_absence=1)
        self._run(api._fgrade_this_std, roster, [cell(4, 100)])
        written = self.written["Scheduled Course Roster"]["ZZT-ROSTER"]
        self.assertEqual(written["fgrade"], "FA")
        self.assertEqual(written["fgradepass"], "Fail")
        # The numeric is preserved for transcript truth, as the other branches do.
        self.assertEqual(written["fscore"], 4.0)

    def test_each_cell_gets_the_band_its_level_lands_in(self):
        rows = [
            frappe._dict(
                {
                    "name": "ZZT-C1",
                    "rawscore_card": 4.0,
                    "graded_card": 1,
                    "extracredit_card": 0,
                    "grade": None,
                    "score": None,
                }
            ),
            frappe._dict(
                {
                    "name": "ZZT-C2",
                    "rawscore_card": 2.0,
                    "graded_card": 1,
                    "extracredit_card": 0,
                    "grade": None,
                    "score": None,
                }
            ),
        ]
        self.assertEqual(self._run(api._grade_thisstudent, self._roster(rows)), "done")
        self.assertEqual(rows[0].grade, "Distinction")
        self.assertEqual(rows[1].grade, "Pass")
        # score holds the level, not a weighted contribution: the weighting in
        # _fgrade_this_std needs a denominator only known for the whole row.
        self.assertEqual(rows[0].score, 4.0)
        self.assertEqual(
            self.written["Course Assess Results Detail"]["ZZT-C1"]["grade"],
            "Distinction",
        )

    def test_an_ungraded_or_extra_credit_cell_is_left_alone(self):
        rows = [
            frappe._dict(
                {
                    "name": "ZZT-U",
                    "rawscore_card": 0.0,
                    "graded_card": 0,
                    "extracredit_card": 0,
                    "grade": None,
                    "score": None,
                }
            ),
            frappe._dict(
                {
                    "name": "ZZT-X",
                    "rawscore_card": 4.0,
                    "graded_card": 1,
                    "extracredit_card": 1,
                    "grade": None,
                    "score": None,
                }
            ),
        ]
        self._run(api._grade_thisstudent, self._roster(rows))
        self.assertIsNone(rows[0].grade)
        self.assertIsNone(rows[1].grade)
        self.assertNotIn("Course Assess Results Detail", self.written)
