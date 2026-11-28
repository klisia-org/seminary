# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""privatedocs p029: video assignments, uploads in parts, and draft captions.

An object store in a dict stands in for the storage app, and a fake generator
for the app that drafts captions."""

import hashlib
import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from seminary.seminary import captions, oral, video_submissions
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr082_deadlines import _row, _scale, _section
from seminary.seminary.tests.test_adr120_group_work import _enrol
from seminary.storage import direct

THIS = "seminary.seminary.tests.test_p029_video_submissions"
GENERATED = []


class FakeStore:
	"""Multipart uploads and objects in dicts, like R2 at the seams seminary uses."""

	def __init__(self):
		self.objects = {}
		self.uploads = {}

	def is_configured(self):
		return True

	def supports_multipart(self):
		return True

	def create_multipart(self, key, content_type=None):
		upload_id = f"up-{len(self.uploads) + 1}"
		self.uploads[upload_id] = {"key": key, "parts": {}}
		return upload_id

	def presigned_part(self, key, upload_id, part_number, ttl=None):
		return f"https://store.invalid/{key}?part={part_number}"

	def put_part(self, upload_id, number, data):
		"""What the browser's PUT to the part URL does."""
		self.uploads[upload_id]["parts"][number] = data

	def complete_multipart(self, key, upload_id):
		parts = self.uploads.pop(upload_id)["parts"]
		if not parts:
			return 0
		self.objects[key] = b"".join(parts[n] for n in sorted(parts))
		return len(parts)

	def abort_multipart(self, key, upload_id):
		self.uploads.pop(upload_id, None)

	def list_multipart(self, prefix):
		return []

	def stat(self, key):
		if key not in self.objects:
			return None
		data = self.objects[key]
		# A multipart ETag is not the content hash.
		return {"size": len(data), "etag": f"{hashlib.md5(data, usedforsecurity=False).hexdigest()}-2"}

	def stream(self, key, chunk_size=1024 * 1024):
		yield self.objects[key]

	def copy(self, source, dest):
		self.objects[dest] = self.objects[source]

	def delete(self, key):
		self.objects.pop(key, None)

	def list_keys(self, prefix):
		return []

	def presigned_get(self, key, ttl=None, file_name=None, content_type=None, as_attachment=False):
		return f"https://store.invalid/{key}"


def fake_generator(request, video_url, language):
	GENERATED.append((request, video_url, language))


def _activity(**values):
	doc = frappe.get_doc(
		{
			"doctype": "Assignment Activity",
			"title": fx.uid("Sermon"),
			"type": "Video",
			"question": "<p>Preach on Romans 8.</p>",
			"grade_assignment": 1,
			"video_steps": json.dumps(["transcribe", "moments", "questions"]),
			**values,
		}
	)
	doc.flags.ignore_links = True
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc


class VideoCase(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		GENERATED.clear()
		self.store = FakeStore()
		for target in (
			"seminary.storage.backend.get_storage_backend",
			"seminary.storage.direct.get_storage_backend",
			"seminary.storage.hooks.get_storage_backend",
		):
			p = patch(target, return_value=self.store)
			p.start()
			self.addCleanup(p.stop)
		offered = patch.object(video_submissions, "is_offered", return_value=True)
		offered.start()
		self.addCleanup(offered.stop)
		self.cs = _section(_scale(), published=1)
		self.student = fx.make_student()
		self.other = fx.make_student()
		for s in (self.student, self.other):
			_enrol(self.cs, s)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def upload(self, user, act, chunks=None):
		"""Send a video in parts as `user`, as the browser does, and register it.
		Each upload's bytes are its own: storage keys are content hashes."""
		chunks = chunks or (b"a" * 10, frappe.generate_hash(length=5).encode())
		frappe.set_user(user)
		try:
			out = direct.start_multipart("sermon.mp4", "video/mp4;codecs=avc1", act)
			upload_id = frappe.cache.get_value(direct._pending_key(out["key"].split("/")[2]))["upload_id"]
			for i, chunk in enumerate(chunks, start=1):
				direct.presign_part(out["key"], i)
				self.store.put_part(upload_id, i, chunk)
			return direct.complete_multipart(out["key"])
		finally:
			frappe.set_user("Administrator")

	def submit(self, student, act, file_url):
		frappe.set_user(student.user)
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Assignment Submission",
					"assignment": act,
					"member": student.user,
					"course": self.cs,
					"assignment_attachment": file_url,
				}
			)
			doc.insert(ignore_permissions=True)
			return doc
		finally:
			frappe.set_user("Administrator")


