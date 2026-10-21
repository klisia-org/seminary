# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""The Students tab on a course page (privatedocs p015 §4).

One row per active roster student, for the section's instructors: work waiting
for feedback, the student's last activity in the course, whether the projected
grade is below passing (not on competency sections), and the attendance alert.

When Aretenic is installed, each ``course_interaction`` hook adds its interaction
summary for the section and, per student, the last instructor interaction and
the messages waiting for a reply. Its contract:

    fn(course_schedule=<name>) -> None | {
        "summary": {"computed_on": str, "frozen": bool,
                    "items": [{"label": str, "value": str, "flagged": bool}],
                    "flags": [str, ...]},
        "students": {<Student>: {"last_instructor_interaction": str | None,
                                 "messages_waiting": int}},
    }

A failing hook is logged and ignored: the tab never depends on it.
"""

import frappe
from frappe.utils import date_diff, get_datetime, now_datetime

from seminary.seminary import cbe
from seminary.seminary.grade_projection import (
    compute,
    section_assessments,
    section_scale,
)
from seminary.seminary.guards import require_course_staff

# (doctype, section field, "submitted at" expression) for work an instructor
# grades by hand. Quizzes grade themselves and never wait.
_WAITING = (
    ("Assignment Submission", "course", "coalesce(submitted_on, creation)"),
    ("Discussion Submission", "coursesc", "creation"),
    ("Exam Submission", "course", "creation"),
)

# Every submission counts as activity, quizzes included.
_SUBMITTED = (
    *_WAITING,
    ("Quiz Submission", "course", "creation"),
)


def _student_of(row, by_user):
    return row.get("student") or by_user.get(row.get("member"))


def _bump(latest, student, when):
    if not student or not when:
        return
    when = get_datetime(when)
    if student not in latest or when > latest[student]:
        latest[student] = when


def _waiting_feedback(course_schedule, by_user):
    """{student: [submitted datetimes]} of hand-graded work not yet Graded."""
    waiting = {}
    for doctype, section_field, submitted in _WAITING:
        extra = " and docstatus < 2" if doctype == "Exam Submission" else ""
        for row in frappe.db.sql(
            f"""select student, member, {submitted} as submitted
            from `tab{doctype}`
            where `{section_field}` = %s and status = 'Not Graded'{extra}""",  # nosec B608 -- doctype, field and expression are module constants
            (course_schedule,),
            as_dict=True,
        ):
            student = _student_of(row, by_user)
            if student and row.submitted:
                waiting.setdefault(student, []).append(get_datetime(row.submitted))
    return waiting


def _last_activity(course_schedule, by_user, rosters):
    """{student: datetime} of the latest submission, discussion reply, SCORM
    commit or attendance marked Present in the section."""
    latest = {}
    for doctype, section_field, submitted in _SUBMITTED:
        for row in frappe.db.sql(
            f"""select student, member, max({submitted}) as at
            from `tab{doctype}`
            where `{section_field}` = %s
            group by student, member""",  # nosec B608 -- doctype, field and expression are module constants
            (course_schedule,),
            as_dict=True,
        ):
            _bump(latest, _student_of(row, by_user), row.at)

    for row in frappe.db.sql(
        """select r.student, r.member, max(coalesce(r.reply_dt, r.creation)) as at
        from `tabDiscussion Submission Replies` r
        join `tabDiscussion Submission` d on d.name = r.parent
        where d.coursesc = %s and r.parenttype = 'Discussion Submission'
        group by r.student, r.member""",
        (course_schedule,),
        as_dict=True,
    ):
        _bump(latest, _student_of(row, by_user), row.at)

    student_of_roster = {r.name: r.student for r in rosters}
    for row in frappe.db.sql(
        """select student as roster, member, max(last_commit_on) as at
        from `tabSCORM Attempt`
        where course = %s
        group by student, member""",
        (course_schedule,),
        as_dict=True,
    ):
        student = student_of_roster.get(row.roster) or by_user.get(row.member)
        _bump(latest, student, row.at)

    for row in frappe.db.sql(
        """select student, max(date) as at
        from `tabStudent Attendance`
        where course_schedule = %s and status = 'Present' and docstatus < 2
        group by student""",
        (course_schedule,),
        as_dict=True,
    ):
        _bump(latest, row.student, row.at)
    return latest


def _interaction(course_schedule):
    """The first ``course_interaction`` hook that answers, or None."""
    from seminary.seminary.utils import _aretenic_enabled

    if not _aretenic_enabled():
        return None
    for fn in frappe.get_hooks("course_interaction") or []:
        try:
            value = frappe.get_attr(fn)(course_schedule=course_schedule)
        except Exception:
            frappe.log_error(title="Students tab: course interaction hook failed")
            value = None
        if isinstance(value, dict) and value:
            return value
    return None


@frappe.whitelist()
def get_course_students(course_schedule):
    """Rows for the Students tab. The section's teaching staff only."""
    require_course_staff(course_schedule, include_registrar=True)

    rosters = frappe.get_all(
        "Scheduled Course Roster",
        filters={"course_sc": course_schedule, "active": 1},
        fields=[
            "name",
            "student",
            "stuname_roster",
            "stuemail_rc",
            "audit_bool",
            "absence_limit",
            "attendance_alert_level",
        ],
        order_by="stuname_roster asc",
    )
    by_user = {r.stuemail_rc: r.student for r in rosters if r.stuemail_rc}
    is_cbe = bool(cbe.framework_for(course_schedule))

    waiting = _waiting_feedback(course_schedule, by_user)
    activity = _last_activity(course_schedule, by_user, rosters)

    grades = {}
    if not is_cbe:
        max_grade, intervals = section_scale(course_schedule)
        rows = section_assessments(course_schedule, [r.name for r in rosters])
        grades = {
            roster: compute(assessments, intervals, max_grade)["projected"]
            for roster, assessments in rows.items()
        }

    interaction = _interaction(course_schedule)
    per_student = (interaction or {}).get("students") or {}

    now = now_datetime()
    students = []
    for r in rosters:
        pending = waiting.get(r.student) or []
        last = activity.get(r.student)
        row = {
            "student": r.student,
            "student_name": r.stuname_roster or r.student,
            "roster": r.name,
            "auditing": bool(r.audit_bool),
            "waiting": len(pending),
            "oldest_waiting_days": date_diff(now, min(pending)) if pending else None,
            "last_activity": str(last) if last else None,
            "days_since_activity": date_diff(now, last) if last else None,
            "attendance_alert_level": r.attendance_alert_level or 0,
            "absence_limit": r.absence_limit or 0,
        }
        if not is_cbe:
            projected = grades.get(r.name)
            row["projected_grade"] = projected
            row["at_risk"] = (
                None
                if projected is None or r.audit_bool
                else projected["grade_pass"] != "Pass"
            )
        if interaction is not None:
            mine = per_student.get(r.student) or {}
            row["last_instructor_interaction"] = mine.get("last_instructor_interaction")
            row["messages_waiting"] = mine.get("messages_waiting") or 0
        students.append(row)

    return {
        "is_cbe": is_cbe,
        "students": students,
        "interaction": (
            {"summary": interaction.get("summary")} if interaction is not None else None
        ),
    }
