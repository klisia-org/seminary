# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/100b: oral activities, recorded conversations and talk time."""

import io
import json
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from seminary.seminary import oral, oral_activities
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr082_deadlines import (
    _card,
    _roster,
    _row,
    _scale,
    _section,
)


def _activity(mode="Conversation", group_size=0, allow_upload=0):
    doc = frappe.get_doc(
        {
            "doctype": "Oral Activity",
            "title": fx.uid("Seminar"),
            "course": fx.uid("C"),
            "mode": mode,
            "group_size": group_size,
            "allow_upload": allow_upload,
            "max_minutes": 10,
            "oral_steps": "[]",
        }
    )
    doc.flags.ignore_links = True
    doc.insert(ignore_permissions=True)
    return doc


class OralActivityCase(IntegrationTestCase):
    mode = "Conversation"
    group_size = 0
    allow_upload = 0
    size = 4

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.cs = _section(_scale())
        self.activity = _activity(self.mode, self.group_size, self.allow_upload)
        self.row = _row(
            self.cs,
            add_to_date(now_datetime(), days=7),
            kind="Oral",
            oral=self.activity.name,
        )
        self.students = [fx.make_student() for _ in range(self.size)]
        self.cards = {}
        for s in self.students:
            roster = _roster(self.cs, s.name)
            self.cards[s.name] = _card(roster, self.row, s.name)

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def record(self, student, present=(), chunks=(b"aa", b"bb")):
        frappe.set_user(student.user)
        name = oral.start_recording(
            "Scheduled Course Assess Criteria",
            self.row,
            "audio/webm",
            participants=json.dumps([s.name for s in present]),
        )["recording"]
        doc = frappe.get_doc("Oral Recording", name)
        for i, chunk in enumerate(chunks):
            oral._store_chunk(doc, i, chunk)
        oral.finish_recording(name, len(chunks))
        frappe.set_user("Administrator")
        return name

    def submit(self, student, recording):
        frappe.set_user(student.user)
        try:
            return oral_activities.submit(recording)["submissions"]
        finally:
            frappe.set_user("Administrator")

    def state(self, student):
        frappe.set_user(student.user)
        try:
            return oral_activities.my_state(self.cs, self.activity.name)
        finally:
            frappe.set_user("Administrator")


class TestSharedRecording(OralActivityCase):
    def test_one_recording_is_shared_by_every_member_present(self):
        a, b, c, _d = self.students
        rec = self.record(a, present=[b, c])
        subs = self.submit(a, rec)
        self.assertEqual(len(subs), 3)
        rows = frappe.get_all(
            "Oral Activity Submission",
            filters={"name": ["in", subs]},
            fields=["student", "recording", "course_assess", "submitted_on"],
        )
        self.assertEqual({r.student for r in rows}, {a.name, b.name, c.name})
        self.assertEqual({r.recording for r in rows}, {rec})
        self.assertEqual({r.course_assess for r in rows}, {self.row})
        self.assertTrue(all(r.submitted_on for r in rows))
        self.assertRaises(frappe.ValidationError, self.submit, b, rec)

    def test_no_second_recording_and_the_absent_member_still_records(self):
        a, b, _c, d = self.students
        self.record(a, present=[b])
        self.assertFalse(self.state(a)["may_record"])
        self.assertFalse(self.state(b)["may_record"])
        self.assertRaises(frappe.PermissionError, self.record, b)
        later = self.state(d)
        self.assertTrue(later["may_record"])
        self.assertNotIn(a.name, [p["student"] for p in later["choosable"]])

    def test_a_grade_reaches_the_card_and_the_gradebook_like_an_assignment(self):
        a, b, _c, _d = self.students
        subs = self.submit(a, self.record(a, present=[b]))
        mine = frappe.db.get_value(
            "Oral Activity Submission", {"name": ["in", subs], "student": a.name}
        )
        oral_activities.save_grade(mine, 88, "Clear and kind.")
        card = frappe.db.get_value(
            "Course Assess Results Detail",
            self.cards[a.name],
            ["rawscore_card"],
            as_dict=True,
        )
        self.assertEqual(float(card.rawscore_card), 88.0)
        other = frappe.db.get_value(
            "Course Assess Results Detail", self.cards[b.name], "rawscore_card"
        )
        self.assertFalse(other)


class TestGroups(OralActivityCase):
    group_size = 2

    def test_groups_are_made_once_and_limit_who_can_be_named(self):
        a = self.students[0]
        first = self.state(a)
        self.state(self.students[1])
        groups = oral_activities._section_groups(self.cs)
        self.assertEqual(len(groups), 2)
        self.assertEqual(sorted(len(g) for g in groups.values()), [2, 2])
        mine = next(g for g in groups.values() if a.name in g)
        self.assertEqual(
            [p["student"] for p in first["choosable"]], [s for s in mine if s != a.name]
        )
        stranger = next(s for s in self.students if s.name not in mine)
        self.assertRaises(frappe.ValidationError, self.record, a, [stranger])


