# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt

import unittest

from seminary.seminary.utils import times_overlap

# The legacy conflict tests here referenced fields removed long ago
# (schedule_date, a single `instructor`/`room` field). Room double-booking is
# now detected over the cs_meetinfo meeting-date child table using the shared
# times_overlap predicate (ADR 038); that predicate is unit-tested below.


class TestTimesOverlap(unittest.TestCase):
    def test_clear_overlap(self):
        self.assertTrue(times_overlap("09:00:00", "10:30:00", "10:00:00", "11:00:00"))

    def test_contained(self):
        self.assertTrue(times_overlap("09:00:00", "12:00:00", "10:00:00", "11:00:00"))

    def test_back_to_back_does_not_overlap(self):
        # Touching endpoints (one class ends as the next begins) is not a clash.
        self.assertFalse(times_overlap("09:00:00", "10:00:00", "10:00:00", "11:00:00"))

    def test_disjoint(self):
        self.assertFalse(times_overlap("09:00:00", "10:00:00", "11:00:00", "12:00:00"))

    def test_missing_bound_is_not_overlap(self):
        self.assertFalse(times_overlap(None, "10:00:00", "09:00:00", "11:00:00"))


class TestSeatSemantics(unittest.TestCase):
    """Documents the seat-holder model (ADR 038). seats_used counts Submitted +
    Awaiting Payment; Waitlisted/Unseated never hold a seat."""

    def test_seat_holder_states(self):
        from seminary.seminary.waitlist import SEAT_HOLDER_STATES, DEMAND_STATES

        self.assertEqual(set(SEAT_HOLDER_STATES), {"Submitted", "Awaiting Payment"})
        self.assertNotIn("Waitlisted", SEAT_HOLDER_STATES)
        self.assertNotIn("Unseated", SEAT_HOLDER_STATES)
        self.assertIn("Waitlisted", DEMAND_STATES)
        self.assertNotIn("Unseated", DEMAND_STATES)
