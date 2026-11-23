# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Oral activities captured from virtual meetings (decisions/100d).

An Oral Activity whose ``capture`` is *Virtual meeting* is not recorded by
students. On a section, the instructor adds an **Oral Activity Meeting** for
each class meeting that captures part of it, with a method from the
``meeting_capture`` hook, ``{method: "dotted.path.to.Class"}``. Instances have

- ``needs_managed``: works only on meetings Seminary created (051a);
- ``rooms``: can record breakout rooms;
- ``arm(capture) -> str``: get ready before the meeting, return a reference;
- ``disarm(ref, capture)``: stand down.

``capture`` is ``{"name", "title", "course_schedule", "meeting_url",
"provider", "provider_meeting_id", "start", "end", "bot_name"}`` with
``start``/``end`` in UTC ISO 8601. When the provider has the audio it calls
``seminary.seminary.oral.meeting_recorded(name, result)`` (see
``meeting_recorded`` below), or ``meeting_failed(name, error)``.

Nothing about a participant is final until the instructor confirms the list:
bots rarely see emails and per-person files carry no identity (100d §4).
Confirming creates the submissions and puts the students on the recording.
"""

import json
import unicodedata
from datetime import UTC, datetime, timezone
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.utils import (
	cint,
	get_datetime,
	get_system_timezone,
	get_time,
	getdate,
	now_datetime,
	today,
)

from seminary.seminary.guards import GRADE

OAM = "Oral Activity Meeting"
ROW = "Course Schedule Meeting Dates"
SCAC = "Scheduled Course Assess Criteria"
SUBMISSION = "Oral Activity Submission"
HOOK = "meeting_capture"
ACTIVE = ("Scheduled", "Armed")
METHOD_LABELS = {
	"account": "The school's meeting account records it",
	"bot": "A recorder joins the meeting",
}


# ------------------------------------------------------------------ methods


def capture_methods() -> dict[str, str]:
	"""{method: dotted path} the apps provide and the school allows."""
	settings = frappe.get_cached_doc("Seminary Settings")
	out = {}
	for name, paths in dict(frappe.get_hooks(HOOK) or {}).items():
		path = paths[-1] if isinstance(paths, list) else paths
		allowed = settings.get(f"meeting_capture_{name}")
		if path and (allowed in (None, "") or cint(allowed)):
			out[name] = path
	return out


def method(name):
	path = capture_methods().get(name)
	if not path:
		frappe.throw(_("Capture method {0} is not available.").format(name))
	return frappe.get_attr(path)()


# ------------------------------------------------------------------ helpers


def _staff(course, action=None):
	"""Reads need course staff; a write names its action (decisions/105)."""
	from seminary.seminary.guards import require_course_staff, require_grader, require_section_capability

	require_grader()
	if action:
		require_section_capability(course, action)
	else:
		require_course_staff(course)


def _staff_capture(name, action=None):
	"""One capture for its section's staff. A student is refused before the
	name is even looked up."""
	from seminary.seminary.guards import require_grader

	require_grader()
	doc = frappe.get_doc(OAM, name)
	_staff(doc.course_schedule, action)
	return doc


def _scac(course, activity):
	from seminary.seminary.oral_activities import _scac_for

	return _scac_for(course, activity)


def _activity(name):
	return frappe.db.get_value("Oral Activity", name, ["name", "title", "mode", "capture"], as_dict=True)


def _row(name):
	return frappe.db.get_value(
		ROW,
		name,
		[
			"name",
			"parent",
			"cs_meetdate",
			"cs_fromtime",
			"cs_totime",
			"cs_online",
			"cs_web_meeting",
			"cs_meeting_account",
			"cs_meeting_id",
		],
		as_dict=True,
	)


def _utc(day, time):
	local = datetime.combine(getdate(day), get_time(time))
	aware = local.replace(tzinfo=ZoneInfo(get_system_timezone()))
	return aware.astimezone(UTC).isoformat()


def _capture(doc):
	"""What a method is told about one capture."""
	if doc.get("kind") == "Group":
		# A group meeting holds its own meeting (100d-a §4).
		activity = _activity(doc.oral_activity)
		title = frappe.db.get_value("Course Schedule", doc.course_schedule, "title")
		provider = (
			frappe.db.get_value("Web Meeting Account", doc.meeting_account, "provider")
			if doc.meeting_account
			else None
		)
		return {
			"name": doc.name,
			"title": f"{title or doc.course_schedule}: {activity.title}"
			+ (f" ({doc.group_label})" if doc.group_label else ""),
			"course_schedule": doc.course_schedule,
			"meeting_url": doc.link,
			"provider": provider,
			"provider_meeting_id": doc.provider_meeting_id,
			"start": _utc(doc.meeting_date, doc.from_time),
			"end": _utc(doc.meeting_date, doc.to_time),
			"bot_name": _("Seminary recorder (for assessment)"),
		}
	row = _row(doc.meeting)
	cs = frappe.db.get_value("Course Schedule", doc.course_schedule, ["title", "web_meeting"], as_dict=True)
	activity = _activity(doc.oral_activity)
	provider = (
		frappe.db.get_value("Web Meeting Account", row.cs_meeting_account, "provider")
		if row.cs_meeting_account
		else None
	)
	return {
		"name": doc.name,
		"title": f"{cs.title or doc.course_schedule}: {activity.title}",
		"course_schedule": doc.course_schedule,
		"meeting_url": row.cs_web_meeting or cs.web_meeting,
		"provider": provider,
		"provider_meeting_id": row.cs_meeting_id,
		"start": _utc(row.cs_meetdate, row.cs_fromtime),
		"end": _utc(row.cs_meetdate, row.cs_totime),
		"bot_name": _("Seminary recorder (for assessment)"),
	}


def _normal(name):
	text = unicodedata.normalize("NFKD", name or "")
	text = "".join(c for c in text if not unicodedata.combining(c))
	return " ".join(text.casefold().split())


def _enqueue(fn, **kwargs):
	frappe.enqueue(
		f"seminary.seminary.oral_meetings.{fn}",
		queue="short",
		enqueue_after_commit=True,
		now=bool(frappe.flags.in_test),
		**kwargs,
	)


# --------------------------------------------------------- staff: scheduling


@frappe.whitelist()
def capture_options(course, activity):
	"""The section's online meetings still to come, and the methods for each."""
	_staff(course)
	_scac(course, activity)
	modality = frappe.db.get_value("Course Schedule", course, "modality")
	methods = {}
	for name in capture_methods():
		try:
			methods[name] = method(name)
		except Exception:
			# A broken provider app must not hide the others.
			frappe.log_error(title=f"Capture method {name} could not be loaded")
	act = _activity(activity)
	meetings = []
	for r in frappe.get_all(
		ROW,
		filters={
			"parent": course,
			"parenttype": "Course Schedule",
			"cs_meetdate": [">=", today()],
		},
		fields=[
			"name",
			"cs_meetdate",
			"cs_fromtime",
			"cs_totime",
			"cs_online",
			"cs_meeting_id",
		],
		order_by="cs_meetdate asc, cs_fromtime asc",
	):
		if not (cint(r.cs_online) or modality == "Virtual"):
			continue
		if not (r.cs_fromtime and r.cs_totime):
			continue
		meetings.append(
			{
				"name": r.name,
				"date": r.cs_meetdate,
				"from_time": str(r.cs_fromtime),
				"to_time": str(r.cs_totime),
				"methods": [
					m
					for m, obj in methods.items()
					if (r.cs_meeting_id or not getattr(obj, "needs_managed", False))
				],
			}
		)
	return {
		"capture": act.capture,
		"methods": [{"method": m, "label": _(METHOD_LABELS.get(m, m))} for m in methods],
		"meetings": meetings,
	}


