# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/100c: the oral defense of a submitted paper."""

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, get_datetime, now_datetime

from seminary.seminary import oral, oral_defense
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr082_deadlines import (
    _card,
    _roster,
    _row,
    _scale,
    _section,
)

THIS = "seminary.seminary.tests.test_adr100c_oral_defense"
FOLLOW_UPS = []


def fake_questions(recording, step, payload):
    return {
        "questions": [
            {
                "question": f"Q{i}: why?",
                "passage": "secret passage",
                "good_answer": "secret answer",
            }
            for i in range(payload["count"])
        ]
    }


def fake_transcribe(recording, step, payload):
    oral.step_done(
        recording,
        "transcribe",
        {"segments": [{"start": 0, "end": 3, "text": "Because grace."}]},
    )


def fake_follow_up(recording, step, payload):
    return {"question": FOLLOW_UPS.pop(0) if FOLLOW_UPS else None}


@contextmanager
def _steps(transcribe=True):
    steps = {
        "questions": f"{THIS}.fake_questions",
        "follow_up": f"{THIS}.fake_follow_up",
    }
    if transcribe:
        steps["transcribe"] = f"{THIS}.fake_transcribe"
    with patch.object(oral, "provided_steps", return_value=steps), patch.object(
        oral, "allowed_steps", return_value=list(oral.STEPS)
    ):
        yield


class DefenseCase(IntegrationTestCase):
    follow_up = 0
    review = 0

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        FOLLOW_UPS.clear()
        self.cs = _section(_scale())
        activity = frappe.get_doc(
            {
                "doctype": "Assignment Activity",
                "title": fx.uid("Exegesis"),
                "course": fx.uid("C"),
                "type": "Text",
                "oral_defense": 1,
                "defense_questions": 2,
                "defense_answer_s": 60,
                "defense_follow_up": self.follow_up,
                "defense_window": 3600,
                "defense_review": self.review,
                "defense_steps": '["transcribe"]',
            }
        )
        activity.flags.ignore_links = True
        activity.flags.ignore_mandatory = True
        activity.insert(ignore_permissions=True)
        self.activity = activity.name
        self.row = _row(
            self.cs, add_to_date(now_datetime(), days=7), assignment=self.activity
        )
        self.student = fx.make_student()
        _card(_roster(self.cs, self.student.name), self.row, self.student.name)

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def as_student(self, fn, *args, **kwargs):
        frappe.set_user(self.student.user)
        try:
            return fn(*args, **kwargs)
        finally:
            frappe.set_user("Administrator")

    def submit(self):
        def go():
            doc = frappe.get_doc(
                {
                    "doctype": "Assignment Submission",
                    "assignment": self.activity,
                    "course": self.cs,
                    "member": self.student.user,
                    "student": self.student.name,
                    "answer": "<p>Grace precedes faith, as Augustine argued.</p>",
                }
            )
            doc.flags.ignore_links = True
            doc.insert()
            return doc.name

        with _steps():
            self.sub = self.as_student(go)
        return self.sub

    def answer(self, current):
        """Record the current question and say it is done, as the page does."""

        def go():
            name = oral.start_recording(
                "Oral Defense Question", current["name"], "audio/webm"
            )["recording"]
            doc = frappe.get_doc("Oral Recording", name)
            oral._store_chunk(doc, 0, b"audio")
            oral.finish_recording(name, 1)
            return oral_defense.next_question(self.sub)

        with _steps():
            return self.as_student(go)


