# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""ADR 100 §2–§8: recording in chunks, the step pipeline, permissions and
retention. A ToDo stands in for the record a recording belongs to, and a fake
provider stands in for the app that runs the steps."""

import json
import os
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from seminary.seminary import oral
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr081_attendance import _roster, _section

THIS = "seminary.seminary.tests.test_adr100_oral_core"
CALLS = []
CONTEXT = {}


def resolve(name, user):
	"""The fake record: whatever the test put in CONTEXT."""
	return dict(CONTEXT)


def _bytes(file_doc):
	content = file_doc.get_content()
	return content.encode() if isinstance(content, str) else content


def fake_step(recording, step, payload):
	CALLS.append((recording, step, payload))


def failing_step(recording, step, payload):
	raise RuntimeError("provider down")


@contextmanager
def _settings(**values):
	base = {"oral_audio_retention_days": 365, "oral_max_minutes": 60}
	base.update(values)
	with patch.object(oral, "_settings", return_value=frappe._dict(base)):
		yield


@contextmanager
def _provided(*steps, path=f"{THIS}.fake_step"):
	with patch.object(oral, "provided_steps", return_value={s: path for s in steps}):
		yield


class OralCase(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		CALLS.clear()
		self.program = fx.make_program()
		self.student = fx.make_student()
		self.user = self.student.user
		self.classmate = fx.make_student()
		self.cs = _section()
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "oral reference"}).insert(
			ignore_permissions=True
		)
		CONTEXT.clear()
		CONTEXT.update(
			{
				"course_schedule": self.cs,
				"participants": [(self.user, self.student.name)],
				"may_record": True,
				"steps": [],
				"criteria": [{"criterion_code": "C1"}],
			}
		)
		self._refs = patch.dict(oral.REFERENCES, {"ToDo": f"{THIS}.resolve"})
		self._refs.start()

	def tearDown(self):
		self._refs.stop()
		frappe.set_user("Administrator")
		super().tearDown()

	def record(self, chunks=(b"aa", b"bb", b"cc"), steps=None):
		"""Record as the student, chunk by chunk, and finish."""
		if steps is not None:
			CONTEXT["steps"] = steps
		frappe.set_user(self.user)
		name = oral.start_recording("ToDo", self.todo.name, "audio/webm;codecs=opus")["recording"]
		doc = frappe.get_doc("Oral Recording", name)
		for i, chunk in enumerate(chunks):
			oral._store_chunk(doc, i, chunk)
		oral.finish_recording(name, len(chunks))
		frappe.set_user("Administrator")
		return frappe.get_doc("Oral Recording", name)


class TestRecording(OralCase):
	def test_chunks_join_in_order_into_one_private_file(self):
		with _settings(), _provided():
			doc = self.record()
		self.assertEqual(doc.status, "Ready")
		self.assertTrue(doc.audio)
		file_doc = frappe.get_doc("File", {"file_url": doc.audio})
		self.assertTrue(file_doc.is_private)
		self.assertEqual(file_doc.attached_to_name, doc.name)
		self.assertEqual(_bytes(file_doc), b"aabbcc")
		self.assertFalse(os.path.isdir(oral._chunk_dir(doc.name)))
		self.assertEqual(
			[(p.user, p.student) for p in doc.participants],
			[(self.user, self.student.name)],
		)
		self.assertEqual(doc.mime_type, "audio/webm")

	def test_a_resent_chunk_replaces_the_first(self):
		frappe.set_user(self.user)
		name = oral.start_recording("ToDo", self.todo.name, "audio/webm")["recording"]
		doc = frappe.get_doc("Oral Recording", name)
		oral._store_chunk(doc, 0, b"old")
		oral._store_chunk(doc, 0, b"new")
		oral._store_chunk(doc, 1, b"!")
		self.assertEqual(oral.received_chunks(name), [0, 1])
		with _settings(), _provided():
			oral.finish_recording(name, 2)
		frappe.set_user("Administrator")
		audio = frappe.db.get_value("Oral Recording", name, "audio")
		self.assertEqual(_bytes(frappe.get_doc("File", {"file_url": audio})), b"new!")

	def test_finishing_with_a_gap_names_what_is_missing(self):
		frappe.set_user(self.user)
		name = oral.start_recording("ToDo", self.todo.name, "audio/webm")["recording"]
		doc = frappe.get_doc("Oral Recording", name)
		oral._store_chunk(doc, 0, b"a")
		oral._store_chunk(doc, 2, b"c")
		with self.assertRaises(frappe.ValidationError) as caught:
			oral.finish_recording(name, 3)
		self.assertIn("1", str(caught.exception))
		self.assertEqual(frappe.db.get_value("Oral Recording", name, "status"), "Recording")

	def test_someone_else_cannot_add_to_a_recording(self):
		frappe.set_user(self.user)
		name = oral.start_recording("ToDo", self.todo.name, "audio/webm")["recording"]
		frappe.set_user(self.classmate.user)
		self.assertRaises(frappe.PermissionError, oral.received_chunks, name)
		self.assertRaises(frappe.PermissionError, oral.finish_recording, name, 1)

	def test_only_registered_records_can_be_recorded(self):
		frappe.set_user(self.user)
		self.assertRaises(
			frappe.PermissionError,
			oral.start_recording,
			"Note",
			"anything",
			"audio/webm",
		)

	def test_the_record_decides_who_may_record(self):
		CONTEXT["may_record"] = False
		frappe.set_user(self.user)
		self.assertRaises(
			frappe.PermissionError,
			oral.start_recording,
			"ToDo",
			self.todo.name,
			"audio/webm",
		)

	def test_unknown_formats_are_refused(self):
		frappe.set_user(self.user)
		self.assertRaises(
			frappe.ValidationError,
			oral.start_recording,
			"ToDo",
			self.todo.name,
			"video/x-msvideo",
		)

	def test_a_recording_longer_than_allowed_is_refused(self):
		frappe.set_user(self.user)
		name = oral.start_recording("ToDo", self.todo.name, "audio/webm")["recording"]
		doc = frappe.get_doc("Oral Recording", name)
		with _settings(oral_max_minutes=1):
			self.assertRaises(
				frappe.ValidationError,
				oral._store_chunk,
				doc,
				0,
				b"x" * (60 * oral.MAX_BYTES_PER_SECOND + 1),
			)


class TestSteps(OralCase):
	def test_the_pipeline_runs_in_order_and_ends_ready(self):
		steps = ["transcribe", "diarize", "moments", "score_suggestions"]
		with _settings(), _provided(*steps):
			doc = self.record(steps=steps)
			self.assertEqual([c[1] for c in CALLS], ["transcribe"])
			self.assertEqual(doc.status, "Processing")

			oral.step_done(
				doc.name,
				"transcribe",
				{
					"segments": [
						{"start": 0, "end": 4, "text": "In the beginning"},
						{"start": 4, "end": 6, "text": "was the Word"},
						{"start": 6, "end": 9, "text": "Amen"},
					]
				},
			)
			self.assertEqual([c[1] for c in CALLS], ["transcribe", "diarize"])
			self.assertEqual(CALLS[-1][2]["expected_speakers"], 1)

			oral.step_done(doc.name, "diarize", {"labels": ["S1", "S2", "S1"]})
			self.assertEqual(sorted(c[1] for c in CALLS[2:]), ["moments", "score_suggestions"])
			self.assertEqual(CALLS[-1][2]["criteria"], [{"criterion_code": "C1"}])

			oral.step_done(
				doc.name,
				"moments",
				{"moments": [{"start": 4, "end": 6, "criterion_code": "C1", "reason": "x"}]},
			)
			oral.step_done(
				doc.name,
				"score_suggestions",
				{"criteria": [{"criterion_code": "C1", "level": "3"}]},
			)

		doc.reload()
		self.assertEqual(doc.status, "Ready")
		talk = {s.label: (s.talk_s, s.turns) for s in doc.speakers}
		self.assertEqual(talk, {"S1": (7.0, 2), "S2": (2.0, 1)})
		moment = frappe.get_doc("Oral Moment", {"recording": doc.name})
		self.assertEqual((moment.source, moment.state), ("Suggested", "Suggested"))
		self.assertEqual(moment.course_schedule, self.cs)
		self.assertTrue(
			frappe.db.exists("Oral Step Result", {"recording": doc.name, "step": "score_suggestions"})
		)

	def test_a_step_turned_off_after_recording_is_skipped(self):
		steps = ["transcribe", "moments"]
		with _settings(), _provided(*steps):
			doc = self.record(steps=steps)
		with _settings(), _provided("transcribe"):
			oral.step_done(doc.name, "transcribe", {"segments": []})
		doc.reload()
		self.assertEqual(doc.status, "Ready")
		self.assertEqual(json.loads(doc.step_state)["moments"], "skipped")
		self.assertEqual([c[1] for c in CALLS], ["transcribe"])

	def test_without_a_transcript_nothing_after_it_runs(self):
		with _settings(), _provided("moments"):
			doc = self.record(steps=["transcribe", "moments"])
		self.assertEqual(doc.status, "Ready")
		self.assertEqual(CALLS, [])

	def test_steps_the_school_turned_off_are_never_chosen(self):
		with _settings(), _provided("transcribe"), patch.object(oral, "allowed_steps", return_value=[]):
			doc = self.record(steps=["transcribe"])
		self.assertEqual(json.loads(doc.steps), [])
		self.assertEqual(doc.status, "Ready")

	def test_results_are_checked(self):
		with _settings(), _provided("transcribe", "diarize"):
			doc = self.record(steps=["transcribe", "diarize"])
			self.assertRaises(
				frappe.ValidationError,
				oral.step_done,
				doc.name,
				"transcribe",
				{"segments": [{"start": 5, "end": 1, "text": "x"}]},
			)
			self.assertRaises(
				frappe.ValidationError,
				oral.step_done,
				doc.name,
				"diarize",
				{"labels": []},
			)
			self.assertRaises(
				frappe.ValidationError,
				oral.step_done,
				doc.name,
				"consistency",
				{},
			)
			oral.step_done(doc.name, "transcribe", {"segments": []})
			self.assertRaises(
				frappe.ValidationError,
				oral.step_done,
				doc.name,
				"transcribe",
				{"segments": []},
			)
			self.assertRaises(
				frappe.ValidationError,
				oral.step_done,
				doc.name,
				"diarize",
				{"labels": ["S1"]},
			)

	def test_a_failing_provider_fails_the_recording_but_keeps_the_audio(self):
		with _settings(), _provided("transcribe", path=f"{THIS}.failing_step"):
			doc = self.record(steps=["transcribe"])
		self.assertEqual(doc.status, "Failed")
		self.assertIn("provider down", doc.error)
		self.assertTrue(doc.audio)

	def test_no_step_writes_a_grade_or_a_visible_comment(self):
		def counts():
			return (
				frappe.db.count("Rubric Score"),
				frappe.db.count("Assignment Submission Comment"),
				frappe.db.count("Grading Comment"),
			)

		before = counts()
		steps = ["transcribe", "moments", "score_suggestions", "consistency"]
		with _settings(), _provided(*steps):
			doc = self.record(steps=steps)
			oral.step_done(
				doc.name,
				"transcribe",
				{"segments": [{"start": 0, "end": 1, "text": "x"}]},
			)
			oral.step_done(doc.name, "moments", {"moments": [{"start": 0}]})
			oral.step_done(doc.name, "score_suggestions", {"criteria": []})
			oral.step_done(doc.name, "consistency", {"note": "x"})
		self.assertEqual(counts(), before)

	def test_only_a_step_suggests_a_moment(self):
		with _settings(), _provided():
			doc = self.record()
		self.assertRaises(
			frappe.ValidationError,
			frappe.get_doc(
				{
					"doctype": "Oral Moment",
					"recording": doc.name,
					"source": "Suggested",
					"start": 1,
				}
			).insert,
		)
		by_hand = frappe.get_doc({"doctype": "Oral Moment", "recording": doc.name, "start": 1}).insert()
		self.assertEqual((by_hand.source, by_hand.state), ("Instructor", "Kept"))


class TestAllowedSteps(IntegrationTestCase):
	def test_unset_checks_allow_and_an_untick_forbids(self):
		with patch.object(oral, "_settings", return_value=frappe._dict()):
			self.assertEqual(oral.allowed_steps(), list(oral.STEPS))
		with patch.object(oral, "_settings", return_value=frappe._dict(oral_step_moments=0)):
			self.assertNotIn("moments", oral.allowed_steps())


class TestTalkTime(IntegrationTestCase):
	def test_overlap_counts_for_both_and_runs_are_turns(self):
		stats = oral.talk_time(
			[
				{"start": 0, "end": 5, "speaker": "A"},
				{"start": 4, "end": 6, "speaker": "B"},
				{"start": 6, "end": 8, "speaker": "A"},
				{"start": 8, "end": 12, "speaker": "A"},
				{"start": 12, "end": 13},
			]
		)
		self.assertEqual(stats["A"], {"talk_s": 11.0, "turns": 2, "longest_turn_s": 6.0})
		self.assertEqual(stats["B"], {"talk_s": 2.0, "turns": 1, "longest_turn_s": 2.0})


class TestPermissions(OralCase):
	def test_the_students_on_it_read_it_and_no_one_else(self):
		with _settings(), _provided():
			doc = self.record()
		self.assertTrue(oral.has_permission(doc, "read", self.user))
		self.assertFalse(oral.has_permission(doc, "write", self.user))
		self.assertFalse(oral.has_permission(doc, "read", self.classmate.user))

		frappe.set_user(self.classmate.user)
		self.assertNotIn(doc.name, frappe.get_list("Oral Recording", pluck="name"))
		frappe.set_user(self.user)
		self.assertIn(doc.name, frappe.get_list("Oral Recording", pluck="name"))

	def test_moments_and_staff_results_are_not_for_students(self):
		with _settings(), _provided():
			doc = self.record()
		frappe.get_doc({"doctype": "Oral Moment", "recording": doc.name, "start": 1}).insert()
		frappe.set_user(self.user)
		self.assertFalse(frappe.has_permission("Oral Moment", "read"))
		self.assertFalse(frappe.has_permission("Oral Step Result", "read"))


class TestRetention(OralCase):
	def setUp(self):
		super().setUp()
		self.roster = _roster(self.cs, self.student.name, self.program.name)

	def _sent(self, days_ago):
		frappe.db.set_value(
			"Scheduled Course Roster",
			self.roster,
			"grades_sent_on",
			now_datetime() - timedelta(days=days_ago),
		)

	def test_audio_stays_until_grades_are_sent(self):
		with _settings(), _provided():
			doc = self.record()
			oral.delete_expired_audio()
		self.assertTrue(frappe.db.get_value("Oral Recording", doc.name, "audio"))

	def test_audio_goes_after_the_period_and_the_transcript_stays(self):
		steps = ["transcribe"]
		with _settings(), _provided(*steps):
			doc = self.record(steps=steps)
			oral.step_done(
				doc.name,
				"transcribe",
				{"segments": [{"start": 0, "end": 1, "text": "x"}]},
			)
		self._sent(days_ago=400)
		with _settings():
			oral.delete_expired_audio()
		doc.reload()
		self.assertFalse(doc.audio)
		self.assertTrue(doc.audio_deleted_on)
		self.assertEqual(len(json.loads(doc.transcript)), 1)
		self.assertFalse(
			frappe.db.exists(
				"File",
				{"attached_to_doctype": "Oral Recording", "attached_to_name": doc.name},
			)
		)

	def test_audio_stays_within_the_period(self):
		with _settings(), _provided():
			doc = self.record()
		self._sent(days_ago=10)
		with _settings():
			oral.delete_expired_audio()
		self.assertTrue(frappe.db.get_value("Oral Recording", doc.name, "audio"))

	def test_a_hold_keeps_the_audio(self):
		with _settings(), _provided():
			doc = self.record()
		self._sent(days_ago=400)
		student = frappe.get_doc("Student", self.student.name)
		student.append("student_holds", {"hold_type": "Academic", "is_active": 1})
		student.flags.ignore_permissions = True
		student.flags.ignore_mandatory = True
		student.save()
		with _settings():
			oral.delete_expired_audio()
		self.assertTrue(frappe.db.get_value("Oral Recording", doc.name, "audio"))

	def test_an_abandoned_recording_is_closed_and_its_chunks_dropped(self):
		frappe.set_user(self.user)
		name = oral.start_recording("ToDo", self.todo.name, "audio/webm")["recording"]
		oral._store_chunk(frappe.get_doc("Oral Recording", name), 0, b"a")
		frappe.set_user("Administrator")
		frappe.db.set_value("Oral Recording", name, "started_at", now_datetime() - timedelta(hours=30))
		oral.sweep_abandoned()
		self.assertEqual(frappe.db.get_value("Oral Recording", name, "status"), "Failed")
		self.assertFalse(os.path.isdir(oral._chunk_dir(name)))
