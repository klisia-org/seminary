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


class TestDiscussionVisibility(IntegrationTestCase):
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
