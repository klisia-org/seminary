# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Oral defense of a submitted paper (decisions/100c).

On submission of a text assignment whose activity asks for a defense, the
paper's text is extracted and the ``questions`` step writes the questions, or
the instructor writes them by hand. The questions are Oral Defense Question
rows, a doctype students cannot read: a student sees a question only when it is
asked (§2).

The defense opens when its questions are ready, or when the instructor releases
them if the activity says ``defense_review``; it is due ``defense_window``
later (§4). It runs one question at a time under the exam conditions of 100a §2:
reading time, a timed recording, one take. With ``defense_follow_up``, the
answer is transcribed at once and the ``follow_up`` step may add one question
on it; the student waits at most ``FOLLOW_UP_BUDGET`` seconds (§3).

A student whose override says ``written_instead`` (100 §9) answers in writing.

The ``questions`` and ``follow_up`` providers are called directly and return
their result: ``(None, step, payload) -> dict``.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now_datetime, strip_html

from seminary.seminary import oral
from seminary.seminary.guards import GRADE

QUESTION = "Oral Defense Question"
SUBMISSION = "Assignment Submission"
TEXT_TYPES = ("PDF", "Document", "Text")
PREPARE_S = 20
FOLLOW_UP_BUDGET = 20


# ------------------------------------------------------------------ lookups


def _activity(name):
	return frappe.db.get_value(
		"Assignment Activity",
		name,
		[
			"name",
			"title",
			"type",
			"question",
			"rubric",
			"oral_defense",
			"defense_questions",
			"defense_answer_s",
			"defense_follow_up",
			"defense_window",
			"defense_review",
			"defense_steps",
		],
		as_dict=True,
	)


def defended(activity) -> bool:
	return bool(activity and cint(activity.oral_defense) and activity.type in TEXT_TYPES)


def _sub(name):
	return frappe.db.get_value(
		SUBMISSION,
		name,
		[
			"name",
			"assignment",
			"member",
			"student",
			"course",
			"course_assess",
			"late",
			"defense_status",
			"defense_opened_on",
			"defense_due",
			"defense_started_on",
			"defense_done_on",
		],
		as_dict=True,
	)


def _questions(submission, states=None):
	filters = {"submission": submission}
	if states:
		filters["state"] = ["in", states]
	return frappe.get_all(
		QUESTION,
		filters=filters,
		fields=[
			"name",
			"position",
			"follow_up_of",
			"source",
			"state",
			"follow_up_state",
			"question",
			"passage",
			"good_answer",
			"recording",
			"answer_text",
			"asked_on",
			"answered_on",
		],
		order_by="position asc, creation asc",
	)


def _written_instead(sub):
	from seminary.seminary.deadlines import get_override

	ov = get_override(sub.course_assess, sub.student) if sub.course_assess else None
	return bool(ov and cint(ov.written_instead))


def _steps(activity):
	try:
		steps = json.loads(activity.defense_steps or "[]")
	except ValueError:
		steps = []
	return [s for s in steps if s in oral.PIPELINE]


def defense_criteria(activity):
	"""The rubric criteria judged from the defense (§5), or all of them when
	none is flagged."""
	from seminary.seminary.oral_activities import rubric_criteria

	criteria = rubric_criteria(activity.rubric)
	flagged = set(
		frappe.get_all(
			"Rubric Criterion",
			filters={"parent": activity.rubric, "from_defense": 1},
			pluck="criterion_code",
		)
		if activity.rubric
		else []
	)
	return [c for c in criteria if c["criterion_code"] in flagged] or criteria


def _paper(submission):
	from seminary.seminary.plagiarism.service import cache_submission_text

	return cache_submission_text(submission) or ""


def _names(student):
	row = frappe.db.get_value(
		"Student",
		student,
		["first_name", "middle_name", "last_name", "student_name"],
		as_dict=True,
	)
	names = set()
	for value in (row or {}).values():
		for part in [value, *(value or "").split()]:
			if part and len(part) >= 2:
				names.add(part)
	return sorted(names)


def _provider(step):
	if step not in oral.allowed_steps():
		return None
	return oral.provided_steps().get(step)


# ------------------------------------------------------------- on submission


