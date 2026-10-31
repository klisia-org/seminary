# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Threads, notices and unread counts on graded discussions (decisions/097).

A reply may answer another reply (`in_reply_to`); the person answered gets one
in-app notice. What is new is computed from one `Discussion Read State` row per
user and discussion, never from a row per reply. Lesson questions share the
notice only (097 §7).
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from seminary.seminary.guards import _memo, require_enrolled

READ_STATE = "Discussion Read State"


def instructor_users(course_schedule):
    """Users of the section's instructors."""

    def _load():
        names = frappe.get_all(
            "Course Schedule Instructors",
            filters={"parent": course_schedule, "parenttype": "Course Schedule"},
            pluck="instructor",
        )
        if not names:
            return set()
        return set(
            frappe.get_all(
                "Instructor",
                filters={"name": ["in", names], "user": ["is", "set"]},
                pluck="user",
            )
        )

    return _memo(("discussion_instructor_users", course_schedule), _load)


def last_seen(course_schedule, discussion_id, user=None):
    return frappe.db.get_value(
        READ_STATE,
        {
            "user": user or frappe.session.user,
            "course_schedule": course_schedule,
            "disc_activity": discussion_id,
        },
        "last_seen",
    )


def mark_seen(course_schedule, discussion_id, user=None):
    user = user or frappe.session.user
    filters = {
        "user": user,
        "course_schedule": course_schedule,
        "disc_activity": discussion_id,
    }
    name = frappe.db.exists(READ_STATE, filters)
    if name:
        frappe.db.set_value(
            READ_STATE, name, "last_seen", now_datetime(), update_modified=False
        )
    else:
        frappe.get_doc(
            {"doctype": READ_STATE, **filters, "last_seen": now_datetime()}
        ).insert(ignore_permissions=True)


def annotate(submissions, course_schedule, discussion_id, user=None):
    """Mark each post and reply `is_new` and each reply `by_instructor`, in place."""
    user = user or frappe.session.user
    seen = last_seen(course_schedule, discussion_id, user)
    seen = get_datetime(seen) if seen else None
    teachers = instructor_users(course_schedule)

    def _new(author, at):
        return bool(author != user and at and (not seen or get_datetime(at) > seen))

    for sub in submissions:
        sub["is_new"] = _new(sub.get("member") or sub.get("owner"), sub.get("creation"))
        for reply in sub.get("replies") or []:
            reply["by_instructor"] = reply.get("member") in teachers
            reply["is_new"] = _new(reply.get("member"), reply.get("creation"))
    return submissions


def unread_count(course_schedule, discussion_id, user=None):
    """Posts and replies by others, since the user last opened the discussion,
    on the posts they may read."""
    from seminary.seminary.api import _visible_classmates

    user = user or frappe.session.user
    visible = _visible_classmates(course_schedule, discussion_id, user)
    if visible is not None:
        visible = visible | {user}
    seen = last_seen(course_schedule, discussion_id, user)

    filters = {"coursesc": course_schedule, "disc_activity": discussion_id}
    if visible is not None:
        filters["member"] = ["in", list(visible)]
    posts = frappe.get_all(
        "Discussion Submission", filters=filters, fields=["name", "member", "creation"]
    )
    if not posts:
        return 0
    count = sum(
        1 for p in posts if p.member != user and (not seen or p.creation > seen)
    )
    reply_filters = {
        "parent": ["in", [p.name for p in posts]],
        "parenttype": "Discussion Submission",
        "member": ["!=", user],
    }
    if seen:
        reply_filters["creation"] = [">", seen]
    count += frappe.db.count("Discussion Submission Replies", reply_filters)
    return count


def answered_user(submission, in_reply_to):
    """Whose words a new reply answers: the reply's author, else the post's."""
    if in_reply_to:
        return frappe.db.get_value(
            "Discussion Submission Replies",
            {"name": in_reply_to, "parent": submission},
            "member",
        )
    return frappe.db.get_value("Discussion Submission", submission, "member")


def _notify(user, subject, message, reference_doctype, reference_name, dedupe_key):
    if not user or user == frappe.session.user:
        return
    person = frappe.db.get_value("Person", {"user": user}, "name")
    if not person:
        return
    from seminary.seminary import comms

    try:
        comms.send_message(
            channel="In-App",
            subject=subject,
            message=message,
            person=person,
            category="Academic",
            reference_doctype=reference_doctype,
            reference_name=reference_name,
            triggered_by=frappe.session.user,
            dedupe_key=dedupe_key,
        )
    except Exception:
        frappe.log_error(title="Discussion reply notice failed")


def notify_discussion_reply(submission, reply_name, in_reply_to=None):
    """Tell the author of the post or reply that was answered (097 §5)."""
    row = frappe.db.get_value(
        "Discussion Submission",
        submission,
        ["coursesc", "disc_activity", "disc_title"],
        as_dict=True,
    )
    if not row:
        return
    who = frappe.db.get_value("User", frappe.session.user, "full_name")
    title = row.disc_title or frappe.db.get_value(
        "Discussion Activity", row.disc_activity, "discussion_name"
    )
    what = _("your reply") if in_reply_to else _("your post")
    _notify(
        answered_user(submission, in_reply_to),
        _("{0} replied in {1}").format(who, title),
        _("{0} answered {1} in the discussion {2}.").format(
            frappe.utils.escape_html(who),
            what,
            frappe.utils.escape_html(title or ""),
        ),
        "Course Schedule",
        row.coursesc,
        f"disc-reply-{reply_name}",
    )


def notify_lesson_answer(topic, reply_name):
    """Tell the person who asked a lesson question that it was answered (097 §7)."""
    row = frappe.db.get_value(
        "Discussion Topic",
        topic,
        ["owner", "title", "reference_doctype", "reference_docname"],
        as_dict=True,
    )
    if not row or row.reference_doctype != "Course Lesson":
        return
    lesson = frappe.db.get_value(
        "Course Lesson",
        row.reference_docname,
        ["lesson_title", "course_sc"],
        as_dict=True,
    )
    if not lesson:
        return
    who = frappe.db.get_value("User", frappe.session.user, "full_name")
    _notify(
        row.owner,
        _("{0} answered your question").format(who),
        _("{0} answered your question “{1}” on the lesson {2}.").format(
            frappe.utils.escape_html(who),
            frappe.utils.escape_html(row.title or ""),
            frappe.utils.escape_html(lesson.lesson_title or ""),
        ),
        "Course Schedule",
        lesson.course_sc,
        f"lesson-answer-{reply_name}",
    )


@frappe.whitelist()
def mark_discussion_seen(course_name, discussion_id):
    """The caller has opened the discussion: what they saw is no longer new."""
    require_enrolled(course_name)
    mark_seen(course_name, discussion_id)
    return True
