"""Due dates, cut-offs and late deductions (decisions/082).

One place answers "when is this due for this student, is it still open, and
how much does lateness cost". Everything here reads live rows:

* a student's dates are the Student Due Date Override's where it has one and
  the assessment row's otherwise (section 2);
* the cut-off refuses student-authored submissions on the server (section 3);
* the deduction is worked out from the submission time and the effective due
  date each time a grade card is written, never stored as policy (section 4),
  so moving a date re-prices the cards that are not yet sent.

Scores on the submissions and cards are percentages (0-100), so a deduction
is percentage points of the maximum score.
"""

import math

import frappe
from frappe import _
from frappe.utils import cint, flt, format_datetime, get_datetime, now_datetime

# A timed attempt the client closes at the cut-off still has to reach the
# server; this much lateness on the wire is not a refusal.
CUTOFF_SLACK_SECONDS = 120

SUBMISSION_DOCTYPES = (
    "Quiz Submission",
    "Exam Submission",
    "Assignment Submission",
    "Discussion Submission",
)

POLICY_FIELDS = (
    "late_policy_enabled",
    "late_deduction",
    "late_interval",
    "late_grace_minutes",
    "late_floor",
    "missing_reply_deduction",
)

ROW_DATE_FIELDS = ("due_date", "cutoff_date", "replies_due_date", "late_policy_exempt")

_ROW_FIELDS = [
    "name",
    "parent",
    "title",
    "type",
    "quiz",
    "exam",
    "assignment",
    "discussion",
    "extracredit_scac",
    *ROW_DATE_FIELDS,
]

_ACTIVITY_FIELD = {
    "quiz": "quiz",
    "exam": "exam",
    "assignment": "assignment",
    "discussion": "discussion",
}


# ------------------------------------------------------------------ lookups


def _row(course_assess):
    if not course_assess:
        return None
    return frappe.db.get_value(
        "Scheduled Course Assess Criteria", course_assess, _ROW_FIELDS, as_dict=True
    )


def row_for_activity(course_schedule, activity_type, activity):
    """The assessment row that puts this activity in this section, or None."""
    field = _ACTIVITY_FIELD.get((activity_type or "").strip().lower())
    if not (course_schedule and field and activity):
        return None
    name = frappe.db.get_value(
        "Scheduled Course Assess Criteria",
        {"parent": course_schedule, field: activity},
        "name",
    )
    return _row(name)


def get_override(course_assess, student):
    if not (course_assess and student):
        return None
    return frappe.db.get_value(
        "Student Due Date Override",
        {"course_assess": course_assess, "student": student},
        [
            "name",
            "due_date",
            "cutoff_date",
            "replies_due_date",
            "extra_minutes",
            "extra_attempts",
            "reason",
        ],
        as_dict=True,
    )


def discussion_has_two_dates(row):
    """A discussion whose activity requires a post before replies and at least
    one reply, with a replies due date set (section 5)."""
    if not row or not row.get("discussion") or not row.get("replies_due_date"):
        return False
    return _discussion_requires_replies(row.discussion)


def effective(course_assess, student, row=None):
    """The dates that apply to this student on this assessment."""
    row = row or _row(course_assess)
    if not row:
        return None
    ov = get_override(row.name, student) or frappe._dict()
    two_dates = discussion_has_two_dates(row)
    return frappe._dict(
        course_assess=row.name,
        course_schedule=row.parent,
        title=row.title,
        due_date=ov.due_date or row.due_date,
        cutoff_date=ov.cutoff_date or row.cutoff_date,
        replies_due_date=(
            (ov.replies_due_date or row.replies_due_date) if two_dates else None
        ),
        extra_minutes=cint(ov.extra_minutes),
        extra_attempts=cint(ov.extra_attempts),
        override=ov.name,
        late_policy_exempt=cint(row.late_policy_exempt),
    )