class TestQuestionsAreHidden(DefenseCase):
    def test_the_student_sees_a_question_only_when_asked_and_never_its_key(self):
        self.submit()
        state = self.as_student(oral_defense.my_defense, self.sub)
        self.assertEqual(
            (state["status"], state["count"], state["current"]), ("Open", 2, None)
        )
        self.assertNotIn("Q0", frappe.as_json(state))
        frappe.set_user(self.student.user)
        self.assertRaises(
            frappe.PermissionError,
            frappe.get_list,
            "Oral Defense Question",
            filters={"submission": self.sub},
        )
        self.assertRaises(frappe.PermissionError, oral_defense.get_defense, self.sub)
        frappe.set_user("Administrator")
        first = self.as_student(oral_defense.start, self.sub)["current"]
        self.assertEqual(set(first), {"name", "question", "follow_up"})
        self.assertNotIn(
            "secret", frappe.as_json(self.as_student(oral_defense.my_defense, self.sub))
        )

    def test_the_window_counts_from_when_the_questions_are_ready(self):
        self.submit()
        sub = frappe.db.get_value(
            "Assignment Submission",
            self.sub,
            ["defense_opened_on", "defense_due"],
            as_dict=True,
        )
        self.assertEqual(
            (
                get_datetime(sub.defense_due) - get_datetime(sub.defense_opened_on)
            ).total_seconds(),
            3600,
        )


class TestIncompleteUntilDone(DefenseCase):
    def test_the_defense_is_open_until_every_question_is_answered(self):
        self.submit()
        current = self.as_student(oral_defense.start, self.sub)["current"]
        self.assertEqual(
            frappe.db.get_value("Assignment Submission", self.sub, "defense_status"),
            "In Progress",
        )
        out = self.answer(current)
        self.assertFalse(out["done"])
        out = self.answer(out["current"])
        self.assertTrue(out["done"])
        sub = frappe.db.get_value(
            "Assignment Submission",
            self.sub,
            ["defense_status", "defense_late"],
            as_dict=True,
        )
        self.assertEqual((sub.defense_status, sub.defense_late), ("Done", 0))
        answers = frappe.get_all(
            "Oral Defense Question",
            filters={"submission": self.sub},
            pluck="answer_text",
        )
        self.assertEqual(answers, ["Because grace.", "Because grace."])

    def test_a_late_defense_makes_the_submission_late(self):
        self.submit()
        frappe.db.set_value(
            "Assignment Submission",
            self.sub,
            "defense_due",
            add_to_date(now_datetime(), hours=-2),
        )
        out = self.as_student(oral_defense.start, self.sub)
        out = self.answer(out["current"])
        self.answer(out["current"])
        late = frappe.db.get_value(
            "Assignment Submission", self.sub, ["defense_late", "late"], as_dict=True
        )
        self.assertGreaterEqual(late.defense_late, 7100)
        self.assertEqual(late.late, late.defense_late)


class TestFollowUp(DefenseCase):
    follow_up = 1

    def test_a_follow_up_comes_next_and_is_not_followed_up(self):
        FOLLOW_UPS.append("And what of works?")
        self.submit()
        out = self.as_student(oral_defense.start, self.sub)
        self.assertTrue(self.answer(out["current"]).get("wait") is None)

    def test_the_student_moves_on_after_the_budget(self):
        self.submit()
        current = self.as_student(oral_defense.start, self.sub)["current"]

        def go():
            name = oral.start_recording(
                "Oral Defense Question", current["name"], "audio/webm"
            )["recording"]
            doc = frappe.get_doc("Oral Recording", name)
            oral._store_chunk(doc, 0, b"audio")
            oral.finish_recording(name, 1)
            return name, oral_defense.next_question(self.sub)

        with _steps(transcribe=False):
            recording, out = self.as_student(go)
        self.assertEqual(out, {"wait": True})
        self.assertEqual(
            self.as_student(oral_defense.next_question, self.sub), {"wait": True}
        )
        frappe.db.set_value(
            "Oral Defense Question",
            current["name"],
            "answered_on",
            add_to_date(now_datetime(), seconds=-25),
        )
        out = self.as_student(oral_defense.next_question, self.sub)
        self.assertFalse(out["done"])
        self.assertEqual(
            frappe.db.get_value(
                "Oral Defense Question", current["name"], "follow_up_state"
            ),
            "Timed Out",
        )
        # A follow-up that arrives after the student moved on is dropped.
        FOLLOW_UPS.append("Too late?")
        frappe.db.set_value(
            "Oral Recording",
            recording,
            "transcript",
            frappe.as_json([{"start": 0, "end": 1, "text": "x"}]),
        )
        with _steps():
            oral_defense.after_step(recording, "transcribe")
        self.assertFalse(
            frappe.db.exists("Oral Defense Question", {"follow_up_of": current["name"]})
        )


