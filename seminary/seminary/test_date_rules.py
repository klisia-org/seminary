# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import datetime
import unittest

from seminary.seminary import date_rules


class TestDateRules(unittest.TestCase):
    def test_days_offset_from_anchor(self):
        ctx = {"anchors": {"Project Start": datetime.date(2026, 1, 10)}}
        self.assertEqual(
            date_rules.resolve("Project Start", 30, "Days", ctx),
            datetime.date(2026, 2, 9),
        )

    def test_negative_days_offset(self):
        ctx = {"anchors": {"Expected Graduation": datetime.date(2026, 6, 1)}}
        self.assertEqual(
            date_rules.resolve("Expected Graduation", -30, "Days", ctx),
            datetime.date(2026, 5, 2),
        )

    def test_unresolvable_anchor_returns_none(self):
        self.assertIsNone(
            date_rules.resolve("Project Start", 5, "Days", {"anchors": {}})
        )

    def test_academic_terms_without_term_context_returns_none(self):
        self.assertIsNone(date_rules.resolve("Term Start", 2, "Academic Terms", {}))

    def test_snap_to_weekday_advances_to_next_occurrence(self):
        # 2026-01-10 is a Saturday; next Monday is 2026-01-12.
        self.assertEqual(
            date_rules.snap_to_weekday(datetime.date(2026, 1, 10), "Monday"),
            datetime.date(2026, 1, 12),
        )

    def test_snap_to_weekday_keeps_same_day(self):
        # 2026-01-12 is a Monday; asking for Monday leaves it unchanged.
        self.assertEqual(
            date_rules.snap_to_weekday(datetime.date(2026, 1, 12), "Monday"),
            datetime.date(2026, 1, 12),
        )

    def test_weekday_post_processing_in_resolve(self):
        ctx = {"anchors": {"Project Start": datetime.date(2026, 1, 10)}}
        # +0 days -> Sat 2026-01-10, snapped to Monday -> 2026-01-12.
        self.assertEqual(
            date_rules.resolve("Project Start", 0, "Days", ctx, weekday="Monday"),
            datetime.date(2026, 1, 12),
        )

    def test_holiday_subtract(self):
        holiday = datetime.date(2026, 12, 25)
        ctx = {"anchors": {"Project Start": holiday}, "holidays": {holiday}}
        self.assertEqual(
            date_rules.resolve(
                "Project Start", 0, "Days", ctx, holiday_adjust="Subtract one day"
            ),
            datetime.date(2026, 12, 24),
        )

    def test_clamp_to_max(self):
        ctx = {"anchors": {"Project Start": datetime.date(2026, 1, 1)}}
        self.assertEqual(
            date_rules.resolve(
                "Project Start", 365, "Days", ctx, clamp_to=datetime.date(2026, 6, 30)
            ),
            datetime.date(2026, 6, 30),
        )


if __name__ == "__main__":
    unittest.main()
