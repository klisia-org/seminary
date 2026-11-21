# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Oral activities: a recorded talk or a recorded group conversation (decisions/100b).

The recording is made first and belongs to the section's assessment row (the
Scheduled Course Assess Criteria that links the Oral Activity), because no
submission exists yet. Submitting it creates one Oral Activity Submission per
student on the recording, all pointing at it, so grades, due dates and the
gradebook work as for any activity.

Groups
    A *Conversation* uses the section's student groups (097). A section with
    none gets groups of ``group_size`` the first time the activity is opened;
    with no size either, the recorder may name anyone in the section. Whoever
    records names the members present; only they are on the recording.

What is not allowed for now: recording again before submitting (once a
recording is finished it is the one that counts), and a classmate's talk time.
"""

import json
import random

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, today

from seminary.seminary import deadlines, oral

SCAC = "Scheduled Course Assess Criteria"
SUBMISSION = "Oral Activity Submission"


# ------------------------------------------------------------------ lookups


def _row(scac):
    row = frappe.db.get_value(
        SCAC, scac, ["name", "parent", "parenttype", "oral", "title"], as_dict=True
    )
    if not row or row.parenttype != "Course Schedule" or not row.oral:
        frappe.throw(_("Oral activity not found."), frappe.PermissionError)
    return row


def _activity(name):
    return frappe.db.get_value(
        "Oral Activity",
        name,
        [
            "name",
            "title",
            "mode",
            "prompt",
            "max_minutes",
            "allow_upload",
            "group_size",
            "oral_steps",
            "rubric",
        ],
        as_dict=True,
    )


def _steps(activity):
    try:
        steps = json.loads(activity.oral_steps or "[]")
    except ValueError:
        steps = []
    return [s for s in steps if s in oral.PIPELINE]


def _roster(course_schedule):
    """[(user, student, name)] of the section's active students."""
    out = []
    for r in frappe.get_all(
        "Scheduled Course Roster",
        filters={"course_sc": course_schedule, "active": 1},
        fields=["student", "stuname_roster"],
        order_by="stuname_roster asc",
    ):
        user = frappe.db.get_value("Student", r.student, "user") if r.student else None
        if user:
            out.append((user, r.student, r.stuname_roster or r.student))
    return out


def _section_groups(course_schedule):
    """{group: [student]} from the section's student groups, active members only."""
    groups = {}
    for r in frappe.db.sql(
        """select k.student_group, m.student
        from `tabStudent Group Link` k
        join `tabStudent Group Members` m on m.parent = k.student_group
            and m.parenttype = 'Student Group' and m.status = 'Active'
        where k.parent = %s and k.parenttype = 'Course Schedule'
        order by k.idx, m.idx""",
        (course_schedule,),
        as_dict=True,
    ):
        groups.setdefault(r.student_group, []).append(r.student)
    return groups


def ensure_groups(course_schedule, activity):
    """Groups of ``group_size`` for a Conversation on a section that has none.

    Members are shuffled with a seed from the section and activity, so the
    groups are random but the same if two students open it at once; the lock
    on the section row keeps the second from making a second set."""
    if activity.mode != "Conversation" or cint(activity.group_size) < 2:
        return _section_groups(course_schedule)
    groups = _section_groups(course_schedule)
    if groups:
        return groups
    frappe.db.sql(
        "select name from `tabCourse Schedule` where name = %s for update",
        (course_schedule,),
    )
    groups = _section_groups(course_schedule)
    if groups:
        return groups
    students = _roster(course_schedule)
    if len(students) < 2:
        return {}
    # A fair, repeatable shuffle for grouping, not a secret.
    random.Random(f"{course_schedule}|{activity.name}").shuffle(students)  # nosec B311
    size = cint(activity.group_size)
    chunks = [students[i : i + size] for i in range(0, len(students), size)]
    if len(chunks) > 1 and len(chunks[-1]) == 1:
        chunks[-2].extend(chunks.pop())
    idx = frappe.db.count(
        "Student Group Link",
        {"parent": course_schedule, "parenttype": "Course Schedule"},
    )
    for n, chunk in enumerate(chunks, start=1):
        group = frappe.get_doc(
            {
                "doctype": "Student Group",
                "group_name": _("{0}: group {1}").format(activity.title, n),
                "active": 1,
                "group_members": [
                    {
                        "student": student,
                        "student_name": name,
                        "status": "Active",
                        "joined_on": today(),
                    }
                    for _user, student, name in chunk
                ],
            }
        ).insert(ignore_permissions=True)
        frappe.get_doc(
            {
                "doctype": "Student Group Link",
                "parent": course_schedule,
                "parenttype": "Course Schedule",
                "parentfield": "stu_groups_course",
                "idx": idx + n,
                "student_group": group.name,
            }
        ).db_insert()
    return _section_groups(course_schedule)


def _submitted(scac):
    return set(
        frappe.get_all(SUBMISSION, filters={"course_assess": scac}, pluck="student")
    )


