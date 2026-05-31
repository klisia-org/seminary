# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import add_to_date, now_datetime

from seminary.seminary import chapel as chapel_service


class UnitTestChapel(UnitTestCase):
    """Check-in window / code helpers (pure logic, no DB writes — UnitTestCase
    skips test-record dependency loading)."""

    def _chapel(self, minutes_from_now_start, duration_mins=60):
        now = now_datetime()
        start = add_to_date(now, minutes=minutes_from_now_start)
        return frappe._dict(
            starts_on=start,
            ends_on=add_to_date(start, minutes=duration_mins),
        )

    def _settings(self, before, after, require_code=0):
        return frappe._dict(
            chapel_checkin_opens_before_mins=before,
            chapel_checkin_closes_after_mins=after,
            require_chapel_checkin_code=require_code,
        )

    def test_window_disabled_when_both_zero(self):
        # A chapel far in the past is still "open" when the window is disabled.
        chapel = self._chapel(minutes_from_now_start=-600)
        settings = self._settings(0, 0)
        self.assertIsNone(chapel_service._checkin_bounds(chapel, settings))
        self.assertTrue(chapel_service._is_open_now(chapel, settings))

    def test_open_inside_window(self):
        # Started 5 min ago, 60 min service, 15 before / 30 after → open now.
        chapel = self._chapel(minutes_from_now_start=-5)
        settings = self._settings(15, 30)
        self.assertTrue(chapel_service._is_open_now(chapel, settings))

    def test_closed_before_window_opens(self):
        # Starts in 2 hours, opens only 15 min before → not open yet.
        chapel = self._chapel(minutes_from_now_start=120)
        settings = self._settings(15, 30)
        self.assertFalse(chapel_service._is_open_now(chapel, settings))

    def test_closed_after_window_shuts(self):
        # Ended well over an hour ago, closes 30 min after end → shut.
        chapel = self._chapel(minutes_from_now_start=-180)
        settings = self._settings(15, 30)
        self.assertFalse(chapel_service._is_open_now(chapel, settings))

    def test_code_validation(self):
        settings = self._settings(0, 0, require_code=1)
        chapel = frappe._dict(checkin_code="AB7KP")
        # Correct code (case-insensitive) passes; wrong/empty throws.
        chapel_service._validate_code(chapel, settings, "ab7kp")
        with self.assertRaises(frappe.ValidationError):
            chapel_service._validate_code(chapel, settings, "WRONG")
        with self.assertRaises(frappe.ValidationError):
            chapel_service._validate_code(chapel, settings, None)

    def test_code_skipped_when_not_required(self):
        settings = self._settings(0, 0, require_code=0)
        chapel = frappe._dict(checkin_code="AB7KP")
        # No exception even with a wrong code when the feature is off.
        chapel_service._validate_code(chapel, settings, None)
