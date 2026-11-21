# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/100d: oral activities captured from virtual meetings."""

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_to_date, now_datetime, today

from seminary.seminary import oral, oral_activities, oral_meetings
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr082_deadlines import _row, _scale, _section

THIS = "seminary.seminary.tests.test_adr100d_meeting_capture"
CALLS = []


class FakeBot:
    needs_managed = False
    rooms = False

    def arm(self, capture):
        CALLS.append(("arm", capture["name"], capture["start"], capture["meeting_url"]))
        return f"BOT-{len(CALLS)}"

    def disarm(self, ref, capture=None):
        CALLS.append(("disarm", ref))


class FakeAccount(FakeBot):
    needs_managed = True


def fake_transcribe(recording, step, payload):
    CALLS.append(("transcribe", len(payload["tracks"])))


@contextmanager
def _methods():
    with (
        patch.object(
            oral_meetings,
            "capture_methods",
            return_value={"bot": f"{THIS}.FakeBot", "account": f"{THIS}.FakeAccount"},
        ),
        patch.object(
            oral,
            "provided_steps",
            return_value={"transcribe": f"{THIS}.fake_transcribe"},
        ),
        patch.object(oral, "allowed_steps", return_value=list(oral.STEPS)),
    ):
        yield


def _student(name):
    student = fx.make_student()
    frappe.db.set_value("Student", student.name, "student_name", name)
    return student


def _on_roster(cs, student, name):
    frappe.get_doc(
        {
            "doctype": "Scheduled Course Roster",
            "name": f"{cs}-{student.name}",
            "course_sc": cs,
            "student": student.name,
            "stuname_roster": name,
            "active": 1,
            "audit_bool": 0,
        }
    ).db_insert()


