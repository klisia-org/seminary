# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Machine-generated captions for uploaded videos (privatedocs p029 §7, §8).

An app provides caption generation through the ``seminary_caption_generators``
hook: a dotted path called with ``(request, video_url, language)``. It returns
at once and later calls ``captions_ready(request, vtt)`` or
``captions_failed(request, error)``, because transcription is slow.

The captions come back as a *Draft*: the editor that asked adds a Draft row to
its own caption list (a lesson's Captions table, or a rich-text video's
``data-captions``), so this module never needs to know which record holds the
video. Students see a draft, labelled machine-generated; the content check
counts a video as captioned only once its captions are *Reviewed*.
"""

from __future__ import annotations

import os

import frappe
from frappe import _
from frappe.utils import now_datetime

REQUEST = "Caption Request"
DRAFT, REVIEWED = "Draft", "Reviewed"


def generators() -> list[str]:
	return frappe.get_hooks("seminary_caption_generators") or []


def draft_label(label, status):
	"""The label a player shows: a draft says it is machine-generated."""
	if status == DRAFT:
		return _("{0} (machine-generated)").format(label)
	return label


def _require_editor():
	from seminary.seminary.guards import is_school_role
	from seminary.seminary.utils import has_course_instructor_role, has_course_moderator_role

	user = frappe.session.user
	if not (is_school_role(user) or has_course_instructor_role(user) or has_course_moderator_role(user)):
		frappe.throw(_("Only instructors can generate captions."), frappe.PermissionError)


def _video_file(video):
	"""The File row behind a video URL on this site, readable by this user."""
	from seminary.storage.backend import normalize_file_url

	url = normalize_file_url((video or "").strip())
	name = frappe.db.get_value("File", {"file_url": url}, "name") if url else None
	if not name:
		frappe.throw(_("Captions can be generated only for a video uploaded to this site."))
	doc = frappe.get_doc("File", name)
	if not frappe.has_permission("File", "read", doc=doc):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	return doc


@frappe.whitelist(methods=["POST"])
def request_captions(video: str, language: str):
	"""Ask the provider for draft captions of ``video`` in ``language``."""
	_require_editor()
	paths = generators()
	if not paths:
		frappe.throw(_("Caption generation is not available on this site."))
	if not language or not frappe.db.exists("Language", language):
		frappe.throw(_("Choose the language spoken in the video."))
	file_doc = _video_file(video)
	doc = frappe.get_doc(
		{
			"doctype": REQUEST,
			"video": file_doc.file_url,
			"language": language,
			"status": "Requested",
			"requested_by": frappe.session.user,
			"requested_on": now_datetime(),
		}
	).insert(ignore_permissions=True)
	try:
		frappe.get_attr(paths[-1])(request=doc.name, video_url=file_doc.file_url, language=language)
	except Exception as e:
		frappe.log_error(title=f"Caption request {doc.name} could not start")
		captions_failed(doc.name, str(e))
	return _state(frappe.get_doc(REQUEST, doc.name))


def _state(doc):
	return {
		"name": doc.name,
		"video": doc.video,
		"language": doc.language,
		"status": doc.status,
		"caption_file": doc.caption_file,
		"error": doc.error,
	}


def _readable(doc):
	from seminary.seminary.guards import is_school_role

	user = frappe.session.user
	if doc.requested_by != user and not is_school_role(user):
		frappe.throw(_("Not permitted."), frappe.PermissionError)


@frappe.whitelist()
def caption_request(name: str):
	"""Where one request stands, for the editor waiting on it."""
	doc = frappe.get_doc(REQUEST, name) if frappe.db.exists(REQUEST, name) else None
	if not doc:
		frappe.throw(_("Not found."), frappe.DoesNotExistError)
	_readable(doc)
	return _state(doc)


@frappe.whitelist()
def caption_requests(videos: str | list):
	"""This user's latest request per video and language, so an editor reopened
	after the captions came back can still add them."""
	_require_editor()
	if isinstance(videos, str):
		videos = frappe.parse_json(videos)
	from seminary.storage.backend import normalize_file_url

	urls = [normalize_file_url(v) for v in (videos or []) if v][:50]
	if not urls:
		return []
	rows = frappe.get_all(
		REQUEST,
		filters={"video": ["in", urls], "requested_by": frappe.session.user},
		fields=["name", "video", "language", "status", "caption_file", "error"],
		order_by="creation desc",
		limit=200,
	)
	latest = {}
	for r in rows:
		latest.setdefault((r.video, r.language), r)
	return list(latest.values())


def captions_ready(request, vtt):
	"""The provider's WebVTT for ``request``. Not a web endpoint."""
	doc = frappe.get_doc(REQUEST, request)
	if doc.status != "Requested":
		return
	text = vtt.decode("utf-8") if isinstance(vtt, bytes) else str(vtt or "")
	if not text.lstrip("﻿").startswith("WEBVTT"):
		captions_failed(request, "The provider did not return WebVTT.")
		return
	video_name = frappe.db.get_value("File", {"file_url": doc.video}, "file_name") or "video"
	base = os.path.splitext(video_name)[0] or "video"
	# Private and loose, as an uploaded caption file is: the requester owns it, and
	# saving the lesson that lists it attaches it there (file_policy.adopt), so
	# whoever reads the lesson reads its captions.
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{base}-{doc.language}.vtt",
			"content": text.encode("utf-8"),
			"is_private": 1,
		}
	).insert(ignore_permissions=True)
	file_doc.db_set("owner", doc.requested_by, update_modified=False)
	doc.caption_file = file_doc.file_url
	doc.status = "Ready"
	doc.completed_on = now_datetime()
	doc.save(ignore_permissions=True)
	_tell(doc)


def captions_failed(request, error=None):
	doc = frappe.get_doc(REQUEST, request)
	if doc.status != "Requested":
		return
	doc.status = "Failed"
	doc.error = (error or _("Captions could not be generated."))[:1000]
	doc.completed_on = now_datetime()
	doc.save(ignore_permissions=True)
	_tell(doc)


def _tell(doc):
	frappe.publish_realtime("caption_request", _state(doc), user=doc.requested_by, after_commit=True)