class TestActivity(VideoCase):
	def test_a_new_video_assignment_needs_the_site_to_offer_it(self):
		with patch.object(video_submissions, "is_offered", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				_activity()

	def test_length_defaults_to_twenty_minutes_and_stops_at_the_school_ceiling(self):
		act = _activity()
		self.assertEqual(act.max_video_minutes, 20)
		self.assertEqual(act.expected_speakers, 1)
		with patch.object(video_submissions, "ceiling_minutes", return_value=30):
			with self.assertRaises(frappe.ValidationError):
				_activity(max_video_minutes=45)

	def test_only_steps_that_run_on_a_finished_recording_are_kept(self):
		act = _activity()
		self.assertEqual(json.loads(act.video_steps), ["transcribe", "moments"])

	def test_the_size_ceiling_follows_the_length_at_720p(self):
		act = _activity(max_video_minutes=10)
		expected = int(10 * video_submissions.BYTES_PER_MINUTE * video_submissions.SIZE_MARGIN)
		self.assertEqual(video_submissions.max_bytes(act), expected)
		# About 9.7 MB a minute, as the recorder's notice says.
		self.assertAlmostEqual(video_submissions.BYTES_PER_MINUTE / 1e6, 9.72, places=2)


class TestMultipart(VideoCase):
	def test_parts_join_into_one_private_offloaded_file(self):
		act = _activity()
		tail = frappe.generate_hash(length=5).encode()
		out = self.upload(self.student.user, act.name, chunks=(b"a" * 10, tail))
		file_doc = frappe.get_doc("File", out["name"])
		self.assertTrue(file_doc.is_private)
		self.assertEqual(file_doc.file_size, 15)
		self.assertEqual(file_doc.owner, self.student.user)
		# Keyed by the content's MD5, hashed by streaming: a multipart ETag is not it.
		digest = hashlib.md5(b"a" * 10 + tail, usedforsecurity=False).hexdigest()
		self.assertTrue(file_doc.file_url.endswith(f"key=media/{digest[:2]}/{digest}"))
		self.assertIn(f"media/{digest[:2]}/{digest}", self.store.objects)

	def test_a_part_past_the_ceiling_is_refused(self):
		act = _activity(max_video_minutes=1)
		frappe.set_user(self.student.user)
		out = direct.start_multipart("sermon.webm", "video/webm", act.name)
		too_far = video_submissions.max_bytes(act) // direct.PART_SIZE + 2
		with self.assertRaises(frappe.ValidationError):
			direct.presign_part(out["key"], too_far)

	def test_an_oversized_join_is_refused_and_removed(self):
		act = _activity(max_video_minutes=1)
		with patch.object(video_submissions, "max_bytes", return_value=10):
			with self.assertRaises(frappe.ValidationError):
				self.upload(self.student.user, act.name)
		self.assertEqual(self.store.objects, {})

	def test_another_user_cannot_finish_the_upload(self):
		act = _activity()
		frappe.set_user(self.student.user)
		out = direct.start_multipart("sermon.mp4", "video/mp4", act.name)
		frappe.set_user(self.other.user)
		with self.assertRaises(frappe.PermissionError):
			direct.complete_multipart(out["key"])

	def test_only_video_is_accepted(self):
		act = _activity()
		frappe.set_user(self.student.user)
		with self.assertRaises(frappe.ValidationError):
			direct.start_multipart("paper.pdf", "application/pdf", act.name)

	def test_an_assignment_of_another_type_takes_no_video(self):
		act = _activity()
		frappe.db.set_value("Assignment Activity", act.name, "type", "PDF")
		frappe.clear_document_cache("Assignment Activity", act.name)
		frappe.set_user(self.student.user)
		with self.assertRaises(frappe.ValidationError):
			direct.start_multipart("sermon.mp4", "video/mp4", act.name)


class TestRecording(VideoCase):
	def setUp(self):
		super().setUp()
		self.act = _activity(rubric=None)
		_row(self.cs, add_days(today(), 7), kind="Assignment", assignment=self.act.name)
		self._provided = patch.object(oral, "provided_steps", return_value={})
		self._provided.start()
		self.addCleanup(self._provided.stop)

	def test_a_submitted_video_becomes_its_recording(self):
		file_url = self.upload(self.student.user, self.act.name)["file_url"]
		sub = self.submit(self.student, self.act.name, file_url)
		name = video_submissions.recording_of(sub.name)
		rec = frappe.get_doc("Oral Recording", name)
		self.assertEqual(rec.audio, file_url)
		self.assertEqual(rec.source, "Uploaded")
		self.assertEqual(rec.mime_type, "video/mp4")
		self.assertEqual(json.loads(rec.steps), ["transcribe", "moments"])
		self.assertEqual([p.student for p in rec.participants], [self.student.name])
		# The recording holds a File over the video, so retention deletes the video itself.
		self.assertTrue(
			frappe.db.exists(
				"File",
				{"file_url": file_url, "attached_to_doctype": "Oral Recording", "attached_to_name": rec.name},
			)
		)
		self.assertEqual(oral._resolve("Assignment Submission", sub.name)["expected_speakers"], 1)

	def test_another_students_video_url_is_not_taken_over(self):
		file_url = self.upload(self.other.user, self.act.name)["file_url"]
		with self.assertRaises(frappe.PermissionError):
			self.submit(self.student, self.act.name, file_url)
		# Nor by the recording, should the file policy ever let it through.
		sub = frappe._dict(name="AS-x", member=self.student.user, assignment=self.act.name, type="Video")
		sub.assignment_attachment = file_url
		with patch.object(video_submissions, "_make_recording") as make:
			video_submissions.on_submission_update(sub)
		make.assert_not_called()

	def test_a_replaced_video_drops_the_old_recording_and_file(self):
		first = self.upload(self.student.user, self.act.name)["file_url"]
		sub = self.submit(self.student, self.act.name, first)
		old = video_submissions.recording_of(sub.name)
		second = self.upload(self.student.user, self.act.name, chunks=(b"c" * 7,))["file_url"]
		sub.reload()
		sub.assignment_attachment = second
		sub.save(ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Oral Recording", old))
		self.assertFalse(frappe.db.exists("File", {"file_url": first}))
		self.assertEqual(
			frappe.db.get_value("Oral Recording", video_submissions.recording_of(sub.name), "audio"), second
		)

	def test_retention_leaves_the_date_the_video_was_deleted(self):
		file_url = self.upload(self.student.user, self.act.name)["file_url"]
		sub = self.submit(self.student, self.act.name, file_url)
		rec = frappe.get_doc("Oral Recording", video_submissions.recording_of(sub.name))
		oral.delete_audio(rec)
		info = video_submissions.video_of(sub.name)
		self.assertTrue(info["deleted_on"])
		self.assertFalse(frappe.db.exists("File", {"file_url": file_url}))
		# The object goes once the deletion commits, with the upload's temporary copy.
		frappe.db.after_commit.run()
		self.assertEqual(self.store.objects, {})

	def test_a_kept_moment_becomes_a_timestamp_comment(self):
		file_url = self.upload(self.student.user, self.act.name)["file_url"]
		sub = self.submit(self.student, self.act.name, file_url)
		rec = video_submissions.recording_of(sub.name)
		moment = frappe.get_doc(
			{
				"doctype": "Oral Moment",
				"recording": rec,
				"start": 42.7,
				"end": 50,
				"source": "Suggested",
				"state": "Suggested",
				"criterion_code": "C1",
				"note": "Clear thesis <here>",
			}
		)
		moment.flags.from_step = True
		moment.insert(ignore_permissions=True)
		with patch.object(oral, "_staff_recording"):
			oral.set_moment_state(moment.name, "Kept")
		row = frappe.get_all(
			"Assignment Submission Comment",
			filters={"parent": sub.name, "anchor_type": "Timestamp"},
			fields=["timestamp_s", "comment"],
		)
		self.assertEqual(len(row), 1)
		self.assertEqual(row[0].timestamp_s, 42)
		self.assertTrue(row[0].comment.startswith("C1 Clear thesis"))
		self.assertNotIn("<here>", row[0].comment)

	def test_trashing_the_submission_removes_its_recording(self):
		file_url = self.upload(self.student.user, self.act.name)["file_url"]
		sub = self.submit(self.student, self.act.name, file_url)
		rec = video_submissions.recording_of(sub.name)
		frappe.delete_doc("Assignment Submission", sub.name, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("Oral Recording", rec))


class TestCaptions(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		GENERATED.clear()
		hooks = patch.object(captions, "generators", return_value=[f"{THIS}.fake_generator"])
		hooks.start()
		self.addCleanup(hooks.stop)
		self.video = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{fx.uid('lecture')}.mp4",
				"content": b"not really a video",
				"is_private": 0,
			}
		).insert(ignore_permissions=True)
		self.language = frappe.db.get_value("Language", {"enabled": 1}, "name") or "en"

	def test_a_request_goes_to_the_generator_and_waits(self):
		out = captions.request_captions(self.video.file_url, self.language)
		self.assertEqual(out["status"], "Requested")
		self.assertEqual(GENERATED, [(out["name"], self.video.file_url, self.language)])

	def test_ready_captions_are_a_private_vtt_the_requester_owns(self):
		out = captions.request_captions(self.video.file_url, self.language)
		captions.captions_ready(out["name"], "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello\n")
		state = captions.caption_request(out["name"])
		self.assertEqual(state["status"], "Ready")
		file_doc = frappe.get_doc("File", {"file_url": state["caption_file"]})
		self.assertTrue(file_doc.is_private)
		self.assertTrue(file_doc.file_name.endswith(f"-{self.language}.vtt"))
		self.assertEqual(file_doc.owner, "Administrator")
		self.assertEqual(captions.caption_requests([self.video.file_url])[0]["name"], out["name"])

	def test_anything_but_webvtt_fails_the_request(self):
		out = captions.request_captions(self.video.file_url, self.language)
		captions.captions_ready(out["name"], "1\n00:00:00,000 --> 00:00:01,000\nHello\n")
		self.assertEqual(captions.caption_request(out["name"])["status"], "Failed")

	def test_a_video_not_on_this_site_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			captions.request_captions("https://example.com/video.mp4", self.language)

	def test_a_draft_is_labelled_machine_generated(self):
		self.assertEqual(captions.draft_label("English", "Draft"), "English (machine-generated)")
		self.assertEqual(captions.draft_label("English", "Reviewed"), "English")
		self.assertEqual(captions.draft_label("English", None), "English")