def _recordings(scac):
    """Finished recordings for this row, newest first."""
    return frappe.get_all(
        "Oral Recording",
        filters={
            "reference_doctype": SCAC,
            "reference_name": scac,
            "status": ["!=", "Recording"],
        },
        fields=["name", "status", "recorded_by", "creation"],
        order_by="creation desc",
    )


def _students_on(recording):
    return frappe.get_all(
        "Oral Recording Participant",
        filters={"parent": recording, "parenttype": "Oral Recording"},
        fields=["user", "student"],
        order_by="idx asc",
    )


def _covered(scac):
    """Students who have submitted, or are on a finished recording."""
    covered = _submitted(scac)
    for rec in _recordings(scac):
        covered.update(p.student for p in _students_on(rec.name))
    return covered


def _my_recording(scac, student):
    for rec in _recordings(scac):
        if any(p.student == student for p in _students_on(rec.name)):
            return rec
    return None


# ---------------------------------------------------------------- the resolver


def resolve(scac, user):
    row = _row(scac)
    activity = _activity(row.oral)
    roster = _roster(row.parent)
    me = next((r for r in roster if r[0] == user), None)
    covered = _covered(scac)
    conversation = activity.mode == "Conversation"
    choosable = []
    if conversation and me:
        groups = ensure_groups(row.parent, activity)
        mine = next((g for g in groups.values() if me[1] in g), None)
        pool = set(mine) if mine is not None else {r[1] for r in roster}
        choosable = [
            (u, s)
            for u, s, _name in roster
            if s in pool and s != me[1] and s not in covered
        ]
    ctx = {
        "course_schedule": row.parent,
        "participants": [(me[0], me[1])] if me else [],
        "choosable": choosable,
        "may_record": bool(me and me[1] not in covered),
        "allow_upload": bool(cint(activity.allow_upload)),
        "steps": _steps(activity),
        "prompt": activity.prompt,
        "max_seconds": cint(activity.max_minutes) * 60,
        "may_label": "seminary.seminary.oral_activities.may_label",
    }
    if not conversation:
        ctx["expected_speakers"] = 1
    ctx["criteria"] = rubric_criteria(activity.rubric)
    return ctx


def rubric_criteria(rubric):
    """The rubric as a step reads it: each criterion with its levels, lowest
    first, and the cell's descriptor for each level."""
    from seminary.seminary.rubrics import rubric_payload

    payload = rubric_payload(rubric)
    if not payload:
        return []
    levels = sorted(payload["levels"], key=lambda lv: lv.get("percent") or 0)
    cells = {
        (c["criterion_code"], c["level"]): c["descriptor"] for c in payload["cells"]
    }
    return [
        {
            "criterion_code": c["criterion_code"],
            "title": c["title"],
            "description": c["description"],
            "levels": [
                {
                    "label": lv["label"],
                    "descriptor": cells.get((c["criterion_code"], lv["label"])),
                }
                for lv in levels
            ],
        }
        for c in payload["criteria"]
    ]


def may_label(recording, user):
    """Students on the recording link speakers until a submission is graded."""
    return not frappe.db.exists(
        SUBMISSION, {"recording": recording, "status": "Graded"}
    )


# ------------------------------------------------------------------ endpoints


def _scac_for(course, activity):
    name = frappe.db.get_value(
        SCAC, {"parent": course, "parenttype": "Course Schedule", "oral": activity}
    )
    if not name:
        frappe.throw(
            _("This oral activity is not part of the section's grading."),
            frappe.DoesNotExistError,
        )
    return name


def _people(rows):
    return [
        {
            "student": s,
            "name": frappe.db.get_value("Student", s, "student_name"),
        }
        for _u, s in rows
    ]


@frappe.whitelist()
def my_state(course, activity):
    """For the student opening the activity: what to record, with whom, and
    what has been recorded or submitted. An activity that is in a lesson but
    not yet in the section's grading cannot be recorded: there is nothing for
    the recording to belong to."""
    if not gradeable(course, activity):
        return {"gradeable": False}
    scac = _scac_for(course, activity)
    user = frappe.session.user
    ctx = resolve(scac, user)
    student = ctx["participants"][0][1] if ctx["participants"] else None
    if not student:
        frappe.throw(_("You are not enrolled in this section."), frappe.PermissionError)
    act = _activity(activity)
    rec = _my_recording(scac, student)
    submission = frappe.db.get_value(
        SUBMISSION,
        {"course_assess": scac, "student": student},
        ["name", "status", "grade", "comments", "submitted_on", "late", "recording"],
        as_dict=True,
    )
    if submission and submission.status != "Graded":
        submission.grade = submission.comments = None
    steps = [s for s in ctx["steps"] if s in oral.available_steps()]
    return {
        "gradeable": True,
        "scac": scac,
        "title": act.title,
        "mode": act.mode,
        "prompt": act.prompt,
        "allow_upload": ctx["allow_upload"],
        "max_seconds": min(
            ctx["max_seconds"] or oral.max_seconds(), oral.max_seconds()
        ),
        "may_record": ctx["may_record"],
        "choosable": _people(ctx["choosable"]),
        "recording": (submission and submission.recording) or (rec and rec.name),
        "submission": submission,
        "notice": {
            "steps": [_(oral.STEP_LABELS[s]) for s in steps],
            "retention_days": cint(
                frappe.db.get_single_value(
                    "Seminary Settings", "oral_audio_retention_days"
                )
                or 365
            ),
        },
    }


