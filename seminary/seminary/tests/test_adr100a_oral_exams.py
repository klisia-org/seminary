# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""ADR 100a: oral answers in exams, and the written alternative (100 §9)."""

import json
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import oral, oral_exams
from seminary.seminary.doctype.exam_submission.exam_submission import save_exam_draft
from seminary.seminary.doctype.exam_submission.test_p006_exam_submission import (
    _without_dangling_fetch,
)
from seminary.seminary.tests import cohort_fixtures as fx

THIS = "seminary.seminary.tests.test_adr100a_oral_exams"
CALLS = []


def fake_step(recording, step, payload):
    CALLS.append((recording, step, payload))


@contextmanager
def _provided(*steps):
    with patch.object(
        oral, "provided_steps", return_value={s: f"{THIS}.fake_step" for s in steps}
    ), patch.object(
        oral,
        "_settings",
        return_value=frappe._dict(oral_max_minutes=60, oral_audio_retention_days=365),
    ):
        yield


def _exam(modes, takes=1, steps=("transcribe",)):
    doc = frappe.get_doc(
        {
            "doctype": "Exam Activity",
            "title": fx.uid("ADR100a Exam"),
            "oral_steps": json.dumps(list(steps)),
            "questions": [
                {
                    "question": f"ADR100A-OQ-{i}",
                    "points": 1,
                    "response_mode": mode,
                    "takes": takes,
                    "question_detail": f"<p>Question {i}</p>",
                }
                for i, mode in enumerate(modes)
            ],
        }
    )
    doc.flags.ignore_links = True
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    rows = frappe.get_all(
        "Exam Question", {"parent": doc.name}, pluck="name", order_by="idx"
    )
    return doc.name, rows