@frappe.whitelist(methods=["POST"])
def schedule_capture(course: str, activity: str, meeting: str, capture_method: str):
	"""Capture one class meeting for an activity on the section."""
	_staff(course, GRADE)
	scac = _scac(course, activity)
	act = _activity(activity)
	if act.capture != "Virtual meeting":
		frappe.throw(_("This activity is not captured from virtual meetings."))
	row = _row(meeting)
	if not row or row.parent != course:
		frappe.throw(_("That meeting is not on this section."))
	if not (row.cs_fromtime and row.cs_totime):
		frappe.throw(_("That meeting has no time."))
	obj = method(capture_method)
	if getattr(obj, "needs_managed", False) and not row.cs_meeting_id:
		frappe.throw(_("This method records only meetings created on a school meeting account."))
	if frappe.db.exists(OAM, {"meeting": meeting, "oral_activity": activity, "status": ["in", ACTIVE]}):
		frappe.throw(_("This meeting is already captured for this activity."))
	doc = frappe.get_doc(
		{
			"doctype": OAM,
			"course_schedule": course,
			"course_assess": scac,
			"oral_activity": activity,
			"kind": "Whole class",
			"meeting": meeting,
			"meeting_date": row.cs_meetdate,
			"from_time": row.cs_fromtime,
			"to_time": row.cs_totime,
			"method": capture_method,
			"status": "Scheduled",
		}
	).insert(ignore_permissions=True)
	_enqueue("arm", name=doc.name)
	return doc.name


