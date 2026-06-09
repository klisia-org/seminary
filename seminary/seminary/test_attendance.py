# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt

import frappe
from frappe.tests import UnitTestCase

from seminary.seminary import attendance as svc


class UnitTestAttendance(UnitTestCase):
    """Pure standing logic: effective-absence math, limit resolution, levels."""

    def _settings(self, per=3, buffer=1):
        return frappe._dict(tardies_per_absence=per, absence_warning_buffer=buffer)

    # --- effective absences (tardy conversion) ---------------------------
    def test_effective_converts_tardies(self):
        # 7 tardies, 3 per absence → +2; plus 2 raw absences = 4.
        self.assertEqual(svc._effective(2, 7, self._settings(per=3)), 4)

    def test_effective_no_conversion_when_disabled(self):
        self.assertEqual(svc._effective(2, 7, self._settings(per=0)), 2)

    # --- limit resolution (non-DB branches) ------------------------------
    def test_limit_custom(self):
        meta = {
            "policy": svc.POLICY_CUSTOM,
            "custom": 4,
            "modality": "Presential",
            "total": 10,
        }
        self.assertEqual(svc._absence_limit(meta, "Any Program"), 4)

    def test_limit_disabled(self):
        meta = {
            "policy": svc.POLICY_DISABLED,
            "custom": 4,
            "modality": "Presential",
            "total": 10,
        }
        self.assertEqual(svc._absence_limit(meta, "Any Program"), 0)

    def test_limit_auto_virtual_is_zero(self):
        meta = {
            "policy": svc.POLICY_AUTO,
            "custom": None,
            "modality": "Virtual",
            "total": 10,
        }
        self.assertEqual(svc._absence_limit(meta, "Any Program"), 0)

    def test_limit_auto_no_meetings_is_zero(self):
        meta = {
            "policy": svc.POLICY_AUTO,
            "custom": None,
            "modality": "Presential",
            "total": 0,
        }
        self.assertEqual(svc._absence_limit(meta, "Any Program"), 0)

    # --- alert level -----------------------------------------------------
    def test_level_no_limit(self):
        self.assertEqual(svc._level(5, 0, 1), svc.ALERT_NONE)

    def test_level_over(self):
        self.assertEqual(svc._level(5, 4, 1), svc.ALERT_OVER)

    def test_level_danger_within_buffer(self):
        # limit 4, buffer 1 → danger band is 3..4; 3 effective → danger.
        self.assertEqual(svc._level(3, 4, 1), svc.ALERT_DANGER)

    def test_level_ok_below_band(self):
        self.assertEqual(svc._level(2, 4, 1), svc.ALERT_NONE)

    def test_level_zero_effective_never_flags(self):
        # Even when limit - buffer <= 0, a student with no absences is OK.
        self.assertEqual(svc._level(0, 1, 1), svc.ALERT_NONE)