@frappe.whitelist(methods=["POST"])
def submit(recording):
    """Hand in a finished recording: one submission for each student on it."""
    doc = frappe.get_doc("Oral Recording", recording)
    if doc.reference_doctype != SCAC:
        frappe.throw(_("This recording is not for an oral activity."))
    people = _students_on(doc.name)
    if all(p.user != frappe.session.user for p in people):
        frappe.throw(_("This is not your recording."), frappe.PermissionError)
    if doc.status == "Recording":
        frappe.throw(_("The recording is not finished yet."))
    if not doc.audio:
        frappe.throw(_("The recording has no audio."))
    if frappe.db.exists(SUBMISSION, {"recording": doc.name}):
        frappe.throw(_("This recording has already been submitted."))
    row = _row(doc.reference_name)
    done = _submitted(row.name)
    at = now_datetime()
    names = []
    for p in people:
        if p.student in done:
            continue
        dates = deadlines.effective(row.name, p.student)
        if dates:
            deadlines.assert_open(dates, at)
        sub = frappe.get_doc(
            {
                "doctype": SUBMISSION,
                "oral_activity": row.oral,
                "course": row.parent,
                "course_assess": row.name,
                "member": p.user,
                "student": p.student,
                "recording": doc.name,
                "submitted_on": at,
                "late": deadlines.seconds_late(dates, at) if dates else 0,
            }
        )
        sub.insert(ignore_permissions=True)
        names.append(sub.name)
    return {"submissions": names}


@frappe.whitelist()
def section_summary(course, activity):
    """The staff's roster for one activity on a section: who submitted, with
    which recording and in which group."""
    from seminary.seminary.guards import require_course_staff, require_grader

    require_grader()
    require_course_staff(course)
    scac = _scac_for(course, activity)
    act = _activity(activity)
    groups = _section_groups(course) if act.mode == "Conversation" else {}
    group_of = {s: g for g, members in groups.items() for s in members}
    group_names = {
        g: frappe.db.get_value("Student Group", g, "group_name") for g in groups
    }
    subs = {
        s.student: s
        for s in frappe.get_all(
            SUBMISSION,
            filters={"course_assess": scac},
            fields=[
                "name",
                "student",
                "status",
                "grade",
                "submitted_on",
                "late",
                "recording",
            ],
        )
    }
    out = []
    for _user, student, name in _roster(course):
        s = subs.get(student)
        out.append(
            {
                "student": student,
                "student_name": name,
                "group": group_names.get(group_of.get(student)),
                "submission": s.name if s else None,
                "status": s.status if s else None,
                "grade": s.grade if s else None,
                "submitted_on": s.submitted_on if s else None,
                "late": s.late if s else 0,
                "recording": s.recording if s else None,
            }
        )
    return {"scac": scac, "title": act.title, "mode": act.mode, "students": out}


@frappe.whitelist()
def get_submission(submission):
    """One submission for its grading page."""
    from seminary.seminary.guards import require_course_staff, require_grader

    require_grader()
    doc = frappe.get_doc(SUBMISSION, submission)
    require_course_staff(doc.course)
    act = _activity(doc.oral_activity)
    others = frappe.get_all(
        SUBMISSION,
        filters={"recording": doc.recording, "name": ["!=", doc.name]},
        fields=["name", "member_name", "status"],
    )
    return {
        "name": doc.name,
        "student": doc.student,
        "member_name": doc.member_name,
        "course": doc.course,
        "course_assess": doc.course_assess,
        "oral_activity": doc.oral_activity,
        "title": act.title,
        "mode": act.mode,
        "prompt": act.prompt,
        "rubric": act.rubric,
        "recording": doc.recording,
        "status": doc.status,
        "grade": doc.grade,
        "comments": doc.comments,
        "submitted_on": doc.submitted_on,
        "late": doc.late,
        "group_submissions": others,
    }


@frappe.whitelist(methods=["POST"])
def save_grade(submission, grade, comments=None):
    """Grade one student's submission. Talk time is never a grade (100b §7):
    nothing here reads it."""
    from seminary.seminary.guards import require_course_staff, require_grader

    require_grader()
    doc = frappe.get_doc(SUBMISSION, submission)
    require_course_staff(doc.course)
    doc.grade = float(grade)
    doc.status = "Graded"
    if comments is not None:
        doc.comments = comments
    doc.save(ignore_permissions=True)
    return {"status": doc.status, "grade": doc.grade, "percentage": doc.percentage}


@frappe.whitelist()
def gradeable(course, activity):
    return bool(
        frappe.db.exists(
            SCAC, {"parent": course, "parenttype": "Course Schedule", "oral": activity}
        )
    )