@frappe.whitelist()
def list_captures(course, activity):
	_staff(course)
	return frappe.get_all(
		OAM,
		filters={"course_schedule": course, "oral_activity": activity},
		fields=[
			"name",
			"kind",
			"group_label",
			"meeting",
			"meeting_date",
			"from_time",
			"to_time",
			"method",
			"status",
			"error",
			"captured_on",
			"confirmed_on",
		],
		order_by="meeting_date asc, from_time asc",
	)


@frappe.whitelist(methods=["POST"])
def cancel_capture(name: str):
	doc = _staff_capture(name, GRADE)
	if doc.status not in (*ACTIVE, "Failed"):
		frappe.throw(_("This meeting has already been captured."))
	_cancel(doc)
	return doc.status


def _cancel(doc):
	ref, capture = doc.capture_ref, None
	if ref:
		try:
			capture = _capture(doc)
		except Exception:
			capture = {"name": doc.name}
	doc.db_set({"status": "Cancelled", "capture_ref": None})
	if ref:
		_enqueue("disarm", method_name=doc.method, ref=ref, capture=capture)


def disarm(method_name, ref, capture):
	try:
		method(method_name).disarm(ref, capture)
	except Exception:
		frappe.log_error(title=f"Meeting capture could not stand down: {ref}")


# ----------------------------------------------------------- arming (jobs)


def arm(name):
	"""Ask the method to get ready for the meeting. A missing link waits."""
	doc = frappe.get_doc(OAM, name)
	if doc.status not in ACTIVE:
		return
	capture = _capture(doc)
	if not capture["meeting_url"] and not capture["provider_meeting_id"]:
		doc.db_set({"status": "Scheduled", "error": _("Waiting for the meeting's link.")})
		return
	try:
		ref = method(doc.method).arm(capture)
	except Exception as e:
		frappe.log_error(title=f"Meeting capture could not be armed: {name}")
		doc.db_set({"status": "Failed", "error": _message(e)})
		return
	doc.db_set({"status": "Armed", "capture_ref": str(ref or ""), "error": None})


def rearm(name):
	"""The meeting moved or got its link: stand the old arming down, arm again."""
	doc = frappe.get_doc(OAM, name)
	if doc.status not in ACTIVE:
		return
	if doc.capture_ref:
		disarm(doc.method, doc.capture_ref, _capture(doc))
		doc.db_set({"capture_ref": None, "status": "Scheduled"})
	if doc.get("kind") == "Group":
		arm(name)
		return
	row = _row(doc.meeting)
	doc.db_set(
		{
			"meeting_date": row.cs_meetdate,
			"from_time": row.cs_fromtime,
			"to_time": row.cs_totime,
		}
	)
	arm(name)


def _message(e):
	text = getattr(e, "message", None) or str(e) or e.__class__.__name__
	return frappe.utils.strip_html(text)[:500]


# ------------------------------------------------- Course Schedule lifecycle


