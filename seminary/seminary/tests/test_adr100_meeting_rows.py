# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""051a/100d groundwork: regenerating a section's meetings keeps the rows that
still fall on a meeting day, so what points at them (attendance today, provider
meetings and captured activities later) keeps its target."""

from datetime import date

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_time

from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr081_attendance import _attend

MON, TUE, WED = date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4)
NEXT_MON = date(2026, 3, 9)


def _section_with_meetings(dates, from_time="09:00:00", to_time="10:00:00"):
    cs = frappe.get_doc(
        {
            "doctype": "Course Schedule",
            "name": fx.uid("CS"),
            "workflow_state": "Open for Enrollment",
            "c_datestart": MON,
            "c_dateend": NEXT_MON,
            "from_time": from_time,
            "to_time": to_time,
        }
    )
    cs.db_insert()
    for i, day in enumerate(dates, start=1):
        frappe.get_doc(
            {
                "doctype": "Course Schedule Meeting Dates",
                "name": frappe.generate_hash(length=10),
                "parent": cs.name,
                "parenttype": "Course Schedule",
                "parentfield": "cs_meetinfo",
                "idx": i,
                "cs_meetdate": day,
                "cs_fromtime": from_time,
                "cs_totime": to_time,
            }
        ).db_insert()
    return frappe.get_doc("Course Schedule", cs.name)


def _names(doc):
    return {r.cs_meetdate: r.name for r in doc.cs_meetinfo}


class TestMeetingRowsSurvive(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def test_same_days_keep_every_name(self):
        doc = _section_with_meetings([MON, WED, NEXT_MON])
        before = _names(doc)
        doc._merge_meeting_rows([MON, WED, NEXT_MON])
        self.assertEqual(_names(doc), before)

    def test_added_day_is_new_and_kept_days_keep_their_overrides(self):
        doc = _section_with_meetings([MON, NEXT_MON])
        doc.cs_meetinfo[0].cs_online = 1
        doc.cs_meetinfo[0].cs_web_meeting = "https://example.com/m"
        before = _names(doc)

        doc._merge_meeting_rows([MON, TUE, NEXT_MON])

        after = _names(doc)
        self.assertEqual(after[MON], before[MON])
        self.assertEqual(after[NEXT_MON], before[NEXT_MON])
        self.assertNotIn(TUE, before)
        self.assertIsNone(after[TUE])  # appended, not saved yet
        first = doc.cs_meetinfo[0]
        self.assertEqual(
            (first.cs_online, first.cs_web_meeting), (1, "https://example.com/m")
        )
        self.assertEqual([r.idx for r in doc.cs_meetinfo], [1, 2, 3])
        self.assertEqual([r.cs_meetdate for r in doc.cs_meetinfo], [MON, TUE, NEXT_MON])

    def test_dropped_day_without_attendance_is_removed(self):
        doc = _section_with_meetings([MON, WED, NEXT_MON])
        doc._merge_meeting_rows([MON, NEXT_MON])
        self.assertEqual(set(_names(doc)), {MON, NEXT_MON})

    def test_dropped_day_with_attendance_is_refused_and_nothing_changes(self):
        doc = _section_with_meetings([MON, WED, NEXT_MON])
        wed = _names(doc)[WED]
        student = fx.make_student()
        _attend(doc.name, student.name, WED, "Present", meeting=wed)

        self.assertRaises(
            frappe.ValidationError, doc._merge_meeting_rows, [MON, NEXT_MON]
        )
        self.assertIn(wed, _names(doc).values())

    def test_times_follow_the_section_unless_the_meeting_has_its_own(self):
        doc = _section_with_meetings([MON, WED])
        doc.cs_meetinfo[1].cs_fromtime = "14:00:00"
        doc.cs_meetinfo[1].cs_totime = "15:00:00"
        doc.cs_meetinfo[1].db_update()
        doc.from_time, doc.to_time = "18:00:00", "19:30:00"

        doc._merge_meeting_rows([MON, WED])

        mon, wed = doc.cs_meetinfo
        self.assertEqual(get_time(mon.cs_fromtime), get_time("18:00:00"))
        self.assertEqual(get_time(mon.cs_totime), get_time("19:30:00"))
        self.assertEqual(get_time(wed.cs_fromtime), get_time("14:00:00"))