def is_closed(dates, at=None, slack=0):
    if not dates or not dates.cutoff_date:
        return False
    at = get_datetime(at) if at else now_datetime()
    return (at - get_datetime(dates.cutoff_date)).total_seconds() > slack


def assert_open(dates, at=None, slack=CUTOFF_SLACK_SECONDS):
    """Refuse work after the student's cut-off, saying why and what to do."""
    if is_closed(dates, at=at, slack=slack):
        frappe.throw(
            _(
                "{0} closed on {1}, so it no longer accepts submissions. If you "
                "need more time, ask your instructor for an extension."
            ).format(
                dates.title or _("This assessment"),
                format_datetime(dates.cutoff_date),
            ),
            title=_("Submissions closed"),
        )


# ------------------------------------------------------------------ policy


def policy(course_schedule):
    """The section's late policy, or None when no deduction can apply: turned
    off, a non-points scale, or a competency-based section."""
    if not course_schedule:
        return None
    cs = frappe.db.get_value(
        "Course Schedule",
        course_schedule,
        ["gradesc_cs", *POLICY_FIELDS],
        as_dict=True,
    )
    if not cs or not cs.late_policy_enabled:
        return None
    if not is_points_scale(cs.gradesc_cs):
        return None
    from seminary.seminary import cbe

    if cbe.framework_for(course_schedule):
        return None
    return cs


def is_points_scale(grading_scale):
    return bool(grading_scale) and (
        frappe.db.get_value("Grading Scale", grading_scale, "grscale_type") == "Points"
    )


def interval_deduction(pol, due, submitted_at):
    """Percentage points lost for handing in at `submitted_at` against `due`.
    The grace period only decides whether the work is late; once it is, every
    started day or hour counted from the due date costs one step."""
    if not (pol and due and submitted_at):
        return 0.0
    late = (get_datetime(submitted_at) - get_datetime(due)).total_seconds()
    if late <= cint(pol.late_grace_minutes) * 60:
        return 0.0
    step = 3600 if pol.late_interval == "Hour" else 86400
    return math.ceil(late / step) * flt(pol.late_deduction)


def submitted_at(doc):
    """When the student turned the work in, per submission doctype."""
    if doc.doctype == "Exam Submission":
        if doc.get("status") == "Not Submitted":
            return None
        return doc.get("submission_date") or doc.get("creation")
    if doc.doctype == "Assignment Submission":
        return doc.get("submitted_on") or doc.get("creation")
    return doc.get("creation")


def seconds_late(dates, at):
    if not (dates and dates.due_date and at):
        return 0
    return max(
        0, int((get_datetime(at) - get_datetime(dates.due_date)).total_seconds())
    )


def _student_user(student):
    return frappe.db.get_value("Student", student, "user")


def counted_replies(row, student, until=None):
    """Distinct classmates' posts this student replied to, by `until` if given."""
    user = _student_user(student)
    if not user:
        return 0
    params = {"cs": row.parent, "disc": row.discussion, "user": user}
    until_clause = ""
    if until:
        until_clause = "AND r.reply_dt <= %(until)s"
        params["until"] = get_datetime(until)
    return cint(
        frappe.db.sql(
            f"""
            SELECT COUNT(DISTINCT r.parent)
            FROM `tabDiscussion Submission Replies` r
            JOIN `tabDiscussion Submission` s ON s.name = r.parent
            WHERE s.coursesc = %(cs)s AND s.disc_activity = %(disc)s
              AND r.member = %(user)s AND s.member <> r.member
              {until_clause}
            """,  # nosec B608 -- the clause is a constant; values are bound
            params,
        )[0][0]
    )


