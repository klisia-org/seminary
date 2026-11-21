# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/101: channels by cohort type, reactions by channel, Pray saves,
cohort meetings.

The members here are deliberately not all students: an invited pastor (a
Cohort Participant with no Student and no classes), a staff member with no
classes, and an invitee who has not signed in yet (a Person with no User).
"""

import json
from datetime import timedelta

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from seminary.seminary import oral_groups
from seminary.seminary.discipleship import feed_api
from seminary.seminary.discipleship import meetings as mt
from seminary.seminary.tests import cohort_fixtures as fx


def _portal_person(label, roles=("Cohort Participant",)):
    user = fx.make_user(roles=roles)
    return fx.make_person(label, user=user.name)


def _member(cohort, person, is_leader=0, role="Member"):
    name = frappe.db.get_value(
        "Cohort Membership", {"cohort": cohort, "person": person}
    )
    if name:
        frappe.db.set_value(
            "Cohort Membership", name, {"active": 1, "is_leader": is_leader}
        )
        return
    fx.add_member(cohort, person, role=role, is_leader=is_leader)


def _channel(kind="generic", default=0, reactions=None):
    return frappe.get_doc(
        {
            "doctype": "Cohort Channel",
            "channel_name": fx.uid("Channel"),
            "channel_kind": kind,
            "enabled": 1,
            "is_default": default,
            "default_visibility": "cohort_only",
            "reactions": [{"reaction_type": r} for r in reactions or []],
        }
    ).insert(ignore_permissions=True)


def _reaction(label, saves=0):
    if not frappe.db.exists("Cohort Reaction Type", label):
        frappe.get_doc(
            {
                "doctype": "Cohort Reaction Type",
                "label": label,
                "glyph": "*",
                "enabled": 1,
                "saves_post": saves,
            }
        ).insert(ignore_permissions=True)
    else:
        frappe.db.set_value("Cohort Reaction Type", label, "saves_post", saves)
    return label


def _utc(dt):
    return oral_groups._utc_iso(dt)


def _future(days=3, hour=10, length=60):
    start = (now_datetime() + timedelta(days=days)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    return start, start + timedelta(minutes=length)


class TestCommunityChannels(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.pray = _reaction(fx.uid("Pray"), saves=1)
        cls.like = _reaction(fx.uid("Like"))
        cls.insight = _reaction(fx.uid("Insight"))
        cls.prayer = _channel("prayer", reactions=[cls.pray, cls.like])
        cls.faculty = _channel(reactions=[cls.like, cls.insight])
        cls.general = _channel(reactions=[cls.like])
        cls.faculty_type = fx.make_cohort_type(
            channels=[{"channel": cls.faculty.name}, {"channel": cls.prayer.name}]
        )
        cls.student_type = fx.make_cohort_type(
            channels=[{"channel": cls.general.name}, {"channel": cls.prayer.name}]
        )
        cls.dean = _portal_person("Dean", roles=("Cohort Participant",))
        cls.teacher = _portal_person("Teacher", roles=("Instructor",))
        cls.student = _portal_person("Student", roles=("Student",))
        cls.faculty_cohort = fx.make_cohort(cls.faculty_type.name, cls.dean.name).name
        _member(cls.faculty_cohort, cls.dean.name, is_leader=1)
        _member(cls.faculty_cohort, cls.teacher.name)
        cls.student_cohort = fx.make_cohort(
            cls.student_type.name, cls.teacher.name
        ).name
        _member(cls.student_cohort, cls.teacher.name, is_leader=1)
        _member(cls.student_cohort, cls.student.name)

    def tearDown(self):
        frappe.set_user("Administrator")

    # ------------------------------------------------------------ types
    def test_new_type_starts_with_default_channels_and_reminders(self):
        default = _channel(default=1)
        ctype = fx.make_cohort_type()
        offered = [r.channel for r in ctype.channels]
        self.assertIn(default.name, offered)
        self.assertNotIn(self.faculty.name, offered)
        self.assertEqual(
            sorted(r.hours_before for r in ctype.meeting_reminders), [1, 24]
        )

    def test_a_type_needs_a_channel(self):
        ctype = frappe.get_doc("Cohort Type", self.faculty_type.name)
        ctype.channels = []
        with self.assertRaises(frappe.ValidationError):
            ctype.save(ignore_permissions=True)

    # ------------------------------------------------------------ posts
    def test_post_must_use_a_channel_of_the_cohort(self):
        frappe.set_user(self.student.user)
        with self.assertRaises(frappe.ValidationError):
            feed_api.create_post(
                self.student_cohort, self.faculty.name, content="<p>Hi</p>"
            )
        name = feed_api.create_post(
            self.student_cohort, self.general.name, content="<p>Hi</p>"
        )
        self.assertTrue(name)

    def test_whole_community_post_stays_in_its_channel(self):
        frappe.set_user(self.dean.user)
        post = feed_api.create_post(
            self.faculty_cohort,
            self.faculty.name,
            content="<p>Rubric tips</p>",
            visibility="portal_users",
        )
        seen = lambda: frappe.get_list(  # noqa: E731
            "Cohort Post", filters={"name": post}, pluck="name"
        )
        self.assertEqual(seen(), [post])
        frappe.set_user(self.teacher.user)  # faculty cohort member
        self.assertEqual(seen(), [post])
        frappe.set_user(self.student.user)  # no cohort offers the faculty channel
        self.assertEqual(seen(), [])
        self.assertFalse(frappe.get_doc("Cohort Post", post).has_permission("read"))

    def test_topics_suggested_only_from_readable_posts(self):
        """Section 5.6: a topic seen only on someone's private post is not
        offered; counts are of posts the author can read."""
        secret, shared = fx.uid("secretgrief"), fx.uid("sharedgrading")
        frappe.set_user(self.teacher.user)
        feed_api.create_post(
            self.student_cohort,
            self.general.name,
            content="<p>Note to self</p>",
            visibility="private",
            topics=[secret, shared],
        )
        feed_api.create_post(
            self.student_cohort,
            self.general.name,
            content="<p>Grading</p>",
            topics=[shared],
        )
        self.assertEqual(
            feed_api.suggest_topics("#" + shared),
            [{"topic": shared, "posts": 2}],
        )
        frappe.set_user(self.student.user)
        self.assertEqual(feed_api.suggest_topics(secret), [])
        self.assertEqual(
            feed_api.suggest_topics(shared), [{"topic": shared, "posts": 1}]
        )

    def test_channels_listed_per_cohort_with_reactions(self):
        frappe.set_user(self.student.user)
        rows = feed_api.list_channels(self.student_cohort)
        self.assertEqual(
            {r["name"] for r in rows}, {self.general.name, self.prayer.name}
        )
        prayer = next(r for r in rows if r["name"] == self.prayer.name)
        self.assertEqual(prayer["reactions"], [self.pray, self.like])
        with self.assertRaises(frappe.PermissionError):
            feed_api.list_channels(self.faculty_cohort)

    # -------------------------------------------------------- reactions
    def _prayer_post(self):
        frappe.set_user(self.student.user)
        return feed_api.create_post(
            self.student_cohort, self.prayer.name, content="<p>Pray for me</p>"
        )

    def test_reaction_must_be_offered_in_the_channel(self):
        post = self._prayer_post()
        frappe.set_user(self.teacher.user)
        with self.assertRaises(frappe.ValidationError):
            feed_api.toggle_reaction(self.insight, post=post)
        self.assertTrue(feed_api.toggle_reaction(self.like, post=post)["reacted"])

    def test_pray_saves_and_taking_it_back_unsaves(self):
        post = self._prayer_post()
        frappe.set_user(self.teacher.user)
        self.assertTrue(feed_api.toggle_reaction(self.pray, post=post)["saved"])
        save = frappe.db.get_value(
            "Cohort Post Save",
            {"post": post, "person": self.teacher.name},
            ["via_reaction"],
        )
        self.assertEqual(save, 1)
        self.assertFalse(feed_api.toggle_reaction(self.pray, post=post)["saved"])

    def test_unsaving_keeps_the_prayer_and_the_post(self):
        post = self._prayer_post()
        frappe.set_user(self.teacher.user)
        feed_api.toggle_reaction(self.pray, post=post)
        self.assertFalse(feed_api.toggle_save(post)["saved"])
        self.assertTrue(
            frappe.db.exists(
                "Cohort Post Reaction",
                {"post": post, "person": self.teacher.name, "reaction_type": self.pray},
            )
        )
        self.assertEqual(frappe.db.get_value("Cohort Post", post, "prayer_answered"), 0)

    def test_a_save_made_by_hand_survives_taking_the_reaction_back(self):
        post = self._prayer_post()
        frappe.set_user(self.teacher.user)
        feed_api.toggle_save(post)
        feed_api.toggle_reaction(self.pray, post=post)
        self.assertTrue(feed_api.toggle_reaction(self.pray, post=post)["saved"])

    def test_answered_prayer_reaches_those_who_prayed(self):
        post = self._prayer_post()
        frappe.set_user(self.teacher.user)
        feed_api.toggle_reaction(self.pray, post=post)
        feed_api.toggle_save(post)  # unsaved since: still prayed
        frappe.set_user("Administrator")
        self.assertEqual(feed_api.praying_partners(post), [self.teacher.name])
        frappe.set_user(self.student.user)
        feed_api.mark_prayer_answered(post, note="Healed")
        self.assertTrue(
            frappe.db.exists(
                "Communication Log",
                {
                    "reference_doctype": "Cohort Post",
                    "reference_name": post,
                    "person": self.teacher.name,
                },
            )
        )


class TestCohortMeetings(IntegrationTestCase):
    """A faculty development cohort: a dean leads; an instructor, an invited
    pastor, a staff member with no classes and an invitee with no account."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.ctype = fx.make_cohort_type()
        cls.dean = _portal_person("Dean")
        cls.teacher = fx.make_instructor().person
        cls.teacher = frappe.get_doc("Person", cls.teacher)
        cls.pastor = _portal_person("Pastor")
        staff_user = fx.make_user(roles=("Cohort Participant",))
        cls.staffer = fx.make_person("Staff", user=staff_user.name)
        cls.staffer.db_set("is_staff", 1)
        cls.invitee = fx.make_person("Invitee")  # no User yet
        cls.outsider = _portal_person("Outsider")
        cls.cohort = fx.make_cohort(cls.ctype.name, cls.dean.name).name
        _member(cls.cohort, cls.dean.name, is_leader=1)
        for p in (cls.teacher, cls.pastor, cls.staffer, cls.invitee):
            _member(cls.cohort, p.name)

    def tearDown(self):
        frappe.set_user("Administrator")

    def _poll(self):
        frappe.set_user(self.dean.user)
        a, b = _future(3), _future(4)
        name = mt.create_poll(
            self.cohort,
            "Rubric workshop",
            json.dumps(
                [
                    {"start_utc": _utc(a[0]), "end_utc": _utc(a[1])},
                    {"start_utc": _utc(b[0]), "end_utc": _utc(b[1])},
                ]
            ),
            _utc(now_datetime() + timedelta(days=2)),
            link="https://meet.example.test/x",
        )
        return frappe.get_doc(mt.MEETING, name)

    def test_members_without_classes_or_accounts_are_read_safely(self):
        people = {m.person: m for m in mt.members(self.cohort)}
        self.assertIsNone(people[self.invitee.name].user)
        self.assertIsNone(people[self.invitee.name].time_zone)
        self.assertIsNone(people[self.pastor.name].student)
        start, end = _future(3)
        busy = mt._busy(list(people.values()), start.date(), end.date())
        self.assertEqual(busy[self.pastor.name], [])
        self.assertEqual(busy[self.staffer.name], [])
        self.assertEqual(busy[self.invitee.name], [])

    def test_poll_vote_and_pick(self):
        doc = self._poll()
        first, second = doc.options
        frappe.set_user(self.pastor.user)
        mt.vote(doc.name, json.dumps({first.name: "Yes", second.name: "No"}))
        frappe.set_user(self.staffer.user)
        mt.vote(doc.name, json.dumps({first.name: "If need be"}))
        frappe.set_user(self.dean.user)
        view = next(
            m
            for m in mt.cohort_meetings(self.cohort)["meetings"]
            if m["name"] == doc.name
        )
        tally = view["options"][0]["tally"]
        self.assertEqual((tally["Yes"], tally["If need be"]), (1, 1))
        self.assertEqual(view["options"][0]["clashes"], [])
        self.assertIn(self.invitee.full_name, view["non_voters"])
        mt.choose_option(doc.name, first.name)
        doc.reload()
        self.assertEqual(doc.status, "Scheduled")
        self.assertEqual(doc.starts_on, first.starts_on)
        self.assertEqual(
            {a.person for a in doc.attendance},
            {
                self.dean.name,
                self.teacher.name,
                self.pastor.name,
                self.staffer.name,
                self.invitee.name,
            },
        )

    def test_only_members_vote_and_only_leaders_schedule(self):
        doc = self._poll()
        frappe.set_user(self.outsider.user)
        with self.assertRaises(frappe.PermissionError):
            mt.vote(doc.name, json.dumps({doc.options[0].name: "Yes"}))
        frappe.set_user(self.pastor.user)
        start, end = _future(5)
        with self.assertRaises(frappe.PermissionError):
            mt.schedule(self.cohort, "Mine", _utc(start), _utc(end))

    def test_series_and_cancelling_the_rest(self):
        frappe.set_user(self.dean.user)
        start, end = _future(2, hour=19)
        out = mt.schedule(
            self.cohort,
            "Weekly prayer",
            _utc(start),
            _utc(end),
            mode="In person",
            location="Chapel",
            repeat="weekly",
            count=3,
        )
        self.assertEqual(len(out["created"]), 3)
        series = {frappe.db.get_value(mt.MEETING, n, "series") for n in out["created"]}
        self.assertEqual(len(series), 1)
        second = frappe.get_doc(mt.MEETING, out["created"][1])
        self.assertEqual(second.starts_on.date(), (start + timedelta(days=7)).date())
        mt.cancel_meeting(out["created"][1], rest_of_series=1)
        statuses = [
            frappe.db.get_value(mt.MEETING, n, "status") for n in out["created"]
        ]
        self.assertEqual(statuses, ["Scheduled", "Cancelled", "Cancelled"])

    def test_in_person_needs_a_place(self):
        frappe.set_user(self.dean.user)
        start, end = _future(6)
        with self.assertRaises(frappe.ValidationError):
            mt.schedule(self.cohort, "Lunch", _utc(start), _utc(end), mode="In person")

    def test_school_account_only_where_the_type_allows(self):
        frappe.set_user(self.dean.user)
        start, end = _future(6)
        with self.assertRaises(frappe.ValidationError):
            mt.schedule(self.cohort, "Call", _utc(start), _utc(end), school_meeting=1)

    def test_reminders_follow_the_meeting(self):
        frappe.set_user(self.dean.user)
        start, end = _future(4)
        name = mt.schedule(
            self.cohort, "Check-in", _utc(start), _utc(end), link="https://x.test/m"
        )["created"][0]
        queued = lambda: frappe.get_all(  # noqa: E731
            "Communication Log",
            filters={
                "reference_doctype": mt.MEETING,
                "reference_name": name,
                "status": "Queued",
                "scheduled_at": ["is", "set"],
            },
            fields=["person", "scheduled_at"],
        )
        before = queued()
        self.assertTrue(before)
        self.assertEqual(
            {r.scheduled_at for r in before},
            {start - timedelta(hours=24), start - timedelta(hours=1)},
        )
        # The invitee has no account, so only email; nobody errors.
        self.assertIn(self.invitee.name, {r.person for r in before})
        later_start, later_end = _future(5)
        mt.move_meeting(name, _utc(later_start), _utc(later_end))
        after = queued()
        self.assertEqual(
            {r.scheduled_at for r in after},
            {later_start - timedelta(hours=24), later_start - timedelta(hours=1)},
        )

    def test_attendance_after_the_start_only(self):
        frappe.set_user(self.dean.user)
        start, end = _future(1)
        name = mt.schedule(
            self.cohort, "Soon", _utc(start), _utc(end), link="https://x.test/m"
        )["created"][0]
        with self.assertRaises(frappe.ValidationError):
            mt.mark_attendance(
                name, json.dumps([{"person": self.pastor.name, "status": "Present"}])
            )
        frappe.db.set_value(
            mt.MEETING, name, {"starts_on": now_datetime() - timedelta(minutes=5)}
        )
        mt.mark_attendance(
            name, json.dumps([{"person": self.pastor.name, "status": "Present"}])
        )
        rows = {a.person: a.status for a in frappe.get_doc(mt.MEETING, name).attendance}
        self.assertEqual(rows[self.pastor.name], "Present")
        frappe.set_user(self.pastor.user)
        view = next(
            m for m in mt.cohort_meetings(self.cohort)["meetings"] if m["name"] == name
        )
        self.assertEqual(view["my_attendance"], "Present")
        self.assertNotIn("attendance", view)

    def test_calendar_feed(self):
        frappe.set_user(self.pastor.user)
        url = mt.calendar_feed_url(self.cohort)
        token = url.split("token=")[1]
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            mt.cohort_ics(self.cohort, "wrong")
        mt.cohort_ics(self.cohort, token)
        self.assertIn("BEGIN:VCALENDAR", frappe.local.response.filecontent)
        frappe.set_user("Administrator")
        frappe.db.set_value(
            "Cohort Type", self.ctype.name, "meetings_in_calendar_feed", 0
        )
        try:
            frappe.set_user(self.pastor.user)
            with self.assertRaises(frappe.ValidationError):
                mt.calendar_feed_url(self.cohort)
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_value(
                "Cohort Type", self.ctype.name, "meetings_in_calendar_feed", 1
            )

    def test_poll_reminders_and_close_notice(self):
        doc = self._poll()
        frappe.set_user("Administrator")
        frappe.db.set_value(
            mt.MEETING, doc.name, "poll_closes_on", now_datetime() + timedelta(hours=3)
        )
        mt.hourly()
        self.assertEqual(frappe.db.get_value(mt.MEETING, doc.name, "poll_reminded"), 1)
        frappe.db.set_value(
            mt.MEETING, doc.name, "poll_closes_on", now_datetime() - timedelta(hours=1)
        )
        mt.hourly()
        self.assertEqual(
            frappe.db.get_value(mt.MEETING, doc.name, "poll_close_notified"), 1
        )