def row_in_use(row_name) -> bool:
	"""A meeting an activity captures, or has captured, must not be removed."""
	return bool(frappe.db.exists(OAM, {"meeting": row_name, "status": ["not in", ["Cancelled", "Failed"]]}))


def on_section_update(cs):
	"""A captured meeting that moved or changed its link is armed again."""
	before = cs.get_doc_before_save()
	if not before:
		return
	active = frappe.get_all(
		OAM,
		filters={"course_schedule": cs.name, "status": ["in", ACTIVE]},
		fields=["name", "meeting"],
	)
	if not active:
		return
	old = {r.name: r for r in before.cs_meetinfo or []}
	new = {r.name: r for r in cs.cs_meetinfo or []}
	for a in active:
		o, n = old.get(a.meeting), new.get(a.meeting)
		if not n:
			continue
		if not o or _moved(o, n) or (o.cs_web_meeting or "") != (n.cs_web_meeting or ""):
			_enqueue("rearm", name=a.name)


def _moved(a, b):
	return (
		getdate(a.cs_meetdate) != getdate(b.cs_meetdate)
		or str(get_time(a.cs_fromtime)) != str(get_time(b.cs_fromtime))
		or str(get_time(a.cs_totime)) != str(get_time(b.cs_totime))
	)


def on_meeting_link(row_name):
	"""School meetings (051a) fill a link after the save: arm what waited for it."""
	for name in frappe.get_all(OAM, filters={"meeting": row_name, "status": ["in", ACTIVE]}, pluck="name"):
		_enqueue("rearm", name=name)


def on_section_gone(cs_name):
	for name in frappe.get_all(
		OAM,
		filters={"course_schedule": cs_name, "status": ["in", ACTIVE]},
		pluck="name",
	):
		_cancel(frappe.get_doc(OAM, name))


# ------------------------------------------------------- the provider's result


def meeting_failed(name, error=None):
	doc = frappe.get_doc(OAM, name)
	if doc.status in ACTIVE:
		doc.db_set({"status": "Failed", "error": (error or "")[:500] or None})


def meeting_recorded(name, result):
	"""The method's audio for one captured meeting (100d §3, §4, §6).

	``result``: ``{"participants": [{"key", "name", "email", "joined_at",
	"left_at"}], "rooms": [{"label", "audio", "mime_type", "started_at",
	"ended_at", "tracks": [{"key", "label", "audio", "mime_type",
	"offset_s"}]}]}``, audio as bytes. Refused for a meeting no activity
	captures."""
	from seminary.seminary import oral

	doc = frappe.get_doc(OAM, name) if frappe.db.exists(OAM, name) else None
	if not doc or doc.status != "Armed":
		frappe.throw(_("No oral activity is capturing this meeting."), frappe.PermissionError)
	if isinstance(result, str):
		result = json.loads(result)
	rooms = [r for r in result.get("rooms") or [] if r.get("audio")]
	if not rooms:
		frappe.throw(_("The meeting came back without audio."))
	_suggest(doc, result.get("participants") or [])
	from seminary.seminary.oral_activities import _activity as activity_of
	from seminary.seminary.oral_activities import _steps

	steps = _steps(activity_of(doc.oral_activity))
	for room in rooms:
		_room_recording(oral, doc, room, steps)
	doc.status = "Captured"
	doc.captured_on = now_datetime()
	doc.error = None
	doc.save(ignore_permissions=True)