def computed_deduction(doc, row=None, pol=None):
    """The deduction the policy gives this submission, before any change the
    instructor made. 0 when no policy applies."""
    row = row or _row(doc.get("course_assess"))
    if not row or cint(row.extracredit_scac) or cint(row.late_policy_exempt):
        return 0.0
    pol = pol if pol is not None else policy(row.parent)
    if not pol:
        return 0.0
    dates = effective(row.name, doc.get("student"), row=row)
    total = interval_deduction(pol, dates.due_date, submitted_at(doc))
    if dates.replies_due_date:
        required = cint(
            frappe.db.get_value(
                "Discussion Activity", row.discussion, "min_replies_required"
            )
        )
        grace = cint(pol.late_grace_minutes) * 60
        until = get_datetime(dates.replies_due_date)
        if grace:
            from datetime import timedelta

            until = until + timedelta(seconds=grace)
        missing = max(0, required - counted_replies(row, doc.get("student"), until))
        total += missing * flt(pol.missing_reply_deduction)
    return total


# ------------------------------------------------------------------ grade cards


def apply_to_card(card, doc):
    """Set the card's score from the submission's raw percentage, less the
    late deduction. Called by quizresult_to_card before it saves the card."""
    raw = doc.get("percentage")
    if raw in (None, "") or card.extracredit_card:
        card.late_base_card = 0
        card.late_deduction_card = 0
        return
    raw = flt(raw)
    if cint(card.late_adjusted_card):
        deduction = flt(card.late_adjusted_deduction)
    else:
        deduction = computed_deduction(doc)
    row = _row(doc.get("course_assess"))
    pol = policy(row.parent) if row else None
    floor = flt(pol.late_floor) if pol else 0.0
    score = raw - deduction
    if deduction and score < floor:
        score = max(min(raw, floor), score)
    score = max(score, 0.0)
    card.late_base_card = raw
    card.late_deduction_card = flt(raw - score, 2)
    card.rawscore_card = flt(score, 2)


def latest_submission(course_assess, student):
    """The submission a card reflects: the most recent one for this student."""
    row = _row(course_assess)
    if not row:
        return None
    doctype = {
        "Quiz": "Quiz Submission",
        "Exam": "Exam Submission",
        "Assignment": "Assignment Submission",
        "Discussion": "Discussion Submission",
    }.get(row.type)
    if not doctype:
        return None
    name = frappe.db.get_value(
        doctype,
        {"course_assess": course_assess, "student": student},
        "name",
        order_by="creation desc",
    )
    return frappe.get_doc(doctype, name) if name else None


def _is_graded(doc):
    if doc.doctype == "Quiz Submission":
        return True
    return doc.get("status") == "Graded" and doc.get("percentage") not in (None, "")


def refresh(course_assess, students=None):
    """Re-price the cards of one assessment after a date, policy or override
    changed. Skips sent grades (the roster is finalized), ungraded work, and a
    cell the instructor typed over in the gradebook."""
    if frappe.flags.in_install or frappe.flags.in_migrate:
        return
    filters = {"assessment_criteria": course_assess}
    if students:
        filters["student_card"] = ["in", list(students)]
    cards = frappe.get_all(
        "Course Assess Results Detail",
        filters=filters,
        fields=[
            "name",
            "parent",
            "student_card",
            "rawscore_card",
            "late_base_card",
            "late_deduction_card",
            "extracredit_card",
        ],
    )
    if not cards:
        return
    from seminary.seminary.api import quizresult_to_card

    active = set(
        frappe.get_all(
            "Scheduled Course Roster",
            filters={"name": ["in", list({c.parent for c in cards})], "active": 1},
            pluck="name",
        )
    )
    for card in cards:
        if card.parent not in active or card.extracredit_card:
            continue
        sub = latest_submission(course_assess, card.student_card)
        if not sub or not _is_graded(sub):
            continue
        written = flt(card.late_base_card) - flt(card.late_deduction_card)
        current = flt(card.rawscore_card)
        if abs(current - written) > 0.01 and abs(current - flt(sub.percentage)) > 0.01:
            continue
        quizresult_to_card(sub, None)