class CaptureCase(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        CALLS.clear()
        self.cs = _section(_scale(), modality="Virtual")
        frappe.db.set_value("Course Schedule", self.cs, "title", fx.uid("Homiletics"))
        activity = frappe.get_doc(
            {
                "doctype": "Oral Activity",
                "title": fx.uid("Sermon"),
                "course": fx.uid("C"),
                "mode": "Individual",
                "capture": "Virtual meeting",
                "oral_steps": '["transcribe", "diarize"]',
            }
        )
        activity.flags.ignore_links = True
        activity.insert(ignore_permissions=True)
        self.activity = activity.name
        self.scac = _row(
            self.cs, add_days(today(), 14), kind="Oral", oral=self.activity
        )
        self.meeting = frappe.generate_hash(length=10)
        frappe.get_doc(
            {
                "doctype": "Course Schedule Meeting Dates",
                "name": self.meeting,
                "parent": self.cs,
                "parenttype": "Course Schedule",
                "parentfield": "cs_meetinfo",
                "idx": 1,
                "cs_meetdate": add_days(today(), 7),
                "cs_fromtime": "19:00:00",
                "cs_totime": "20:30:00",
                "cs_online": 1,
                "cs_web_meeting": "https://meet.example/abc",
            }
        ).db_insert()
        self.ana = _student("Ana Lúcia Prado")
        self.ben = _student("Benjamin Okafor")
        _on_roster(self.cs, self.ana, "Ana Lúcia Prado")
        _on_roster(self.cs, self.ben, "Benjamin Okafor")

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def schedule(self, method="bot"):
        with _methods():
            return oral_meetings.schedule_capture(
                self.cs, self.activity, self.meeting, method
            )

    def result(self):
        ben_email = frappe.db.get_value("User", self.ben.user, "email")
        start = add_to_date(now_datetime(), hours=-2)
        return {
            "participants": [
                {"key": "1", "name": "ana lucia prado", "email": None},
                {"key": "2", "name": "Ben", "email": ben_email},
                {"key": "3", "name": "Prof. Reyes", "email": "prof@example.org"},
            ],
            "rooms": [
                {
                    "audio": b"mixed",
                    "mime_type": "audio/mpeg",
                    "started_at": start,
                    "ended_at": add_to_date(start, minutes=80),
                    "tracks": [
                        {"key": "1", "label": "ana lucia prado", "audio": b"a"},
                        {"key": "2", "label": "Ben", "audio": b"b", "offset_s": 4},
                        {"key": "3", "label": "Prof. Reyes", "audio": b"c"},
                    ],
                }
            ],
        }

    def recorded(self, name):
        with _methods():
            oral_meetings.meeting_recorded(name, self.result())
        return frappe.get_doc(oral_meetings.OAM, name)


class TestOnlyNamedMeetings(CaptureCase):
    def test_scheduling_arms_the_method_and_tells_everyone(self):
        name = self.schedule()
        doc = frappe.get_doc(oral_meetings.OAM, name)
        self.assertEqual((doc.status, doc.capture_ref), ("Armed", "BOT-1"))
        self.assertEqual(CALLS[0][3], "https://meet.example/abc")
        self.assertIn(self.meeting, oral_meetings.captured_rows(self.cs))
        frappe.set_user(self.ana.user)
        try:
            ctx = oral_activities.resolve(self.scac, self.ana.user)
        finally:
            frappe.set_user("Administrator")
        self.assertFalse(ctx["may_record"])
        self.assertFalse(ctx["allow_upload"])

    def test_a_meeting_no_activity_captures_is_refused(self):
        self.assertRaises(
            frappe.PermissionError, oral.meeting_recorded, "nope", self.result()
        )
        name = self.schedule()
        with _methods():
            oral_meetings.cancel_capture(name)
        self.assertIn(("disarm", "BOT-1"), CALLS)
        self.assertRaises(
            frappe.PermissionError, oral.meeting_recorded, name, self.result()
        )

    def test_an_account_method_needs_a_school_meeting(self):
        self.assertRaises(frappe.ValidationError, self.schedule, "account")

    def test_a_captured_meeting_cannot_be_removed_from_the_schedule(self):
        from seminary.seminary.doctype.course_schedule.course_schedule import (
            _meeting_row_in_use,
        )

        self.schedule()
        row = frappe.get_doc("Course Schedule Meeting Dates", self.meeting)
        self.assertTrue(_meeting_row_in_use(row))


class TestMatchingAndConfirming(CaptureCase):
    def test_emails_link_names_suggest_strangers_stay_out(self):
        doc = self.recorded(self.schedule())
        self.assertEqual(doc.status, "Captured")
        by_name = {p.display_name: p for p in doc.participants}
        self.assertEqual(
            (by_name["Ben"].match, by_name["Ben"].student), ("Email", self.ben.name)
        )
        ana = by_name["ana lucia prado"]
        self.assertEqual(
            (ana.match, ana.suggested_student, ana.student),
            ("Name", self.ana.name, None),
        )
        self.assertFalse(by_name["Prof. Reyes"].match or by_name["Prof. Reyes"].student)
        rec = frappe.get_doc("Oral Recording", {"activity_meeting": doc.name})
        self.assertEqual(rec.source, "Meeting")
        self.assertEqual(
            [s.label for s in rec.speakers], ["ana lucia prado", "Ben", "Prof. Reyes"]
        )
        self.assertEqual(rec.speakers[1].audio_offset_s, 4)
        # One track per person: no diarize; transcribe got the three tracks.
        self.assertNotIn("diarize", rec.steps)
        self.assertIn(("transcribe", 3), CALLS)
        self.assertFalse(rec.participants)
        # Display names are scrubbed before any model reads the transcript.
        self.assertIn("Reyes", oral._names_of(rec))

    def test_confirming_creates_the_submissions_and_suggests_attendance(self):
        doc = self.recorded(self.schedule())
        rows = {p.display_name: p.name for p in doc.participants}
        links = {
            rows["ana lucia prado"]: self.ana.name,
            rows["Ben"]: self.ben.name,
            rows["Prof. Reyes"]: "",
        }
        out = oral_meetings.confirm_capture(doc.name, frappe.as_json(links))
        self.assertEqual(len(out["submissions"]), 2)
        rec = frappe.get_doc("Oral Recording", {"activity_meeting": doc.name})
        self.assertEqual(
            {p.student for p in rec.participants}, {self.ana.name, self.ben.name}
        )
        self.assertEqual(
            {s.label: s.student for s in rec.speakers}["Ben"], self.ben.name
        )
        sub = frappe.get_doc(
            "Oral Activity Submission",
            {"student": self.ana.name, "course_assess": self.scac},
        )
        self.assertEqual((sub.recording, sub.activity_meeting), (rec.name, doc.name))
        self.assertEqual(
            set(oral_meetings.attendance_suggestions(self.cs, self.meeting)),
            {self.ana.name, self.ben.name},
        )
        self.assertRaises(
            frappe.ValidationError,
            oral_meetings.confirm_capture,
            doc.name,
            frappe.as_json(links),
        )

    def test_one_student_cannot_be_two_people(self):
        doc = self.recorded(self.schedule())
        rows = [p.name for p in doc.participants]
        self.assertRaises(
            frappe.ValidationError,
            oral_meetings.confirm_capture,
            doc.name,
            frappe.as_json({rows[0]: self.ana.name, rows[1]: self.ana.name}),
        )


class TestRearming(CaptureCase):
    def test_a_moved_meeting_is_armed_again(self):
        name = self.schedule()
        cs = frappe.get_doc("Course Schedule", self.cs)
        cs._doc_before_save = frappe.get_doc("Course Schedule", self.cs)
        cs.cs_meetinfo[0].cs_fromtime = "18:30:00"
        cs.cs_meetinfo[0].db_update()
        with _methods():
            oral_meetings.on_section_update(cs)
        self.assertIn(("disarm", "BOT-1"), CALLS)
        doc = frappe.get_doc(oral_meetings.OAM, name)
        self.assertEqual((doc.status, doc.capture_ref), ("Armed", "BOT-3"))
        self.assertEqual(str(doc.from_time), "18:30:00")

    def test_a_meeting_without_a_link_waits_for_it(self):
        frappe.db.set_value(
            "Course Schedule Meeting Dates", self.meeting, "cs_web_meeting", None
        )
        name = self.schedule()
        doc = frappe.get_doc(oral_meetings.OAM, name)
        self.assertEqual(doc.status, "Scheduled")
        frappe.db.set_value(
            "Course Schedule Meeting Dates",
            self.meeting,
            "cs_web_meeting",
            "https://m/x",
        )
        with _methods():
            oral_meetings.on_meeting_link(self.meeting)
        self.assertEqual(
            frappe.db.get_value(oral_meetings.OAM, name, "status"), "Armed"
        )
