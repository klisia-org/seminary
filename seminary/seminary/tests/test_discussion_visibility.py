# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""A Discussion Activity's "post before reply" and student-group settings hold
on the server, not only in the browser."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import api
from seminary.seminary.tests import cohort_fixtures as fx


def _section():
    cs = frappe.get_doc(
        {
            "doctype": "Course Schedule",
            "name": fx.uid("CS"),
            "workflow_state": "Open",
            "open_ended": 1,
            "published": 1,
        }
    )
    cs.db_insert()
    return cs.name


def _roster(cs, student):
    frappe.get_doc(
        {
            "doctype": "Scheduled Course Roster",
            "name": f"{cs}-{student.name}",
            "course_sc": cs,
            "student": student.name,
            "stuname_roster": student.name,
            "stuemail_rc": student.user,
            "active": 1,
            "audit_bool": 0,
        }
    ).db_insert()


def _group(cs, students):
    group = frappe.get_doc({"doctype": "Student Group", "name": fx.uid("SG")})
    group.db_insert()
    for idx, student in enumerate(students, 1):
        frappe.get_doc(
            {
                "doctype": "Student Group Members",
                "name": frappe.generate_hash(length=10),
                "parent": group.name,
                "parenttype": "Student Group",
                "parentfield": "group_members",
                "idx": idx,
                "student": student.name,
            }
        ).db_insert()
    frappe.get_doc(
        {
            "doctype": "Student Group Link",
            "name": frappe.generate_hash(length=10),
            "parent": cs,
            "parenttype": "Course Schedule",
            "parentfield": "stu_groups_course",
            "student_group": group.name,
        }
    ).db_insert()


def _post(cs, activity, student):
    doc = frappe.get_doc(
        {
            "doctype": "Discussion Submission",
            "name": fx.uid("DSUB"),
            "coursesc": cs,
            "disc_activity": activity,
            "student": student.name,
            "member": student.user,
            "owner": student.user,
            "original_post": "<p>My post</p>",
            "status": "Not Graded",
        }
    )
    doc.db_insert()
    return doc.name