def refresh_section(course_schedule):
    for name in frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": course_schedule, "parenttype": "Course Schedule"},
        pluck="name",
    ):
        refresh(name)


# ------------------------------------------------------------------ doc events


def _student_authored(doc):
    """True when the student is saving their own work (not a grader)."""
    from seminary.seminary.guards import course_of, is_course_staff

    if frappe.flags.in_install or frappe.flags.in_migrate:
        return False
    user = frappe.session.user
    if not doc.get("member") or doc.member != user:
        return False
    return not is_course_staff(course_of(doc), include_registrar=True)


_CONTENT_FIELDS = {
    "Assignment Submission": ("answer", "assignment_attachment"),
    "Discussion Submission": ("original_post", "original_attachment"),
}


def _is_turn_in(doc):
    """Is this save the student handing work in (as opposed to, say, a
    notification flag being written)?"""
    if doc.is_new():
        return True
    if doc.doctype == "Exam Submission":
        before = doc.get_doc_before_save()
        return bool(before) and before.status == "Not Submitted"
    return any(doc.has_value_changed(f) for f in _CONTENT_FIELDS.get(doc.doctype, ()))


def guard_submission(doc, method=None):
    """validate hook on the four submission doctypes: refuse work after the
    student's cut-off, and record when (and how late) it was turned in."""
    if doc.doctype == "Quiz Submission" and doc.get("standalone"):
        return
    if not _student_authored(doc) or not _is_turn_in(doc):
        return
    dates = effective(doc.get("course_assess"), doc.get("student"))
    if not dates:
        return
    assert_open(dates)
    at = now_datetime()
    if doc.doctype == "Assignment Submission":
        doc.submitted_on = at
        doc.late = seconds_late(dates, at)
    elif doc.doctype == "Discussion Submission" and doc.is_new():
        doc.late = seconds_late(dates, at)


def assert_reply_open(submission):
    """A reply counts for the replier's own grade, so their cut-off governs."""
    from seminary.seminary.guards import current_student

    course_assess = frappe.db.get_value(
        "Discussion Submission", submission, "course_assess"
    )
    student = current_student(frappe.session.user)
    if not (course_assess and student):
        return None
    dates = effective(course_assess, student)
    assert_open(dates)
    return course_assess, student


def on_row_update(doc, method=None):
    """Scheduled Course Assess Criteria on_update: a moved date re-prices."""
    if any(doc.has_value_changed(f) for f in ROW_DATE_FIELDS):
        refresh(doc.name)


def on_section_update(doc):
    """Called from Course Schedule.on_update when the late policy changed."""
    if any(doc.has_value_changed(f) for f in (*POLICY_FIELDS, "gradesc_cs")):
        refresh_section(doc.name)


def extra_attempts(course_schedule, quiz, student):
    row = row_for_activity(course_schedule, "quiz", quiz)
    if not row:
        return 0
    ov = get_override(row.name, student)
    return cint(ov.extra_attempts) if ov else 0


# ------------------------------------------------------------------ endpoints
#
# Staff endpoints use the gradebook's gate (course staff, registrar included);
# the student endpoint answers only for the session user.


def _require_staff(course_schedule):
    from seminary.seminary.guards import require_course_staff

    require_course_staff(course_schedule, include_registrar=True)


def _parse(value):
    return frappe.parse_json(value) if isinstance(value, str) else (value or {})