class TestTalkTimeIsPrivate(OralActivityCase):
    def labelled(self):
        a, b, _c, _d = self.students
        rec = self.record(a, present=[b])
        doc = frappe.get_doc("Oral Recording", rec)
        doc.transcript = json.dumps(
            [
                {"start": 0, "end": 30, "text": "x", "speaker": "Speaker 1"},
                {"start": 30, "end": 40, "text": "y", "speaker": "Speaker 2"},
            ]
        )
        oral._refresh_speakers(doc, json.loads(doc.transcript))
        doc.save(ignore_permissions=True)
        return rec

    def test_a_student_sees_only_their_own_talk_time(self):
        a, b, _c, _d = self.students
        rec = self.labelled()
        frappe.set_user(a.user)
        oral.link_speaker(rec, "Speaker 1", a.name)
        oral.link_speaker(rec, "Speaker 2", b.name)
        mine = oral.get_recording(rec)["speakers"]
        frappe.set_user("Administrator")
        own = next(s for s in mine if s["student"] == a.name)
        other = next(s for s in mine if s["student"] == b.name)
        self.assertEqual((own["talk_s"], own["share"]), (30.0, 75))
        self.assertNotIn("talk_s", other)
        staff = oral.get_recording(rec)["speakers"]
        self.assertTrue(all("talk_s" in s for s in staff))

    def test_labels_lock_once_graded_and_staff_can_still_correct(self):
        a, b, _c, _d = self.students
        rec = self.labelled()
        subs = self.submit(a, rec)
        frappe.set_user(a.user)
        self.assertRaises(
            frappe.ValidationError,
            oral.link_speaker,
            rec,
            "Speaker 1",
            self.students[3].name,
        )
        frappe.set_user("Administrator")
        oral_activities.save_grade(subs[0], 70)
        frappe.set_user(b.user)
        self.assertRaises(
            frappe.PermissionError, oral.link_speaker, rec, "Speaker 1", b.name
        )
        frappe.set_user("Administrator")
        oral.link_speaker(rec, "Speaker 1", b.name)

    def test_talk_time_is_never_written_into_a_score(self):
        a, b, _c, _d = self.students
        rec = self.labelled()
        subs = self.submit(a, rec)
        for name in subs:
            doc = frappe.get_doc("Oral Activity Submission", name)
            self.assertEqual(
                (doc.status, doc.grade or 0, doc.percentage or 0), ("Not Graded", 0, 0)
            )
        oral_activities.save_grade(subs[0], 50)
        self.assertEqual(
            frappe.db.get_value("Oral Activity Submission", subs[0], "percentage"), 50
        )


class TestIndividual(OralActivityCase):
    mode = "Individual"
    size = 2

    def test_an_individual_recording_names_no_one_else(self):
        a, b = self.students
        self.assertEqual(self.state(a)["choosable"], [])
        self.assertRaises(frappe.ValidationError, self.record, a, [b])
        rec = self.record(a)
        self.assertEqual(len(self.submit(a, rec)), 1)


class TestLateAndCutoff(OralActivityCase):
    mode = "Individual"
    size = 1

    def test_lateness_is_recorded_and_the_cutoff_refuses(self):
        (a,) = self.students
        frappe.db.set_value(
            "Scheduled Course Assess Criteria",
            self.row,
            {"due_date": add_to_date(now_datetime(), days=-1)},
        )
        rec = self.record(a)
        (sub,) = self.submit(a, rec)
        self.assertGreater(
            frappe.db.get_value("Oral Activity Submission", sub, "late"), 0
        )

    def test_after_the_cutoff_nothing_is_submitted(self):
        (a,) = self.students
        frappe.db.set_value(
            "Scheduled Course Assess Criteria",
            self.row,
            {
                "due_date": add_to_date(now_datetime(), days=-3),
                "cutoff_date": add_to_date(now_datetime(), days=-2),
            },
        )
        rec = self.record(a)
        self.assertRaises(frappe.ValidationError, self.submit, a, rec)
        self.assertFalse(
            frappe.db.exists("Oral Activity Submission", {"recording": rec})
        )


class TestUpload(OralActivityCase):
    mode = "Individual"
    size = 1

    def upload(self, student):
        files = {
            "file": SimpleNamespace(
                stream=io.BytesIO(b"phone-audio"), mimetype="audio/mp4"
            )
        }
        frappe.set_user(student.user)
        try:
            with patch.object(frappe, "request", SimpleNamespace(files=files)):
                return oral.upload_recording(
                    "Scheduled Course Assess Criteria", self.row
                )
        finally:
            frappe.set_user("Administrator")

    def test_an_upload_is_refused_unless_allowed(self):
        self.assertRaises(frappe.PermissionError, self.upload, self.students[0])

    def test_an_allowed_upload_is_marked_as_one(self):
        frappe.db.set_value("Oral Activity", self.activity.name, "allow_upload", 1)
        out = self.upload(self.students[0])
        doc = frappe.get_doc("Oral Recording", out["recording"])
        self.assertEqual(
            (doc.source, doc.duration_s, doc.mime_type), ("Uploaded", 0, "audio/mp4")
        )
        self.assertTrue(doc.audio)


class TestNotInGrading(OralActivityCase):
    mode = "Individual"
    size = 1

    def test_an_activity_outside_the_grading_says_so_instead_of_failing(self):
        other = _activity("Individual")
        frappe.set_user(self.students[0].user)
        try:
            self.assertEqual(
                oral_activities.my_state(self.cs, other.name), {"gradeable": False}
            )
        finally:
            frappe.set_user("Administrator")
