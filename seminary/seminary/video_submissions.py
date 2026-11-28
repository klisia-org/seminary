# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Video assignments (privatedocs p029).

A *Video* assignment is recorded in the browser at 720p or uploaded as a file,
straight to object storage in parts (``seminary.storage.direct``). Saving the
submission makes the video an ``Oral Recording`` of it (100 §2), so the steps
an app provides run on it as on any oral work, and the 100 §8 retention job
deletes it. The recording owns the File row: deleting the audio of the
recording deletes the video, and ``audio_deleted_on`` says when.

Offered only where an app adds the steps and the site stores media off its
own disk: a 20-minute video does not belong on a shared school server.
"""

from __future__ import annotations

import json
import os

import frappe
from frappe import _
from frappe.utils import cint, strip_html

SUBMISSION = "Assignment Submission"
RECORDING = "Oral Recording"
ACTIVITY = "Assignment Activity"

DEFAULT_MINUTES = 20
DEFAULT_CEILING_MINUTES = 60
# 1.2 Mbps of video and 96 kbps of audio, the recorder's 720p rates.
BYTES_PER_MINUTE = (1_200_000 + 96_000) // 8 * 60
# A phone's own recording runs above the recorder's rate; this much room is allowed.
SIZE_MARGIN = 1.25

VIDEO_MIME = {".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime"}


def is_offered() -> bool:
	"""True when the site has an app providing the steps and storage taking parts."""
	if "aretenic" not in frappe.get_installed_apps():
		return False
	from seminary.storage.backend import get_storage_backend

	backend = get_storage_backend()
	return bool(backend.is_configured() and backend.supports_multipart())


def ceiling_minutes() -> int:
	value = frappe.db.get_single_value("Seminary Settings", "video_max_minutes")
	return cint(value) if value not in (None, "") else DEFAULT_CEILING_MINUTES


def max_minutes(activity) -> int:
	minutes = cint(activity.get("max_video_minutes")) or DEFAULT_MINUTES
	return max(1, min(minutes, ceiling_minutes() or DEFAULT_CEILING_MINUTES))


def max_bytes(activity) -> int:
	return int(max_minutes(activity) * BYTES_PER_MINUTE * SIZE_MARGIN)


def upload_ceiling(assignment) -> int:
	"""The size a video for ``assignment`` may reach, for ``start_multipart``."""
	if not assignment or not frappe.db.exists(ACTIVITY, assignment):
		frappe.throw(_("Choose the assignment this video is for."))
	if not frappe.has_permission(ACTIVITY, "read", assignment):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	activity = frappe.get_cached_doc(ACTIVITY, assignment)
	if activity.type != "Video":
		frappe.throw(_("This assignment does not take a video."))
	return max_bytes(activity)


def validate_activity(doc, method=None):
	"""Assignment Activity ``validate``: a new Video type needs the site to offer it."""
	if doc.type != "Video":
		return
	before = doc.get_doc_before_save()
	if (doc.is_new() or (before and before.type != "Video")) and not is_offered():
		frappe.throw(_("Video assignments are not available on this site."))
	ceiling = ceiling_minutes()
	if not cint(doc.max_video_minutes):
		doc.max_video_minutes = min(DEFAULT_MINUTES, ceiling)
	if ceiling and cint(doc.max_video_minutes) > ceiling:
		frappe.throw(
			_("A video may be at most {0} minutes long on this site.").format(ceiling),
			title=_("Video too long"),
		)
	doc.expected_speakers = max(1, cint(doc.expected_speakers) or 1)
	doc.video_steps = json.dumps(_clean_steps(doc.video_steps))


def _clean_steps(value):
	from seminary.seminary.oral import PIPELINE

	try:
		steps = json.loads(value or "[]")
	except ValueError:
		steps = []
	return [s for s in PIPELINE if s in (steps if isinstance(steps, list) else [])]


# ---------------------------------------------------------------- the resolver


def resolve(submission, user):
	"""What a video submission says about its recording (see ``oral._resolve``)."""
	sub = frappe.db.get_value(
		SUBMISSION, submission, ["name", "member", "student", "course", "assignment"], as_dict=True
	)
	if not sub:
		frappe.throw(_("Submission not found."), frappe.PermissionError)
	activity = frappe.get_cached_doc(ACTIVITY, sub.assignment)
	from seminary.seminary.oral_activities import rubric_criteria

	return {
		"course_schedule": sub.course,
		"participants": [(sub.member, sub.student)] if sub.student else [],
		# Recorded by the video recorder, never by the audio one.
		"may_record": False,
		"allow_upload": False,
		"steps": _clean_steps(activity.video_steps),
		"expected_speakers": max(1, cint(activity.expected_speakers) or 1),
		"prompt": strip_html(activity.question or "").strip() or None,
		"criteria": rubric_criteria(activity.rubric) if activity.rubric else [],
		"max_seconds": max_minutes(activity) * 60,
	}


# -------------------------------------------------------- submission -> recording


def is_video(sub) -> bool:
	"""A submission's type is its activity's: the portal inserts submissions without one."""
	kind = sub.get("type") or frappe.db.get_value(ACTIVITY, sub.get("assignment"), "type")
	return kind == "Video"


def recording_of(submission):
	return frappe.db.get_value(
		RECORDING,
		{"reference_doctype": SUBMISSION, "reference_name": submission},
		"name",
		order_by="creation desc",
	)


def _mime_of(file_name):
	return VIDEO_MIME.get(os.path.splitext(file_name or "")[1].lower(), "video/mp4")


def on_submission_update(doc, method=None):
	"""Assignment Submission ``on_update``: a new video becomes the submission's recording."""
	if not is_video(doc):
		return
	url = doc.assignment_attachment
	current = recording_of(doc.name)
	if current:
		rec = frappe.db.get_value(RECORDING, current, ["audio", "audio_deleted_on"], as_dict=True)
		if rec.audio_deleted_on or rec.audio == url:
			return
		# The student replaced the video before grading: the old one goes with its recording.
		_drop_recording(current)
	if not url:
		return
	# Only the student's own upload, not yet claimed: a submission naming another
	# student's video URL must not take that video over.
	file_name = next(
		(
			f.name
			for f in frappe.get_all(
				"File",
				filters={"file_url": url},
				fields=["name", "owner", "attached_to_doctype", "attached_to_name"],
			)
			if f.owner == doc.member
			and (
				not f.attached_to_doctype
				or (f.attached_to_doctype == SUBMISSION and f.attached_to_name == doc.name)
			)
		),
		None,
	)
	if not file_name:
		if frappe.db.exists("File", {"file_url": url}):
			# A group member's copy of the work (decisions/120): the video is
			# already the uploader's recording.
			return
		frappe.throw(_("The video was not found. Please upload it again."))
	_make_recording(doc, file_name)