def on_submission_update(doc, method=None):
	"""Assignment Submission on_update: a turned-in paper of a defended
	activity gets its questions written, unless its defense has started."""
	if doc.flags.from_defense:
		return
	activity = _activity(doc.assignment)
	if not defended(activity):
		return
	if doc.get("defense_status") in ("In Progress", "Done"):
		return
	if frappe.session.user != doc.member:
		return
	before = doc.get_doc_before_save()
	changed = (
		not before or before.answer != doc.answer or before.assignment_attachment != doc.assignment_attachment
	)
	if not changed and doc.get("defense_status"):
		return
	# A paper changed before its defense started: suggested questions are
	# written again; the instructor's own stay.
	for name in frappe.get_all(
		QUESTION,
		filters={"submission": doc.name, "source": "Suggested", "state": "Pending"},
		pluck="name",
	):
		frappe.delete_doc(QUESTION, name, ignore_permissions=True, force=True)
	frappe.db.set_value(
		SUBMISSION,
		doc.name,
		{
			"defense_status": "Waiting for Questions",
			"defense_opened_on": None,
			"defense_due": None,
		},
		update_modified=False,
	)
	frappe.enqueue(
		"seminary.seminary.oral_defense.prepare",
		submission=doc.name,
		queue="long",
		enqueue_after_commit=True,
		now=bool(frappe.flags.in_test),
	)


def questions_payload(submission):
	sub = _sub(submission)
	activity = _activity(sub.assignment)
	return {
		"submission": submission,
		"count": max(1, cint(activity.defense_questions) or 3),
		"prompt": activity.question,
		"text": _paper(submission),
		"criteria": defense_criteria(activity),
		"redact": _names(sub.student),
	}


def prepare(submission):
	"""Write the questions with the ``questions`` step, then open the defense
	if it may open. Without a step, the instructor writes them."""
	sub = _sub(submission)
	if not sub or sub.defense_status not in ("Waiting for Questions",):
		return
	path = _provider("questions")
	if path and not frappe.db.exists(QUESTION, {"submission": submission}):
		try:
			result = frappe.get_attr(path)(None, "questions", questions_payload(submission))
		except Exception:
			frappe.clear_last_message()
			frappe.log_error(title=f"Oral defense questions for {submission} failed")
			result = None
		for i, q in enumerate((result or {}).get("questions") or []):
			if not isinstance(q, dict) or not str(q.get("question") or "").strip():
				continue
			frappe.get_doc(
				{
					"doctype": QUESTION,
					"submission": submission,
					"course": sub.course,
					"position": (i + 1) * 10,
					"source": "Suggested",
					"question": str(q["question"])[:2000],
					"passage": str(q.get("passage") or "")[:2000] or None,
					"good_answer": str(q.get("good_answer") or "")[:2000] or None,
				}
			).insert(ignore_permissions=True)
	open_if_ready(submission)


def open_if_ready(submission, released=False):
	"""Questions ready: open the defense, or wait for the instructor (§4)."""
	sub = _sub(submission)
	if sub.defense_status not in ("Waiting for Questions", "Waiting for Release"):
		return sub.defense_status
	if not frappe.db.exists(QUESTION, {"submission": submission, "follow_up_of": ["is", "not set"]}):
		return sub.defense_status
	activity = _activity(sub.assignment)
	if cint(activity.defense_review) and not released:
		status = "Waiting for Release"
		frappe.db.set_value(SUBMISSION, submission, "defense_status", status, update_modified=False)
		return status
	now = now_datetime()
	window = cint(activity.defense_window) or 3 * 86400
	frappe.db.set_value(
		SUBMISSION,
		submission,
		{
			"defense_status": "Open",
			"defense_opened_on": now,
			"defense_due": add_to_date(now, seconds=window),
		},
		update_modified=False,
	)
	_tell_student(sub, activity)
	return "Open"


def _tell_student(sub, activity):
	"""The student is told the defense is open (§4), in the portal's bell."""
	try:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": sub.member,
				"type": "Alert",
				"document_type": SUBMISSION,
				"document_name": sub.name,
				"subject": _("Your oral defense of {0} is open.").format(activity.title),
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title=f"Oral defense notice for {sub.name} failed")
	frappe.publish_realtime("oral_defense_open", {"submission": sub.name}, user=sub.member)


# --------------------------------------------------------------- the resolver