def _room_recording(oral, doc, room, steps):
	mime = oral._clean_mime(room.get("mime_type") or "audio/mpeg")
	tracks = [t for t in room.get("tracks") or [] if t.get("audio")]
	chosen = [s for s in steps if s in oral.available_steps()]
	if tracks:
		# One track per person settles who spoke when (100d §4).
		chosen = [s for s in chosen if s != "diarize"]
	rec = frappe.get_doc(
		{
			"doctype": "Oral Recording",
			"reference_doctype": SCAC,
			"reference_name": doc.course_assess,
			"course_schedule": doc.course_schedule,
			"activity_meeting": doc.name,
			"status": "Recording",
			"source": "Meeting",
			"recorded_by": doc.owner,
			"started_at": get_datetime(room.get("started_at")) or now_datetime(),
			"mime_type": mime,
			"steps": json.dumps([s for s in oral.PIPELINE if s in chosen]),
		}
	)
	rec.insert(ignore_permissions=True)
	labels = set()
	for t in tracks:
		label = (t.get("label") or _("Participant")).strip()[:120]
		base, n = label, 2
		while label in labels:
			label, n = f"{base} ({n})", n + 1
		labels.add(label)
		t["label"] = label
		url = _attach(rec, t["audio"], oral._clean_mime(t.get("mime_type") or mime), label)
		rec.append(
			"speakers",
			{"label": label, "audio": url, "audio_offset_s": t.get("offset_s") or 0},
		)
		for p in doc.participants:
			if p.get("_key") and p.get("_key") == t.get("key"):
				p.speaker_label = label
	oral._attach_audio(rec, room["audio"])
	ended = get_datetime(room.get("ended_at")) if room.get("ended_at") else None
	oral._finished(rec)
	if ended and ended > get_datetime(rec.started_at):
		rec.db_set(
			{
				"ended_at": ended,
				"duration_s": int((ended - get_datetime(rec.started_at)).total_seconds()),
			}
		)
	return rec.name


def _attach(rec, content, mime, label):
	from seminary.seminary.oral import MIME_EXTENSIONS

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"oral-{rec.name}-{frappe.scrub(label)[:40]}" + MIME_EXTENSIONS.get(mime, ".mp3"),
			"is_private": 1,
			"attached_to_doctype": "Oral Recording",
			"attached_to_name": rec.name,
			"content": content,
		}
	)
	file_doc.save(ignore_permissions=True)
	return file_doc.file_url


def _suggest(doc, participants):
	"""Match each participant to a student: by email, else Suggested by name."""
	from seminary.seminary.oral_activities import _roster

	roster = _roster(doc.course_schedule)
	by_email = {}
	for user, student, _name in roster:
		by_email[user.lower()] = student
		email = frappe.db.get_value("User", user, "email")
		if email:
			by_email[email.lower()] = student
	by_name = {}
	expected = {m.student for m in doc.get("members") or []}
	for _user, student, name in roster:
		by_name.setdefault(_normal(name), []).append(student)
	if expected:
		# A group meeting expects its members: a name among them wins (100d-a §4).
		for key, found in by_name.items():
			mine = [s for s in found if s in expected]
			if mine:
				by_name[key] = mine
	doc.set("participants", [])
	for p in participants:
		email = (p.get("email") or "").strip().lower()
		student, match = None, None
		if email and email in by_email:
			student, match = by_email[email], "Email"
		else:
			found = by_name.get(_normal(p.get("name")))
			if found and len(found) == 1:
				student, match = found[0], "Name"
		row = doc.append(
			"participants",
			{
				"display_name": (p.get("name") or "")[:140],
				"email": email or None,
				"joined_at": (get_datetime(p["joined_at"]) if p.get("joined_at") else None),
				"left_at": get_datetime(p["left_at"]) if p.get("left_at") else None,
				"match": match,
				"suggested_student": student,
				"student": student if match == "Email" else None,
			},
		)
		row._key = p.get("key")


# ------------------------------------------------------- staff: confirming


def _recordings(name):
	return frappe.get_all(
		"Oral Recording",
		filters={"activity_meeting": name},
		fields=["name", "status", "started_at", "ended_at", "duration_s"],
		order_by="creation asc",
	)


@frappe.whitelist()
def get_capture(name):
	doc = _staff_capture(name)
	from seminary.seminary.oral_activities import _roster

	return {
		"name": doc.name,
		"status": doc.status,
		"method": doc.method,
		"meeting_date": doc.meeting_date,
		"from_time": str(doc.from_time or ""),
		"to_time": str(doc.to_time or ""),
		"error": doc.error,
		"confirmed_on": doc.confirmed_on,
		"participants": [
			{
				"name": p.name,
				"display_name": p.display_name,
				"email": p.email,
				"joined_at": p.joined_at,
				"left_at": p.left_at,
				"speaker_label": p.speaker_label,
				"match": p.match,
				"suggested_student": p.suggested_student,
				"student": p.student,
			}
			for p in doc.participants
		],
		"recordings": _recordings(doc.name),
		"roster": [{"student": s, "name": n} for _u, s, n in _roster(doc.course_schedule)],
	}