class TestFollowUpAsked(DefenseCase):
    follow_up = 1

    def test_the_follow_up_is_asked_before_the_next_question(self):
        FOLLOW_UPS.append("And what of works?")
        self.submit()
        current = self.as_student(oral_defense.start, self.sub)["current"]
        out = self.answer(current)
        self.assertEqual(out["current"]["question"], "And what of works?")
        self.assertTrue(out["current"]["follow_up"])
        out = self.answer(out["current"])
        self.assertTrue(out["current"]["question"].startswith("Q1"))


class TestReview(DefenseCase):
    review = 1

    def test_a_reviewed_defense_waits_for_release_and_counts_from_it(self):
        self.submit()
        self.assertEqual(
            frappe.db.get_value("Assignment Submission", self.sub, "defense_status"),
            "Waiting for Release",
        )
        self.assertRaises(
            frappe.ValidationError, self.as_student, oral_defense.start, self.sub
        )
        staff = oral_defense.get_defense(self.sub)
        first = staff["questions"][0]
        self.assertEqual(first["good_answer"], "secret answer")
        oral_defense.save_question(self.sub, "Explain your thesis.", name=first["name"])
        self.assertEqual(oral_defense.release(self.sub), "Open")
        current = self.as_student(oral_defense.start, self.sub)["current"]
        self.assertEqual(current["question"], "Explain your thesis.")
        self.assertRaises(
            frappe.ValidationError,
            oral_defense.save_question,
            self.sub,
            "Too late",
            name=first["name"],
        )


class TestWritten(DefenseCase):
    def test_the_written_alternative_types_each_answer(self):
        self.submit()
        frappe.get_doc(
            {
                "doctype": "Student Due Date Override",
                "student": self.student.name,
                "course_assess": self.row,
                "course_schedule": self.cs,
                "written_instead": 1,
                "reason": "Speech disability (100 §9).",
            }
        ).insert(ignore_permissions=True)
        out = self.as_student(oral_defense.start, self.sub)
        self.assertTrue(self.as_student(oral_defense.my_defense, self.sub)["written"])
        out = self.as_student(
            oral_defense.answer_in_writing,
            self.sub,
            out["current"]["name"],
            "Grace first.",
        )
        out = self.as_student(
            oral_defense.answer_in_writing,
            self.sub,
            out["current"]["name"],
            "Then faith.",
        )
        self.assertTrue(out["done"])


class TestByHand(DefenseCase):
    def test_without_a_questions_step_the_instructor_writes_them_and_it_opens(self):
        def go():
            doc = frappe.get_doc(
                {
                    "doctype": "Assignment Submission",
                    "assignment": self.activity,
                    "course": self.cs,
                    "member": self.student.user,
                    "student": self.student.name,
                    "answer": "<p>A paper.</p>",
                }
            )
            doc.flags.ignore_links = True
            doc.insert()
            return doc.name

        with patch.object(oral, "provided_steps", return_value={}):
            self.sub = self.as_student(go)
        self.assertEqual(
            frappe.db.get_value("Assignment Submission", self.sub, "defense_status"),
            "Waiting for Questions",
        )
        oral_defense.save_question(self.sub, "First?")
        oral_defense.save_question(self.sub, "Second?")
        rows = oral_defense.get_defense(self.sub)["questions"]
        self.assertEqual(
            [(r.question, r.position) for r in rows], [("First?", 10), ("Second?", 20)]
        )
        self.assertEqual(
            frappe.db.get_value("Assignment Submission", self.sub, "defense_status"),
            "Open",
        )