@frappe.whitelist()
def get_deadline_settings(course):
    """Everything the assessment page needs: the late policy, each row's
    extra dates, the roster and the overrides."""
    _require_staff(course)
    cs = frappe.db.get_value(
        "Course Schedule", course, ["gradesc_cs", *POLICY_FIELDS], as_dict=True
    )
    from seminary.seminary import cbe

    rows = frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": course, "parenttype": "Course Schedule"},
        fields=_ROW_FIELDS,
        order_by="idx asc",
    )
    for row in rows:
        row["two_dates_possible"] = bool(row.discussion) and (
            _discussion_requires_replies(row.discussion)
        )
    overrides = frappe.get_all(
        "Student Due Date Override",
        filters={"course_schedule": course},
        fields=[
            "name",
            "course_assess",
            "student",
            "student_name",
            "due_date",
            "cutoff_date",
            "replies_due_date",
            "extra_minutes",
            "extra_attempts",
            "reason",
            "source",
        ],
        order_by="student_name asc",
    )
    roster = frappe.get_all(
        "Scheduled Course Roster",
        filters={"course_sc": course},
        fields=["student", "stuname_roster as student_name", "active"],
        order_by="stuname_roster asc",
    )
    return {
        "policy": {f: cs.get(f) for f in POLICY_FIELDS},
        "policy_available": is_points_scale(cs.gradesc_cs)
        and not cbe.framework_for(course),
        "rows": rows,
        "overrides": overrides,
        "roster": roster,
    }


def _discussion_requires_replies(discussion):
    activity = frappe.db.get_value(
        "Discussion Activity",
        discussion,
        ["post_before", "min_replies_required"],
        as_dict=True,
    )
    return bool(
        activity and activity.post_before and cint(activity.min_replies_required) > 0
    )


@frappe.whitelist()
def save_late_policy(course, policy):
    """Write the section's late policy. The Course Schedule controller refuses
    it on a scale it cannot apply to, and its on_update re-prices the cards."""
    from seminary.seminary.guards import require_outline_editor

    require_outline_editor()
    _require_staff(course)
    policy = _parse(policy)
    doc = frappe.get_doc("Course Schedule", course)
    for field in POLICY_FIELDS:
        if field in policy:
            doc.set(field, policy.get(field))
    doc.save(ignore_permissions=True)
    return {f: doc.get(f) for f in POLICY_FIELDS}


@frappe.whitelist()
def save_override(data):
    """Create or edit one student's override. The doctype's validate checks
    the section, the roster, the dates and the caller."""
    data = _parse(data)
    fields = (
        "due_date",
        "cutoff_date",
        "replies_due_date",
        "extra_minutes",
        "extra_attempts",
        "reason",
    )
    course_assess = data.get("course_assess")
    course = frappe.db.get_value(
        "Scheduled Course Assess Criteria", course_assess, "parent"
    )
    _require_staff(course)
    if data.get("name"):
        doc = frappe.get_doc("Student Due Date Override", data["name"])
        if doc.course_assess != course_assess:
            frappe.throw(_("This override belongs to another assessment."))
    else:
        doc = frappe.new_doc("Student Due Date Override")
        doc.course_assess = course_assess
        doc.course_schedule = course
        doc.student = data.get("student")
        doc.source = (
            data.get("source")
            if data.get("source") in ("Excused absence",)
            else ("Registrar" if _is_registrar_only(course) else "Instructor")
        )
    for f in fields:
        if f in data:
            doc.set(f, data.get(f) or None)
    doc.save(ignore_permissions=True)
    return doc.as_dict()


def _is_registrar_only(course):
    from seminary.seminary.guards import is_course_staff

    return not is_course_staff(course) and "Registrar" in frappe.get_roles()


@frappe.whitelist()
def delete_override(name):
    course = frappe.db.get_value("Student Due Date Override", name, "course_schedule")
    _require_staff(course)
    if not course:
        frappe.throw(_("That override no longer exists."))
    frappe.delete_doc("Student Due Date Override", name, ignore_permissions=True)
    return {"deleted": name}