class DiscussionCase(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.cs = _section()
        self.me, self.peer, self.other = (fx.make_student() for _ in range(3))
        for student in (self.me, self.peer, self.other):
            _roster(self.cs, student)

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def activity(self, **settings):
        return (
            frappe.get_doc(
                {
                    "doctype": "Discussion Activity",
                    "discussion_name": fx.uid("Disc"),
                    **settings,
                }
            )
            .insert()
            .name
        )

    def read(self, activity):
        frappe.set_user(self.me.user)
        rows = api.get_discussion_submissions(self.cs, activity, member=self.me.user)
        frappe.set_user("Administrator")
        return {r.member for r in rows}


class TestDiscussionVisibility(DiscussionCase):
    def test_post_first_hides_classmates_until_the_student_posts(self):
        activity = self.activity(post_before=1)
        peer_post = _post(self.cs, activity, self.peer)

        self.assertEqual(self.read(activity), set())
        frappe.set_user(self.me.user)
        with self.assertRaises(frappe.PermissionError):
            api.reply_to_discussion_submission(peer_post, "<p>Hi</p>")
        frappe.set_user("Administrator")

        _post(self.cs, activity, self.me)
        self.assertEqual(self.read(activity), {self.peer.user})

    def test_groups_limit_what_a_student_reads_and_answers(self):
        activity = self.activity(use_studentgroup=1)
        _group(self.cs, [self.me, self.peer])
        _group(self.cs, [self.other])
        _post(self.cs, activity, self.peer)
        other_post = _post(self.cs, activity, self.other)

        self.assertEqual(self.read(activity), {self.peer.user})
        frappe.set_user(self.me.user)
        with self.assertRaises(frappe.PermissionError):
            api.reply_to_discussion_submission(other_post, "<p>Hi</p>")

    def test_staff_read_every_post(self):
        activity = self.activity(post_before=1, use_studentgroup=1)
        _group(self.cs, [self.me])
        _post(self.cs, activity, self.peer)
        _post(self.cs, activity, self.other)
        rows = api.get_discussion_submissions(self.cs, activity)
        self.assertEqual({r.member for r in rows}, {self.peer.user, self.other.user})

    def test_replies_say_who_wrote_them(self):
        # The student's "Replies n / m" counter matches on the reply's member.
        activity = self.activity()
        peer_post = _post(self.cs, activity, self.peer)
        frappe.set_user(self.me.user)
        api.reply_to_discussion_submission(peer_post, "<p>Good point</p>")
        frappe.set_user("Administrator")
        replies = api._get_discussion_replies(peer_post)
        self.assertEqual([r.member for r in replies], [self.me.user])


class TestDiscussionThreads(DiscussionCase):
    """decisions/097: answers to replies, the notice, and what is new."""

    def setUp(self):
        super().setUp()
        self.disc = self.activity()
        self.peer_post = _post(self.cs, self.disc, self.peer)
        self.sent = []
        from seminary.seminary import comms

        original = comms.send_message
        self.addCleanup(setattr, comms, "send_message", original)
        comms.send_message = lambda **kw: self.sent.append(kw)

    def reply(self, student, **kw):
        frappe.set_user(student.user)
        name = api.reply_to_discussion_submission(self.peer_post, "<p>Hi</p>", **kw)
        frappe.set_user("Administrator")
        return name

    def person(self, student):
        return frappe.db.get_value("Student", student.name, "person")

    def test_answer_to_a_reply_tells_the_reply_author(self):
        first = self.reply(self.me)
        self.assertEqual([m["person"] for m in self.sent], [self.person(self.peer)])
        self.reply(self.other, in_reply_to=first)
        self.assertEqual(self.sent[-1]["person"], self.person(self.me))
        rows = {r.name: r for r in api._get_discussion_replies(self.peer_post)}
        self.assertEqual(
            [r.in_reply_to for r in rows.values() if r.member == self.other.user],
            [first],
        )

    def test_answer_must_be_on_the_same_post(self):
        other_post = _post(self.cs, self.disc, self.other)
        frappe.set_user(self.me.user)
        stray = api.reply_to_discussion_submission(other_post, "<p>Hi</p>")
        with self.assertRaises(frappe.ValidationError):
            api.reply_to_discussion_submission(
                self.peer_post, "<p>Hi</p>", in_reply_to=stray
            )

    def test_nobody_is_told_about_their_own_reply(self):
        frappe.set_user(self.peer.user)
        api.reply_to_discussion_submission(self.peer_post, "<p>Thanks all</p>")
        frappe.set_user("Administrator")
        self.assertEqual(self.sent, [])

    def test_unread_counts_others_until_seen(self):
        from seminary.seminary import discussion_threads as threads

        self.reply(self.other)
        frappe.set_user(self.me.user)
        # The peer's post and the other student's reply.
        self.assertEqual(threads.unread_count(self.cs, self.disc), 2)
        rows = api.get_discussion_submissions(self.cs, self.disc, member=self.me.user)
        self.assertTrue(rows[0]["is_new"])
        threads.mark_discussion_seen(self.cs, self.disc)
        self.assertEqual(threads.unread_count(self.cs, self.disc), 0)
        rows = api.get_discussion_submissions(self.cs, self.disc, member=self.me.user)
        self.assertFalse(rows[0]["is_new"])

    def test_instructor_replies_are_marked(self):
        from seminary.seminary import discussion_threads as threads

        instructor = fx.make_instructor()
        frappe.get_doc(
            {
                "doctype": "Course Schedule Instructors",
                "name": frappe.generate_hash(length=10),
                "parent": self.cs,
                "parenttype": "Course Schedule",
                "parentfield": "instructor1",
                "instructor": instructor.name,
            }
        ).db_insert()
        frappe.local.p007_cache = {}
        subs = [
            {
                "member": self.peer.user,
                "creation": None,
                "replies": [
                    {"member": instructor.user, "creation": None},
                    {"member": self.me.user, "creation": None},
                ],
            }
        ]
        threads.annotate(subs, self.cs, self.disc)
        self.assertEqual(
            [r["by_instructor"] for r in subs[0]["replies"]], [True, False]
        )

    def test_lesson_question_answer_tells_who_asked(self):
        from seminary.seminary import utils

        lesson = frappe.get_doc(
            {
                "doctype": "Course Lesson",
                "name": fx.uid("LSN"),
                "lesson_title": "Romans 8",
                "course_sc": self.cs,
            }
        )
        lesson.db_insert()
        topic = frappe.get_doc(
            {
                "doctype": "Discussion Topic",
                "title": "Who is the 'I' in Romans 7?",
                "reference_doctype": "Course Lesson",
                "reference_docname": lesson.name,
            }
        )
        topic.insert(ignore_permissions=True)
        topic.db_set("owner", self.peer.user)
        frappe.set_user(self.me.user)
        utils.add_discussion_reply(topic.name, "<p>Paul, I think.</p>")
        frappe.set_user("Administrator")
        self.assertEqual([m["person"] for m in self.sent], [self.person(self.peer)])