class OralExamCase(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        CALLS.clear()
        self.student = fx.make_student()
        self.user = self.student.user
        self.classmate = fx.make_student()

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def draft(self, exam, questions, answers=None, submission=None):
        frappe.set_user(self.user)
        payload = json.dumps(
            [{"question": q, "answer": (answers or {}).get(q, "")} for q in questions]
        )
        with (
            patch(
                "seminary.seminary.utils.user_is_enrolled_in_course", return_value=True
            ),
            _without_dangling_fetch(),
        ):
            doc = save_exam_draft(exam, None, None, payload, 0, submission)
        frappe.set_user("Administrator")
        frappe.db.set_value("Exam Submission", doc.name, "student", self.student.name)
        return doc.name, {r.question: r.name for r in doc.result}

    def take(self, row, chunks=(b"one", b"two")):
        frappe.set_user(self.user)
        name = oral.start_recording("Exam Question Result", row, "audio/webm")[
            "recording"
        ]
        doc = frappe.get_doc("Oral Recording", name)
        for i, chunk in enumerate(chunks):
            oral._store_chunk(doc, i, chunk + name.encode())
        oral.finish_recording(name, len(chunks))
        frappe.set_user("Administrator")
        return name


class TestOralAnswers(OralExamCase):
    def test_the_transcript_becomes_the_answer(self):
        exam, (q,) = _exam(["Oral"])
        sub, rows = self.draft(exam, [q])
        with _provided("transcribe"):
            rec = self.take(rows[q])
            self.assertEqual([c[1] for c in CALLS], ["transcribe"])
            oral.step_done(
                rec,
                "transcribe",
                {
                    "segments": [
                        {"start": 0, "end": 2, "text": "Grace <b>alone</b>"},
                        {"start": 2, "end": 4, "text": "through faith"},
                    ]
                },
            )
        row = frappe.db.get_value(
            "Exam Question Result",
            rows[q],
            ["answer", "oral_recording", "takes_used"],
            as_dict=True,
        )
        self.assertEqual(row.oral_recording, rec)
        self.assertEqual(row.takes_used, 1)
        self.assertEqual(
            row.answer, "<p>Grace &lt;b&gt;alone&lt;/b&gt;</p><p>through faith</p>"
        )
        self.assertEqual(
            frappe.db.get_value("Oral Recording", rec, "course_schedule"), None
        )

    def test_a_later_draft_save_does_not_erase_the_transcript(self):
        exam, (q,) = _exam(["Oral"])
        sub, rows = self.draft(exam, [q])
        with _provided("transcribe"):
            rec = self.take(rows[q])
            oral.step_done(
                rec,
                "transcribe",
                {"segments": [{"start": 0, "end": 1, "text": "Amen"}]},
            )
        self.draft(exam, [q], answers={q: ""}, submission=sub)
        self.assertEqual(
            frappe.db.get_value("Exam Question Result", rows[q], "answer"),
            "<p>Amen</p>",
        )

    def test_takes_are_counted_and_the_last_one_is_graded(self):
        exam, (q,) = _exam(["Oral"], takes=2)
        sub, rows = self.draft(exam, [q])
        with _provided():
            first = self.take(rows[q])
            second = self.take(rows[q])
            frappe.set_user(self.user)
            self.assertRaises(
                frappe.PermissionError,
                oral.start_recording,
                "Exam Question Result",
                rows[q],
                "audio/webm",
            )
        self.assertNotEqual(first, second)
        self.assertEqual(
            frappe.db.get_value("Exam Question Result", rows[q], "oral_recording"),
            second,
        )

    def test_one_take_by_default(self):
        exam, (q,) = _exam(["Oral"], takes=0)
        sub, rows = self.draft(exam, [q])
        with _provided():
            self.take(rows[q])
            frappe.set_user(self.user)
            self.assertRaises(
                frappe.PermissionError,
                oral.start_recording,
                "Exam Question Result",
                rows[q],
                "audio/webm",
            )

    def test_written_questions_and_other_students_cannot_be_recorded(self):
        exam, (written, spoken) = _exam(["Written", "Oral"])
        sub, rows = self.draft(exam, [written, spoken])
        frappe.set_user(self.user)
        self.assertRaises(
            frappe.PermissionError,
            oral.start_recording,
            "Exam Question Result",
            rows[written],
            "audio/webm",
        )
        frappe.set_user(self.classmate.user)
        self.assertRaises(
            frappe.PermissionError,
            oral.start_recording,
            "Exam Question Result",
            rows[spoken],
            "audio/webm",
        )

    def test_a_submitted_exam_cannot_be_recorded(self):
        exam, (q,) = _exam(["Oral"])
        sub, rows = self.draft(exam, [q])
        frappe.db.set_value("Exam Submission", sub, "status", "Not Graded")
        frappe.set_user(self.user)
        self.assertRaises(
            frappe.PermissionError,
            oral.start_recording,
            "Exam Question Result",
            rows[q],
            "audio/webm",
        )

    def test_written_instead_turns_oral_questions_into_written_ones(self):
        exam, (q,) = _exam(["Oral"])
        sub, rows = self.draft(exam, [q])
        frappe.db.set_value("Exam Submission", sub, "course_assess", "ZZT-SCAC")
        ov = frappe.get_doc(
            {
                "doctype": "Student Due Date Override",
                "course_assess": "ZZT-SCAC",
                "course_schedule": "ZZT-CS",
                "student": self.student.name,
                "written_instead": 1,
            }
        )
        ov.db_insert()
        frappe.set_user(self.user)
        self.assertRaises(
            frappe.PermissionError,
            oral.start_recording,
            "Exam Question Result",
            rows[q],
            "audio/webm",
        )
        state = oral_exams.my_oral_state(sub)["questions"]
        self.assertEqual((state[q]["oral"], state[q]["mode"]), (False, "Written"))


class TestStateAndPlayer(OralExamCase):
    def test_the_student_sees_their_own_state_only(self):
        exam, (written, spoken) = _exam(["Written", "Student chooses"], takes=2)
        sub, rows = self.draft(exam, [written, spoken])
        frappe.set_user(self.user)
        result = oral_exams.my_oral_state(sub)
        self.assertEqual(result["notice"]["retention_days"], 365)
        state = result["questions"]
        self.assertFalse(state[written]["oral"])
        self.assertTrue(state[spoken]["oral"])
        self.assertEqual(state[spoken]["takes"], 2)
        self.assertEqual(state[spoken]["row"], rows[spoken])
        frappe.set_user(self.classmate.user)
        self.assertRaises(frappe.PermissionError, oral_exams.my_oral_state, sub)

    def test_the_player_shows_moments_to_staff_only(self):
        exam, (q,) = _exam(["Oral"])
        sub, rows = self.draft(exam, [q])
        with _provided():
            rec = self.take(rows[q])
        moment = oral.add_moment(rec, 1.5, 3, note="good")

        frappe.set_user(self.user)
        mine = oral.get_recording(rec)
        self.assertFalse(mine["is_staff"])
        self.assertEqual(mine["moments"], [])
        self.assertTrue(mine["audio"])
        self.assertRaises(frappe.PermissionError, oral.add_moment, rec, 1)
        self.assertRaises(
            frappe.PermissionError, oral.set_moment_state, moment, "Dismissed"
        )

        frappe.set_user(self.classmate.user)
        self.assertRaises(frappe.PermissionError, oral.get_recording, rec)

        frappe.set_user("Administrator")
        staff = oral.get_recording(rec)
        self.assertEqual([m.note for m in staff["moments"]], ["good"])
        oral.set_moment_state(moment, "Dismissed")
        self.assertEqual(oral.get_recording(rec)["moments"], [])