@frappe.whitelist(methods=["POST"])
def confirm_capture(name: str, links: str | list | dict):
	"""The instructor's list: ``{participant row: student or ""}``. Creates a
	submission for each student, on the recording they spoke in."""
	from seminary.seminary import deadlines
	from seminary.seminary.oral_activities import _roster, _submitted

	doc = _staff_capture(name, GRADE)
	if doc.status != "Captured":
		frappe.throw(_("Only a captured meeting waiting for its list can be confirmed."))
	if isinstance(links, str):
		links = json.loads(links or "{}")
	roster = {s: u for u, s, _n in _roster(doc.course_schedule)}
	seen = set()
	for p in doc.participants:
		student = (links.get(p.name) or "").strip() or None
		if student and student not in roster:
			frappe.throw(_("{0} is not a student on this section.").format(student))
		if student and student in seen:
			frappe.throw(
				_("{0} is linked to more than one participant.").format(
					frappe.db.get_value("Student", student, "student_name") or student
				)
			)
		if student:
			seen.add(student)
		p.student = student
	recordings = [frappe.get_doc("Oral Recording", r.name) for r in _recordings(name)]
	label_to_student = {p.speaker_label: p.student for p in doc.participants if p.speaker_label}
	done = _submitted(doc.course_assess)
	created = []
	for rec in recordings:
		for sp in rec.speakers:
			sp.student = label_to_student.get(sp.label)
		on_this = {sp.student for sp in rec.speakers if sp.student}
		if len(recordings) == 1:
			on_this = set(seen)
		rec.set(
			"participants",
			[{"user": roster[s], "student": s} for s in sorted(on_this)],
		)
		rec.save(ignore_permissions=True)
		at = get_datetime(rec.ended_at) if rec.ended_at else now_datetime()
		for student in sorted(on_this):
			if student in done:
				continue
			dates = deadlines.effective(doc.course_assess, student)
			sub = frappe.get_doc(
				{
					"doctype": SUBMISSION,
					"oral_activity": doc.oral_activity,
					"course": doc.course_schedule,
					"course_assess": doc.course_assess,
					"member": roster[student],
					"student": student,
					"recording": rec.name,
					"activity_meeting": doc.name,
					"submitted_on": at,
					"late": deadlines.seconds_late(dates, at) if dates else 0,
				}
			)
			sub.insert(ignore_permissions=True)
			done.add(student)
			created.append(sub.name)
	doc.status = "Confirmed"
	doc.confirmed_by = frappe.session.user
	doc.confirmed_on = now_datetime()
	doc.save(ignore_permissions=True)
	return {"submissions": created}


# ------------------------------------------------------- attendance (§7)


@frappe.whitelist()
def attendance_suggestions(course_schedule, meeting):
	"""{student: {joined_at, left_at}} from confirmed captures of one meeting."""
	from seminary.seminary.guards import require_course_staff

	require_course_staff(course_schedule, include_registrar=True)
	out = {}
	for name in frappe.get_all(
		OAM,
		filters={
			"course_schedule": course_schedule,
			"meeting": meeting,
			"status": "Confirmed",
		},
		pluck="name",
	):
		for p in frappe.get_doc(OAM, name).participants:
			if p.student and p.student not in out:
				out[p.student] = {"joined_at": p.joined_at, "left_at": p.left_at}
	return out


def captured_rows(course_schedule) -> set:
	"""Class meeting rows recorded for assessment, for the notice (100d §5).
	Group meetings are not class meetings and never reach the shared feed."""
	return set(
		frappe.get_all(
			OAM,
			filters={
				"course_schedule": course_schedule,
				"kind": ["!=", "Group"],
				"meeting": ["is", "set"],
				"status": ["not in", ["Cancelled", "Failed"]],
			},
			pluck="meeting",
		)
	)