def resolve(row_name, user):
	row = frappe.db.get_value(
		QUESTION,
		row_name,
		[
			"name",
			"submission",
			"state",
			"recording",
			"question",
			"follow_up_of",
			"course",
		],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Question not found."), frappe.PermissionError)
	sub = _sub(row.submission)
	activity = _activity(sub.assignment)
	follow = bool(cint(activity.defense_follow_up) and not row.follow_up_of)
	return {
		"course_schedule": sub.course,
		"participants": [(sub.member, sub.student)],
		"may_record": bool(
			user == sub.member
			and sub.defense_status == "In Progress"
			and row.state == "Asked"
			and not row.recording
			and not _written_instead(sub)
		),
		"allow_upload": False,
		"steps": (["transcribe"] if follow else []) + _steps(activity),
		"expected_speakers": 1,
		"max_seconds": cint(activity.defense_answer_s) or 120,
		"prompt": row.question,
		"text": _paper(sub.name),
		"criteria": defense_criteria(activity),
		# A follow-up waits on this transcript: the provider polls it at once (091 §7).
		"urgent": follow,
		"on_start": "seminary.seminary.oral_defense.on_start",
		"after_step": "seminary.seminary.oral_defense.after_step",
	}


def on_start(recording):
	ref = frappe.db.get_value("Oral Recording", recording, "reference_name")
	frappe.db.set_value(QUESTION, ref, "recording", recording)


def after_step(recording, step):
	"""The answer's transcript becomes its text; then, within the budget, the
	``follow_up`` step may add one question on it (§3)."""
	if step != "transcribe":
		return
	doc = frappe.get_doc("Oral Recording", recording)
	row = frappe.get_doc(QUESTION, doc.reference_name)
	text = " ".join(s.get("text", "").strip() for s in json.loads(doc.transcript or "[]"))
	row.db_set("answer_text", text)
	if row.follow_up_of or row.follow_up_state not in (None, "", "Waiting"):
		return
	sub = _sub(row.submission)
	if not cint(_activity(sub.assignment).defense_follow_up):
		return
	# The transcript can come back before the student's page says the answer
	# is saved: the wait starts from whichever side is first.
	if not row.follow_up_state:
		row.db_set("follow_up_state", "Waiting")
	if not row.answered_on:
		row.db_set("answered_on", now_datetime())
	path = _provider("follow_up")
	if not path:
		row.db_set("follow_up_state", "None")
		return
	try:
		result = frappe.get_attr(path)(
			recording,
			"follow_up",
			{
				"question": row.question,
				"answer": text,
				"passage": row.passage,
				"text": _paper(sub.name),
				"redact": _names(sub.student),
			},
		)
	except Exception:
		frappe.clear_last_message()
		frappe.log_error(title=f"Oral defense follow-up for {row.name} failed")
		result = None
	row.reload()
	if row.follow_up_state != "Waiting":
		return  # The student moved on while the step was thinking.
	question = str((result or {}).get("question") or "").strip()
	if not question:
		row.db_set("follow_up_state", "None")
		return
	frappe.get_doc(
		{
			"doctype": QUESTION,
			"submission": row.submission,
			"course": row.course,
			"position": cint(row.position) + 1,
			"follow_up_of": row.name,
			"source": "Suggested",
			"question": question[:2000],
		}
	).insert(ignore_permissions=True)
	row.db_set("follow_up_state", "Asked")


def follow_up_payload(recording):
	"""What the ``follow_up`` step receives for one answer, for trials."""
	doc = frappe.get_doc("Oral Recording", recording)
	if doc.reference_doctype != QUESTION:
		frappe.throw(_("This recording is not an oral defense answer."))
	row = frappe.get_doc(QUESTION, doc.reference_name)
	sub = _sub(row.submission)
	return {
		"question": row.question,
		"answer": " ".join(s.get("text", "").strip() for s in json.loads(doc.transcript or "[]")),
		"passage": row.passage,
		"text": _paper(sub.name),
		"redact": _names(sub.student),
	}


# ----------------------------------------------------------------- the student


def _own(submission):
	sub = _sub(submission)
	if not sub or sub.member != frappe.session.user:
		frappe.throw(_("Submission not found."), frappe.PermissionError)
	return sub


def _public(row):
	"""What a student may see of an asked question: never the passage or the
	good answer."""
	return {
		"name": row.name,
		"question": row.question,
		"follow_up": bool(row.follow_up_of),
	}


@frappe.whitelist()
def my_defense(submission):
	sub = _own(submission)
	activity = _activity(sub.assignment)
	if not defended(activity) or not sub.defense_status:
		return {"required": False}
	rows = _questions(submission)
	asked = next((r for r in rows if r.state == "Asked"), None)
	steps = [s for s in _steps(activity) if s in oral.available_steps()]
	return {
		"required": True,
		"status": sub.defense_status,
		"opened_on": sub.defense_opened_on,
		"due": sub.defense_due,
		"done_on": sub.defense_done_on,
		"count": len([r for r in rows if not r.follow_up_of]),
		"answered": len([r for r in rows if r.state == "Answered"]),
		"current": _public(asked) if asked else None,
		"recording": asked.recording if asked else None,
		"written": _written_instead(sub),
		"prepare_s": PREPARE_S,
		"answer_s": cint(activity.defense_answer_s) or 120,
		"follow_up": bool(cint(activity.defense_follow_up)),
		"notice": {
			"steps": [_(oral.STEP_LABELS[s]) for s in steps],
			"retention_days": cint(
				frappe.db.get_single_value("Seminary Settings", "oral_audio_retention_days") or 365
			),
		},
	}


def _ask_next(sub):
	"""Ask the next pending question: a follow-up first, then the next one.
	With none left, the defense is done."""
	pending = _questions(sub.name, ["Pending"])
	if pending:
		row = pending[0]
		frappe.db.set_value(QUESTION, row.name, {"state": "Asked", "asked_on": now_datetime()})
		return {"done": False, "current": _public(row)}
	_finish(sub)
	return {"done": True, "current": None}


def _finish(sub):
	now = now_datetime()
	late = 0
	if sub.defense_due and now > get_datetime(sub.defense_due):
		late = int((now - get_datetime(sub.defense_due)).total_seconds())
	doc = frappe.get_doc(SUBMISSION, sub.name)
	doc.defense_status = "Done"
	doc.defense_done_on = now
	doc.defense_late = late
	# 082's late policy applies to the defense like any other part (§4).
	if late > cint(doc.late):
		doc.late = late
	doc.flags.from_defense = True
	doc.flags.ignore_permissions = True
	doc.save()


@frappe.whitelist(methods=["POST"])
def start(submission):
	sub = _own(submission)
	if sub.defense_status != "Open":
		frappe.throw(_("The defense is not open."))
	frappe.db.set_value(
		SUBMISSION,
		submission,
		{"defense_status": "In Progress", "defense_started_on": now_datetime()},
		update_modified=False,
	)
	sub.defense_status = "In Progress"
	return _ask_next(sub)


@frappe.whitelist(methods=["POST"])
def next_question(submission):
	"""After an answer: wait for a follow-up while the budget lasts, then move on.

	Returns ``{"wait": True}`` while a follow-up may still come."""
	sub = _own(submission)
	if sub.defense_status != "In Progress":
		frappe.throw(_("The defense is not in progress."))
	asked = _questions(submission, ["Asked"])
	if asked:
		row = asked[0]
		if not row.recording and not row.answer_text:
			frappe.throw(_("Answer the question first."))
		if row.recording and frappe.db.get_value("Oral Recording", row.recording, "status") in (
			None,
			"Recording",
		):
			frappe.throw(_("Your answer is still being saved."))
		activity = _activity(sub.assignment)
		waits = bool(cint(activity.defense_follow_up) and not row.follow_up_of and row.recording)
		values = {"state": "Answered"}
		if not row.answered_on:
			values["answered_on"] = now_datetime()
		if not row.follow_up_state:
			values["follow_up_state"] = "Waiting" if waits else "None"
		frappe.db.set_value(QUESTION, row.name, values)
	waiting = next(
		(r for r in _questions(submission, ["Answered"]) if r.follow_up_state == "Waiting"),
		None,
	)
	if waiting:
		elapsed = (now_datetime() - get_datetime(waiting.answered_on)).total_seconds()
		if elapsed < FOLLOW_UP_BUDGET:
			return {"wait": True}
		frappe.db.set_value(QUESTION, waiting.name, "follow_up_state", "Timed Out")
	return _ask_next(sub)


@frappe.whitelist(methods=["POST"])
def answer_in_writing(submission, question, answer):
	"""The written alternative (100 §9): the answer is typed, not recorded."""
	sub = _own(submission)
	if not _written_instead(sub):
		frappe.throw(_("This defense is answered aloud."), frappe.PermissionError)
	row = frappe.db.get_value(QUESTION, question, ["name", "submission", "state"], as_dict=True)
	if not row or row.submission != submission or row.state != "Asked":
		frappe.throw(_("This question is not being asked."))
	text = strip_html(answer or "").strip()
	if not text:
		frappe.throw(_("Write an answer first."))
	frappe.db.set_value(QUESTION, question, "answer_text", text[:20000])
	return next_question(submission)


# ------------------------------------------------------------------- the staff


def _staff(submission, action=None):
	"""Reads need course staff; a write names its action (decisions/105)."""
	from seminary.seminary.guards import require_course_staff, require_grader, require_section_capability

	require_grader()
	sub = _sub(submission)
	if not sub:
		frappe.throw(_("Submission not found."), frappe.DoesNotExistError)
	if action:
		require_section_capability(sub.course, action)
	else:
		require_course_staff(sub.course)
	return sub


@frappe.whitelist()
def get_defense(submission):
	sub = _staff(submission)
	activity = _activity(sub.assignment)
	return {
		"required": defended(activity) and bool(sub.defense_status),
		"status": sub.defense_status,
		"opened_on": sub.defense_opened_on,
		"due": sub.defense_due,
		"started_on": sub.defense_started_on,
		"done_on": sub.defense_done_on,
		"editable": sub.defense_status in ("Waiting for Questions", "Waiting for Release", "Open"),
		"review": bool(cint(activity.defense_review)),
		"questions": _questions(submission),
	}


@frappe.whitelist(methods=["POST"])
def save_question(
	submission: str,
	question: str,
	passage: str | None = None,
	good_answer: str | None = None,
	name: str | None = None,
):
	"""The instructor writes or edits a question before the student starts (§2)."""
	sub = _staff(submission, GRADE)
	if sub.defense_status not in (
		"Waiting for Questions",
		"Waiting for Release",
		"Open",
	):
		frappe.throw(_("The student has started the defense; its questions cannot change."))
	if not strip_html(question or "").strip():
		frappe.throw(_("Write the question."))
	if name:
		doc = frappe.get_doc(QUESTION, name)
		if doc.submission != submission or doc.follow_up_of:
			frappe.throw(_("Question not found."))
	else:
		last = frappe.db.get_value(
			QUESTION,
			{"submission": submission},
			"position",
			order_by="position desc",
		)
		doc = frappe.get_doc(
			{
				"doctype": QUESTION,
				"submission": submission,
				"course": sub.course,
				"position": cint(last) + 10,
			}
		)
	doc.question = question
	doc.passage = passage
	doc.good_answer = good_answer
	doc.source = "Instructor"
	doc.save(ignore_permissions=True)
	if sub.defense_status == "Waiting for Questions":
		open_if_ready(submission)
	return doc.name


@frappe.whitelist(methods=["POST"])
def delete_question(submission: str, name: str):
	sub = _staff(submission, GRADE)
	if sub.defense_status not in (
		"Waiting for Questions",
		"Waiting for Release",
		"Open",
	):
		frappe.throw(_("The student has started the defense; its questions cannot change."))
	doc = frappe.get_doc(QUESTION, name)
	if doc.submission != submission:
		frappe.throw(_("Question not found."))
	doc.delete(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def release(submission: str):
	"""Open a defense the activity holds for review (§4)."""
	sub = _staff(submission, GRADE)
	if sub.defense_status != "Waiting for Release":
		frappe.throw(_("This defense is not waiting for you."))
	return open_if_ready(submission, released=True)


# ----------------------------------------------------------------- permissions


def has_permission(doc, ptype=None, user=None):
	"""Staff of the section only; students never read a question (§2)."""
	from seminary.seminary.guards import _roles, is_school_role
	from seminary.seminary.student_permissions import (
		_granted_by_another_role,
		_instructor_allows,
	)

	user = user or frappe.session.user
	if is_school_role(user) or _granted_by_another_role(QUESTION, ptype, user):
		return True
	if "Instructor" in _roles(user):
		return _instructor_allows(QUESTION, doc, ptype, user, "course")
	return False


def get_permission_query_conditions(user=None):
	from seminary.seminary.guards import _roles, is_school_role
	from seminary.seminary.student_permissions import (
		_granted_by_another_role,
		_instructor_condition,
	)

	user = user or frappe.session.user
	if is_school_role(user) or _granted_by_another_role(QUESTION, "read", user):
		return ""
	if "Instructor" in _roles(user):
		cond = _instructor_condition(QUESTION, user, "course")
		return cond if cond is not None else "1=0"  # "" lets every row through
	return "1=0"