def _make_recording(sub, file_name):
	from seminary.seminary import oral

	ctx = resolve(sub.name, sub.member)
	file_doc = frappe.get_doc("File", file_name)
	rec = frappe.get_doc(
		{
			"doctype": RECORDING,
			"reference_doctype": SUBMISSION,
			"reference_name": sub.name,
			"course_schedule": ctx["course_schedule"],
			"status": "Recording",
			"source": "Uploaded",
			"recorded_by": sub.member,
			"mime_type": _mime_of(file_doc.file_name),
			"started_at": frappe.utils.now_datetime(),
			"steps": json.dumps(ctx["steps"]),
			"participants": [{"user": u, "student": s} for u, s in ctx["participants"]],
		}
	).insert(ignore_permissions=True)
	# The recording owns the bytes, so 100 §8 retention deletes the video itself.
	file_doc.db_set(
		{
			"attached_to_doctype": RECORDING,
			"attached_to_name": rec.name,
			"attached_to_field": "audio",
		}
	)
	rec.audio = file_doc.file_url
	oral._finished(rec)
	return rec.name


def _drop_recording(name):
	from seminary.seminary import oral

	doc = frappe.get_doc(RECORDING, name)
	if doc.audio:
		oral.delete_audio(doc)
	for moment in frappe.get_all("Oral Moment", filters={"recording": name}, pluck="name"):
		frappe.delete_doc("Oral Moment", moment, ignore_permissions=True, force=True)
	for result in frappe.get_all("Oral Step Result", filters={"recording": name}, pluck="name"):
		frappe.delete_doc("Oral Step Result", result, ignore_permissions=True, force=True)
	frappe.delete_doc(RECORDING, name, ignore_permissions=True, force=True)


def on_submission_trash(doc, method=None):
	if is_video(doc):
		current = recording_of(doc.name)
		if current:
			_drop_recording(current)


def moment_kept(moment):
	"""A kept moment on a video submission becomes its timestamp comment, which
	the student sees once grades are released, as any other (100 §6)."""
	ref = frappe.db.get_value(
		RECORDING, moment.recording, ["reference_doctype", "reference_name"], as_dict=True
	)
	if not ref or ref.reference_doctype != SUBMISSION:
		return
	text = " ".join(p for p in (moment.criterion_code, moment.note) if p).strip()
	frappe.get_doc(
		{
			"doctype": "Assignment Submission Comment",
			"parent": ref.reference_name,
			"parenttype": SUBMISSION,
			"parentfield": "comments_thread",
			"anchor_type": "Timestamp",
			"timestamp_s": int(moment.start or 0),
			"comment": frappe.utils.escape_html(text or _("Moment to review")),
			"author": frappe.session.user,
			"resolved": 0,
		}
	).insert(ignore_permissions=True)


# ------------------------------------------------------------------ endpoints


@frappe.whitelist()
def video_of(submission: str):
	"""The recording behind a video submission, for its player: its name, and
	when the video was deleted under the school's retention rule."""
	if not frappe.has_permission(SUBMISSION, "read", submission):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	name = recording_of(submission)
	if not name:
		return {"recording": None}
	rec = frappe.db.get_value(RECORDING, name, ["name", "status", "audio_deleted_on"], as_dict=True)
	return {
		"recording": rec.name,
		"status": rec.status,
		"deleted_on": rec.audio_deleted_on,
	}


@frappe.whitelist()
def video_limits(assignment: str):
	"""What the recorder needs to know before it starts."""
	activity = frappe.get_cached_doc(ACTIVITY, assignment)
	if not frappe.has_permission(ACTIVITY, "read", assignment):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	from seminary.seminary.oral import STEP_LABELS, _settings

	return {
		"offered": is_offered(),
		"max_minutes": max_minutes(activity),
		"max_bytes": max_bytes(activity),
		"steps": [_(STEP_LABELS[s]) for s in _clean_steps(activity.video_steps)],
		"retention_days": cint(_settings().get("oral_audio_retention_days") or 365),
	}