@frappe.whitelist()
def set_late_adjustment(card, deduction=None, reason=None):
    """Waive (0) or change the late deduction on one student's grade, or pass
    no deduction to go back to the policy. A reason is required to change it."""
    row = frappe.db.get_value(
        "Course Assess Results Detail",
        card,
        ["name", "parent", "assessment_criteria", "student_card"],
        as_dict=True,
    )
    roster = (
        frappe.db.get_value(
            "Scheduled Course Roster", row.parent, ["course_sc", "active"], as_dict=True
        )
        if row
        else None
    )
    _require_staff(roster.course_sc if roster else None)
    if not roster:
        frappe.throw(_("That grade no longer exists."))
    if not roster.active:
        frappe.throw(
            _(
                "Grades for this student were already sent, so the deduction can no longer change."
            )
        )
    sub = latest_submission(row.assessment_criteria, row.student_card)
    if not sub or not _is_graded(sub):
        frappe.throw(
            _(
                "There is no graded submission to take a deduction from yet. Grade it first."
            )
        )
    doc = frappe.get_doc("Course Assess Results Detail", card)
    if deduction in (None, ""):
        doc.late_adjusted_card = 0
        doc.late_adjusted_deduction = 0
        doc.late_adjusted_reason = None
    else:
        if not (reason or "").strip():
            frappe.throw(_("Give a reason for changing the deduction."))
        value = flt(deduction)
        if not 0 <= value <= 100:
            frappe.throw(_("The deduction must be between 0 and 100."))
        doc.late_adjusted_card = 1
        doc.late_adjusted_deduction = value
        doc.late_adjusted_reason = reason.strip()
    apply_to_card(doc, sub)
    doc.save(ignore_permissions=True)
    return {
        "rawscore_card": doc.rawscore_card,
        "late_base_card": doc.late_base_card,
        "late_deduction_card": doc.late_deduction_card,
        "late_adjusted_card": doc.late_adjusted_card,
        "late_adjusted_reason": doc.late_adjusted_reason,
    }


@frappe.whitelist()
def get_student_dates(course, student):
    """One student's dates on every assessment, for the gradebook cell menu."""
    _require_staff(course)
    out = []
    for row in frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": course, "parenttype": "Course Schedule"},
        fields=_ROW_FIELDS,
    ):
        dates = effective(row.name, student, row=row)
        out.append(dates)
    return out


@frappe.whitelist()
def excused_due(course, date, students):
    """Assessments due on `date` for students just marked Excused, so the
    attendance page can offer each one an override (decisions/082 section 2)."""
    _require_staff(course)
    students = _parse(students) or []
    if not students or not date:
        return []
    rows = frappe.db.sql(
        """
        SELECT name, title, due_date
        FROM `tabScheduled Course Assess Criteria`
        WHERE parent = %s AND parenttype = 'Course Schedule'
          AND DATE(due_date) = %s
        ORDER BY due_date
        """,
        (course, frappe.utils.getdate(date)),
        as_dict=True,
    )
    if not rows:
        return []
    names = dict(
        frappe.get_all(
            "Student",
            filters={"name": ["in", students]},
            fields=["name", "student_name"],
            as_list=True,
        )
    )
    out = []
    for student in students:
        for row in rows:
            if get_override(row.name, student):
                continue
            out.append(
                {
                    "student": student,
                    "student_name": names.get(student, student),
                    "course_assess": row.name,
                    "title": row.title,
                    "due_date": row.due_date,
                }
            )
    return out


@frappe.whitelist()
def get_my_dates(course, activity_type=None, activity=None):
    """The session student's dates: for one activity when given, else every
    assessment of the section. Staff get the row's own dates."""
    from seminary.seminary.guards import current_student, require_enrolled

    require_enrolled(course)
    student = current_student(frappe.session.user)
    if activity_type and activity:
        row = row_for_activity(course, activity_type, activity)
        return _for_student(row, student) if row else None
    return [
        _for_student(row, student)
        for row in frappe.get_all(
            "Scheduled Course Assess Criteria",
            filters={"parent": course, "parenttype": "Course Schedule"},
            fields=_ROW_FIELDS,
        )
    ]


def _for_student(row, student):
    dates = effective(row.name, student, row=row)
    dates["closed"] = is_closed(dates)
    return dates
