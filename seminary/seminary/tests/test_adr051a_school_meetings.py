# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/051a: school meeting accounts. An account is a room."""

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import school_meetings
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr100_meeting_rows import (
    MON,
    WED,
    _section_with_meetings,
)

THIS = "seminary.seminary.tests.test_adr051a_school_meetings"
CALLS = []


class FakeProvider:
    fail = False

    def create(self, account, meeting):
        CALLS.append(("create", account["name"], meeting["start"]))
        if FakeProvider.fail:
            raise frappe.ValidationError("The provider is down.")
        n = len(CALLS)
        return {
            "join_url": f"https://meet.example/{n}",
            "meeting_id": f"M{n}",
            "host_key": "123456",
            "alternative_hosts": [],
        }

    def update(self, account, meeting_id, meeting):
        CALLS.append(("update", meeting_id, meeting["start"]))
        if FakeProvider.fail:
            raise frappe.ValidationError("The provider is down.")
        return {}

    def delete(self, account, meeting_id):
        CALLS.append(("delete", meeting_id))


@contextmanager
def _provider():
    with patch.object(
        school_meetings, "providers", return_value={"Fake": f"{THIS}.FakeProvider"}
    ):
        yield


def _account(max_concurrent=1):
    with _provider():
        return (
            frappe.get_doc(
                {
                    "doctype": "Web Meeting Account",
                    "label": fx.uid("Licence"),
                    "provider": "Fake",
                    "host_id": "host@example.com",
                    "max_concurrent": max_concurrent,
                }
            )
            .insert(ignore_permissions=True)
            .name
        )


def _save(doc, **values):
    """A section save as the form does it, with only the meeting rules in play."""
    before = frappe.get_doc("Course Schedule", doc.name)
    doc.update(values)
    with _provider():
        school_meetings.validate(doc)
        for row in doc.cs_meetinfo:
            row.parent, row.parenttype, row.parentfield = (
                doc.name,
                "Course Schedule",
                "cs_meetinfo",
            )
            if frappe.db.exists(school_meetings.ROW, row.name):
                row.db_update()
            else:
                row.db_insert()
        doc.db_update()
        doc._doc_before_save = before
        school_meetings.on_update(doc)
    return frappe.get_doc("Course Schedule", doc.name)


def _school_section(dates=(MON,), from_time="09:00:00", to_time="10:00:00"):
    doc = _section_with_meetings(list(dates), from_time, to_time)
    doc.title = fx.uid("Exegesis")
    doc.db_update()
    return _save(doc, school_meeting=1, modality="Virtual")


class MeetingCase(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        CALLS.clear()
        FakeProvider.fail = False
        frappe.db.set_value(
            "Web Meeting Account", {"name": ["is", "set"]}, "enabled", 0
        )


class TestAccountIsARoom(MeetingCase):
    def test_a_pool_of_one_refuses_an_overlapping_section_and_names_it(self):
        account = _account()
        first = _school_section()
        row = first.cs_meetinfo[0]
        self.assertEqual(
            (row.cs_meeting_account, row.cs_meeting_status, row.cs_meeting_id),
            (account, "Created", "M1"),
        )
        self.assertTrue(row.cs_web_meeting.startswith("https://meet.example/"))
        with self.assertRaises(frappe.ValidationError) as caught:
            _school_section(from_time="09:30:00", to_time="10:30:00")
        self.assertIn(first.title, str(caught.exception))

    def test_touching_meetings_share_an_account(self):
        account = _account()
        _school_section()
        second = _school_section(from_time="10:00:00", to_time="11:00:00")
        self.assertEqual(second.cs_meetinfo[0].cs_meeting_account, account)

    def test_a_second_account_takes_the_overlap(self):
        a, b = sorted([_account(), _account()])
        _school_section()
        second = _school_section(from_time="09:30:00", to_time="10:30:00")
        self.assertEqual(second.cs_meetinfo[0].cs_meeting_account, b)

    def test_max_concurrent_two_runs_two_at_once(self):
        account = _account(max_concurrent=2)
        _school_section()
        second = _school_section(from_time="09:30:00", to_time="10:30:00")
        self.assertEqual(second.cs_meetinfo[0].cs_meeting_account, account)


class TestProviderCalls(MeetingCase):
    def test_a_time_change_updates_the_same_meeting(self):
        _account()
        doc = _school_section()
        doc.cs_meetinfo[0].cs_fromtime = "09:15:00"
        doc = _save(doc)
        self.assertEqual(CALLS[-1][:2], ("update", "M1"))
        self.assertEqual(doc.cs_meetinfo[0].cs_meeting_id, "M1")

    def test_regenerating_the_schedule_keeps_the_meeting(self):
        _account()
        doc = _school_section(dates=(MON, WED))
        ids = {r.cs_meetdate: r.cs_meeting_id for r in doc.cs_meetinfo}
        doc._merge_meeting_rows([MON, WED])
        doc = _save(doc)
        self.assertEqual({r.cs_meetdate: r.cs_meeting_id for r in doc.cs_meetinfo}, ids)
        self.assertEqual([c[0] for c in CALLS], ["create", "create"])

    def test_a_failed_change_keeps_the_previous_link(self):
        _account()
        doc = _school_section()
        link = doc.cs_meetinfo[0].cs_web_meeting
        FakeProvider.fail = True
        doc.cs_meetinfo[0].cs_fromtime = "09:15:00"
        doc = _save(doc)
        row = doc.cs_meetinfo[0]
        self.assertEqual(
            (row.cs_meeting_status, row.cs_web_meeting, row.cs_meeting_id),
            ("Failed", link, "M1"),
        )
        self.assertIn("down", row.cs_meeting_error)

    def test_a_failed_create_leaves_no_link_and_can_be_retried(self):
        _account()
        FakeProvider.fail = True
        doc = _school_section()
        self.assertEqual(doc.cs_meetinfo[0].cs_meeting_status, "Failed")
        self.assertFalse(doc.cs_meetinfo[0].cs_web_meeting)
        FakeProvider.fail = False
        with _provider():
            school_meetings.retry(doc.name)
        row = frappe.get_doc("Course Schedule", doc.name).cs_meetinfo[0]
        self.assertEqual(row.cs_meeting_status, "Created")

    def test_turning_it_off_or_removing_the_row_deletes_the_meeting(self):
        _account()
        doc = _school_section(dates=(MON, WED))
        doc.remove(doc.cs_meetinfo[1])
        doc = _save(doc)
        self.assertIn(("delete", "M2"), CALLS)
        doc = _save(doc, school_meeting=0)
        self.assertIn(("delete", "M1"), CALLS)
        row = doc.cs_meetinfo[0]
        self.assertEqual((row.cs_meeting_account, row.cs_web_meeting), (None, None))

    def test_no_enabled_account_refuses_the_save(self):
        doc = _section_with_meetings([MON])
        self.assertRaises(
            frappe.ValidationError, _save, doc, school_meeting=1, modality="Virtual"
        )


class TestHostKeyIsStaffOnly(MeetingCase):
    def test_the_meeting_rows_are_beyond_a_students_read(self):
        meta = frappe.get_meta("Course Schedule")
        self.assertGreaterEqual(meta.get_field("cs_meetinfo").permlevel, 1)
        student_levels = {
            p.permlevel for p in meta.permissions if p.role == "Student" and p.read
        }
        self.assertEqual(student_levels, {0})
