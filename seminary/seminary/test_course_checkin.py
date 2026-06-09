# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt

from datetime import timedelta

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import add_to_date, getdate, now_datetime

from seminary.seminary import course_checkin as svc


class UnitTestCourseCheckin(UnitTestCase):
    """Meeting check-in window / code / tardy helpers (pure logic, no DB)."""

    def _settings(self, before, after, tardy=0, require_code=0):
        return frappe._dict(
            course_checkin_opens_before_mins=before,
            course_checkin_closes_after_mins=after,
            course_checkin_tardy_after_mins=tardy,
            require_course_checkin_code=require_code,
        )

    def _meeting(self, minutes_from_now_start, duration_mins=60):
        now = now_datetime()
        start = add_to_date(now, minutes=minutes_from_now_start)
        end = add_to_date(start, minutes=duration_mins)
        return start, end

    # --- window ----------------------------------------------------------
    def test_window_exact_when_both_zero(self):
        # With zero grace the window is exactly the meeting span. A meeting far
        # in the past is closed (enforce mode no longer means "always open").
        start, end = self._meeting(-600)
        settings = self._settings(0, 0)
        self.assertEqual(svc._window_bounds(start, end, settings), (start, end))
        self.assertFalse(svc._is_open_now(start, end, settings))

    def test_open_inside_window(self):
        start, end = self._meeting(-5)
        self.assertTrue(svc._is_open_now(start, end, self._settings(15, 30)))

    def test_closed_before_window_opens(self):
        start, end = self._meeting(120)
        self.assertFalse(svc._is_open_now(start, end, self._settings(15, 30)))

    def test_closed_after_window_shuts(self):
        start, end = self._meeting(-180)
        self.assertFalse(svc._is_open_now(start, end, self._settings(15, 30)))

    # --- code ------------------------------------------------------------
    def test_code_validation(self):
        settings = self._settings(0, 0, require_code=1)
        meeting = frappe._dict(checkin_code="AB7KP")
        svc._validate_code(meeting, settings, "ab7kp")  # case-insensitive
        with self.assertRaises(frappe.ValidationError):
            svc._validate_code(meeting, settings, "WRONG")
        with self.assertRaises(frappe.ValidationError):
            svc._validate_code(meeting, settings, None)

    def test_code_skipped_when_not_required(self):
        settings = self._settings(0, 0, require_code=0)
        svc._validate_code(frappe._dict(checkin_code="AB7KP"), settings, None)

    # --- tardy -----------------------------------------------------------
    def test_status_present_within_grace(self):
        start = add_to_date(now_datetime(), minutes=-5)  # started 5 min ago
        self.assertEqual(
            svc._status_for(start, self._settings(15, 30, tardy=10)), "Present"
        )

    def test_status_tardy_past_grace(self):
        start = add_to_date(now_datetime(), minutes=-20)  # 20 min in, grace 10
        self.assertEqual(
            svc._status_for(start, self._settings(15, 30, tardy=10)), "Tardy"
        )

    def test_status_never_tardy_when_grace_zero(self):
        start = add_to_date(now_datetime(), minutes=-120)
        self.assertEqual(
            svc._status_for(start, self._settings(15, 30, tardy=0)), "Present"
        )

    # --- date/time combine ----------------------------------------------
    def test_combine_date_and_timedelta(self):
        # Time fields come back as timedelta; combine with the meeting date.
        dt = svc._combine(getdate("2026-06-08"), timedelta(hours=9, minutes=30))
        self.assertEqual(
            (dt.year, dt.month, dt.day, dt.hour, dt.minute), (2026, 6, 8, 9, 30)
        )
