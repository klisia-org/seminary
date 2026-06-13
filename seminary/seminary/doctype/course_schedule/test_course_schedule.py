# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt

import unittest

import frappe

from seminary.seminary.utils import student_schedule_conflicts, times_overlap

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


class TestStudentScheduleConflicts(unittest.TestCase):
    """Student double-booking detection (ADR 050). The overlap predicate is the
    same as room double-booking (covered by TestTimesOverlap); these guard the
    helper's input handling. The DB join path is verified end-to-end via the
    Desk form and the registrar report."""

    def test_missing_args_return_empty(self):
        self.assertEqual(student_schedule_conflicts(None, "CS-0001"), [])
        self.assertEqual(student_schedule_conflicts("STU-0001", None), [])
        self.assertEqual(student_schedule_conflicts("", ""), [])

    def test_shares_predicate_with_room_detection(self):
        # The SQL overlap (mine.cs_fromtime < theirs.cs_totime AND
        # theirs.cs_fromtime < mine.cs_totime) is exactly times_overlap, so
        # back-to-back sections do not clash for a student either.
        self.assertTrue(times_overlap("13:00:00", "14:30:00", "14:00:00", "15:00:00"))
        self.assertFalse(times_overlap("13:00:00", "14:00:00", "14:00:00", "15:00:00"))


class TestEffectiveRoom(unittest.TestCase):
    """Per-meeting room fallback (ADR 051): a meeting uses its own room override,
    else the section room, and no room when it is online."""

    def setUp(self):
        self.cs = frappe.new_doc("Course Schedule")
        self.cs.room = "ROOM-A"

    def test_inherits_section_room(self):
        row = frappe._dict(cs_room=None, cs_online=0)
        self.assertEqual(self.cs._effective_room(row), "ROOM-A")

    def test_override_wins(self):
        row = frappe._dict(cs_room="ROOM-B", cs_online=0)
        self.assertEqual(self.cs._effective_room(row), "ROOM-B")

    def test_online_has_no_room(self):
        row = frappe._dict(cs_room="ROOM-C", cs_online=1)
        self.assertIsNone(self.cs._effective_room(row))


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
