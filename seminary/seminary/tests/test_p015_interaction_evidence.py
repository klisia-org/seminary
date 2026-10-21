# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""privatedocs p015: who graded and when, the course of a reply, one projected
grade, and the Students tab."""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_to_date, now_datetime

from seminary.seminary import comms, course_students, grade_projection
from seminary.seminary.patches import p015_fill_graded_by, p015_reply_course_reference
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr082_deadlines import _card, _roster, _row, _section


def _scale_with_intervals():
    scale = frappe.get_doc(
        {
            "doctype": "Grading Scale",
            "name": fx.uid("GS"),
            "grading_scale_name": fx.uid("GS"),
            "grscale_type": "Points",
            "maxnumgrade": 100,
        }
    )
    scale.db_insert()
    for code, threshold, grade_pass in (
        ("A", 90, "Pass"),
        ("C", 70, "Pass"),
        ("F", 0, "Fail"),
    ):
        frappe.get_doc(
            {
                "doctype": "Grading Scale Interval",
                "name": frappe.generate_hash(length=10),
                "parent": scale.name,
                "parenttype": "Grading Scale",
                "parentfield": "intervals",
                "grade_code": code,
                "threshold": threshold,
                "grade_pass": grade_pass,
            }
        ).db_insert()
    return scale.name


def _insert(values):
    doc = frappe.get_doc(values)
    doc.name = doc.name or fx.uid(values["doctype"][:4])
    doc.db_insert()
    return doc.name


def _log(**values):
    return _insert(
        {
            "doctype": "Communication Log",
            "name": frappe.generate_hash(length=12),
            "direction": "Outbound",
            "status": "Sent",
            "channel": "In-App",
            "message": "<p>hi</p>",
            **values,
        }
    )


class P015Case(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.scale = _scale_with_intervals()
        self.cs = _section(self.scale)
        self.student = fx.make_student()
        self.roster = _roster(self.cs, self.student.name)
        frappe.db.set_value(
            "Scheduled Course Roster", self.roster, "stuemail_rc", self.student.user
        )

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()
        super().tearDown()


# --------------------------------------------------------------- §1 graded by


class TestGradedBy(P015Case):
    def _assignment(self, status="Not Graded"):
        return _insert(
            {
                "doctype": "Assignment Submission",
                "name": fx.uid("ASUB"),
                "course": self.cs,
                "student": self.student.name,
                "member": self.student.user,
                "status": status,
                "submitted_on": now_datetime(),
            }
        )

    def _discussion(self, status="Not Graded"):
        return _insert(
            {
                "doctype": "Discussion Submission",
                "name": fx.uid("DSUB"),
                "coursesc": self.cs,
                "student": self.student.name,
                "member": self.student.user,
                "status": status,
            }
        )

    def _grade(self, doctype, name, status="Graded", **extra):
        doc = frappe.get_doc(doctype, name)
        doc.status = status
        doc.update(extra)
        # Only the grading fields are under test; the activity is not.
        doc.flags.ignore_mandatory = True
        doc.save(ignore_permissions=True)
        return frappe.get_doc(doctype, name)

    def test_first_grading_is_stamped_and_never_moves(self):
        for doctype, make in (
            ("Assignment Submission", self._assignment),
            ("Discussion Submission", self._discussion),
        ):
            with self.subTest(doctype=doctype):
                name = make()
                ungraded = self._grade(doctype, name, status="Not Graded")
                self.assertIsNone(ungraded.evaluator)
                self.assertIsNone(ungraded.graded_on)

                first = self._grade(doctype, name)
                self.assertEqual(first.evaluator, "Administrator")
                self.assertTrue(first.graded_on)

                # Ungraded and regraded later, by someone else, with a client
                # trying to write the fields: the first grading stands.
                self._grade(doctype, name, status="Not Graded")
                other = fx.make_user(roles=("System Manager",)).name
                frappe.set_user(other)
                again = self._grade(
                    doctype,
                    name,
                    evaluator=other,
                    graded_on=add_days(now_datetime(), 3),
                )
                frappe.set_user("Administrator")
                self.assertEqual(again.evaluator, "Administrator")
                self.assertEqual(again.graded_on, first.graded_on)

    def test_a_client_cannot_stamp_ungraded_work(self):
        name = self._assignment()
        doc = self._grade(
            "Assignment Submission",
            name,
            status="Not Graded",
            evaluator="Guest",
            graded_on=now_datetime(),
        )
        self.assertIsNone(doc.evaluator)
        self.assertIsNone(doc.graded_on)

    def test_legacy_graded_work_is_not_restamped(self):
        name = self._assignment(status="Graded")
        doc = self._grade("Assignment Submission", name)
        self.assertIsNone(doc.graded_on)

    def test_patch_fills_from_the_first_graded_version(self):
        name = self._assignment(status="Graded")
        empty = self._discussion(status="Graded")
        grader = fx.make_user().name
        for owner, created, changed in (
            ("Administrator", "2026-01-01 08:00:00", [["comments", None, "x"]]),
            (grader, "2026-01-02 09:00:00", [["status", "Not Graded", "Graded"]]),
            (
                "Administrator",
                "2026-01-05 10:00:00",
                [["status", "Not Graded", "Graded"]],
            ),
        ):
            version = frappe.get_doc(
                {
                    "doctype": "Version",
                    "name": frappe.generate_hash(length=10),
                    "ref_doctype": "Assignment Submission",
                    "docname": name,
                    "data": json.dumps({"changed": changed}),
                    "owner": owner,
                    "creation": created,
                    "modified": created,
                }
            )
            version.db_insert()

        p015_fill_graded_by.execute()

        row = frappe.db.get_value(
            "Assignment Submission", name, ["evaluator", "graded_on"], as_dict=True
        )
        self.assertEqual(row.evaluator, grader)
        self.assertEqual(str(row.graded_on), "2026-01-02 09:00:00")
        self.assertIsNone(
            frappe.db.get_value("Discussion Submission", empty, "graded_on")
        )


# ------------------------------------------------------------ §2 reply course


class TestReplyCourse(P015Case):
    def test_reply_reference_copies_only_a_course(self):
        course_msg = _log(reference_doctype="Course Schedule", reference_name=self.cs)
        other_msg = _log(reference_doctype="Student", reference_name=self.student.name)
        plain = _log()
        self.assertEqual(
            comms._reply_reference(course_msg),
            {"reference_doctype": "Course Schedule", "reference_name": self.cs},
        )
        self.assertEqual(comms._reply_reference(other_msg), {})
        self.assertEqual(comms._reply_reference(plain), {})
        self.assertEqual(comms._reply_reference(None), {})

    def test_reply_in_conversation_keeps_the_course(self):
        original = _log(reference_doctype="Course Schedule", reference_name=self.cs)
        with patch.object(
            comms, "send_message", return_value=None
        ) as send, patch.object(comms, "mark_conversation_read"):
            comms.reply_in_conversation("someone", "Thanks", in_reply_to=original)
        kwargs = send.call_args.kwargs
        self.assertEqual(kwargs["reference_doctype"], "Course Schedule")
        self.assertEqual(kwargs["reference_name"], self.cs)
        self.assertEqual(kwargs["in_reply_to"], original)

    def test_reply_portal_message_keeps_the_course(self):
        me, them = fx.make_person("Me").name, fx.make_person("Them").name
        original = _log(
            person=me,
            triggered_by="someone@example.test",
            reference_doctype="Course Schedule",
            reference_name=self.cs,
        )
        with patch.object(comms, "_my_person", return_value=me), patch(
            "seminary.seminary.person.find_person", return_value=them
        ), patch.object(comms, "may_message", return_value=True), patch.object(
            comms, "send_message", return_value=None
        ) as send:
            comms.reply_portal_message(original, "Thanks")
        self.assertEqual(send.call_args.kwargs["reference_name"], self.cs)

    def test_patch_walks_the_thread_to_the_course(self):
        root = _log(reference_doctype="Course Schedule", reference_name=self.cs)
        first = _log(in_reply_to=root)
        second = _log(in_reply_to=first)
        elsewhere = _log(reference_doctype="Student", reference_name=self.student.name)
        stray = _log(in_reply_to=elsewhere)
        orphan = _log(in_reply_to=_log())

        p015_reply_course_reference.execute()

        for name in (first, second):
            self.assertEqual(
                frappe.db.get_value(
                    "Communication Log",
                    name,
                    ["reference_doctype", "reference_name"],
                ),
                ("Course Schedule", self.cs),
            )
        for name in (stray, orphan):
            self.assertIsNone(
                frappe.db.get_value("Communication Log", name, "reference_doctype")
            )


# ----------------------------------------------------------- §3 one projection


class TestProjection(IntegrationTestCase):
    INTERVALS = [
        {"grade_code": "A", "threshold": 90, "grade_pass": "Pass"},  # nosec B105
        {"grade_code": "C", "threshold": 70, "grade_pass": "Pass"},  # nosec B105
        {"grade_code": "F", "threshold": 0, "grade_pass": "Fail"},  # nosec B105
    ]

    def rows(self, *scores, extra=None):
        out = [
            {"rawscore_card": s, "weight_scac": w, "extracredit_scac": 0}
            for s, w in scores
        ]
        if extra is not None:
            out.append({"actualextrapt_card": extra, "extracredit_scac": 1})
        return out

    def test_current_counts_missing_work_as_zero(self):
        got = grade_projection.compute(
            self.rows((80, 50), (None, 50)), self.INTERVALS, 100
        )
        self.assertEqual(got["current"]["score"], 40)
        self.assertEqual(got["current"]["grade"], "F")
        self.assertEqual(got["current"]["grade_pass"], "Fail")

    def test_projected_fills_missing_work_with_the_average(self):
        got = grade_projection.compute(
            self.rows((80, 25), (100, 25), (0, 50), extra=200), self.INTERVALS, 100
        )
        # (80*25 + 100*25 + 90*50 + 200) / 100
        self.assertEqual(got["projected"]["score"], 92)
        self.assertEqual(got["projected"]["grade"], "A")
        # (80*25 + 100*25 + 0 + 200) / 100
        self.assertEqual(got["current"]["score"], 47)

    def test_no_projection_before_any_score(self):
        got = grade_projection.compute(
            self.rows((None, 50), (0, 50)), self.INTERVALS, 100
        )
        self.assertIsNone(got["projected"])
        self.assertIsNotNone(got["current"])
        self.assertEqual(
            grade_projection.compute([], self.INTERVALS, 100),
            {"current": None, "projected": None},
        )

    def test_rounds_half_up_like_the_portal(self):
        got = grade_projection.compute(self.rows((0.125, 100)), [], 100)
        # 0.125 * 100 / 100 = 0.125 -> 0.13 (banker's rounding would give 0.12)
        self.assertEqual(got["current"]["score"], 0.13)
        self.assertEqual(got["current"]["grade"], "")


class TestMyStatusAgrees(P015Case):
    def test_my_status_returns_the_server_grades(self):
        from seminary.seminary.utils import get_student_course_status

        row = _row(self.cs, add_days(now_datetime(), -1))
        _row(self.cs, add_days(now_datetime(), 5))
        frappe.db.set_value(
            "Scheduled Course Assess Criteria",
            {"parent": self.cs},
            "weight_scac",
            50,
        )
        card = _card(self.roster, row, self.student.name)
        frappe.db.set_value("Course Assess Results Detail", card, "rawscore_card", 60)

        frappe.set_user(self.student.user)
        status = get_student_course_status(self.cs)
        frappe.set_user("Administrator")

        expected = grade_projection.course_grade_projection(self.cs, self.student.name)
        self.assertEqual(status["current_grade"], expected["current"])
        self.assertEqual(status["projected_grade"], expected["projected"])
        self.assertEqual(status["current_grade"]["score"], 30)
        self.assertEqual(status["projected_grade"]["score"], 60)
        self.assertEqual(status["projected_grade"]["grade_pass"], "Fail")


# ------------------------------------------------------------- §4 Students tab


class TestStudentsTab(P015Case):
    def setUp(self):
        super().setUp()
        self.row = _row(self.cs, add_days(now_datetime(), -1))
        card = _card(self.roster, self.row, self.student.name)
        frappe.db.set_value("Course Assess Results Detail", card, "rawscore_card", 50)

    def students(self):
        with patch.object(course_students, "_interaction", return_value=None):
            return course_students.get_course_students(self.cs)

    def mine(self, out=None):
        out = out or self.students()
        return next(s for s in out["students"] if s["student"] == self.student.name)

    def test_waiting_work_and_its_age(self):
        old = add_to_date(now_datetime(), days=-6)
        _insert(
            {
                "doctype": "Assignment Submission",
                "name": fx.uid("ASUB"),
                "course": self.cs,
                "member": self.student.user,
                "status": "Not Graded",
                "submitted_on": old,
            }
        )
        _insert(
            {
                "doctype": "Discussion Submission",
                "name": fx.uid("DSUB"),
                "coursesc": self.cs,
                "student": self.student.name,
                "status": "Not Graded",
            }
        )
        _insert(
            {
                "doctype": "Assignment Submission",
                "name": fx.uid("ASUB"),
                "course": self.cs,
                "student": self.student.name,
                "status": "Graded",
                "submitted_on": add_to_date(now_datetime(), days=-30),
            }
        )
        row = self.mine()
        self.assertEqual(row["waiting"], 2)
        self.assertEqual(row["oldest_waiting_days"], 6)

    def test_last_activity_takes_the_latest_source(self):
        _insert(
            {
                "doctype": "Student Attendance",
                "name": fx.uid("ATT"),
                "student": self.student.name,
                "course_schedule": self.cs,
                "date": add_days(now_datetime(), -2),
                "status": "Present",
                "docstatus": 1,
            }
        )
        _insert(
            {
                "doctype": "Assignment Submission",
                "name": fx.uid("ASUB"),
                "course": self.cs,
                "student": self.student.name,
                "status": "Graded",
                "submitted_on": add_to_date(now_datetime(), days=-9),
            }
        )
        row = self.mine()
        self.assertEqual(row["days_since_activity"], 2)

        _insert(
            {
                "doctype": "SCORM Attempt",
                "name": fx.uid("SCO"),
                "member": self.student.user,
                "student": self.roster,
                "course": self.cs,
                "last_commit_on": add_to_date(now_datetime(), hours=-1),
            }
        )
        self.assertIn(self.mine()["days_since_activity"], (0, 1))

    def test_at_risk_follows_the_projection(self):
        row = self.mine()
        self.assertTrue(row["at_risk"])
        self.assertEqual(row["projected_grade"]["grade"], "F")
        self.assertEqual(
            row["projected_grade"],
            grade_projection.course_grade_projection(self.cs, self.student.name)[
                "projected"
            ],
        )

    def test_competency_sections_leave_the_column_out(self):
        with patch("seminary.seminary.cbe.framework_for", return_value="FW"):
            out = self.students()
        self.assertTrue(out["is_cbe"])
        self.assertNotIn("at_risk", self.mine(out))
        self.assertNotIn("projected_grade", self.mine(out))

    def test_attendance_alert_is_passed_through(self):
        frappe.db.set_value(
            "Scheduled Course Roster", self.roster, "attendance_alert_level", 2
        )
        self.assertEqual(self.mine()["attendance_alert_level"], 2)

    def test_inactive_students_are_left_out(self):
        frappe.db.set_value("Scheduled Course Roster", self.roster, "active", 0)
        self.assertEqual(self.students()["students"], [])

    def test_a_student_is_refused(self):
        frappe.set_user(self.student.user)
        with self.assertRaises(frappe.PermissionError):
            course_students.get_course_students(self.cs)

    def test_interaction_columns_only_when_the_hook_answers(self):
        out = self.students()
        self.assertIsNone(out["interaction"])
        self.assertNotIn("messages_waiting", self.mine(out))

        answer = {
            "summary": {
                "computed_on": "2026-10-01 00:00:00",
                "frozen": False,
                "items": [
                    {"label": "Longest gap", "value": "3 days", "flagged": False}
                ],
                "flags": [],
            },
            "students": {
                self.student.name: {
                    "last_instructor_interaction": "2026-09-30 10:00:00",
                    "messages_waiting": 2,
                }
            },
        }
        with patch.object(course_students, "_interaction", return_value=answer):
            out = course_students.get_course_students(self.cs)
        self.assertEqual(out["interaction"]["summary"], answer["summary"])
        row = self.mine(out)
        self.assertEqual(row["messages_waiting"], 2)
        self.assertEqual(row["last_instructor_interaction"], "2026-09-30 10:00:00")

    def test_hook_contract_and_failures(self):
        calls = []

        def good(course_schedule):
            calls.append(course_schedule)
            return {"summary": None, "students": {}}

        def bad(course_schedule):
            raise RuntimeError("boom")

        hooks = {"course_interaction": ["bad", "good"]}
        fns = {"bad": bad, "good": good}
        with patch(
            "seminary.seminary.utils._aretenic_enabled", return_value=True
        ), patch.object(
            course_students.frappe, "get_hooks", side_effect=lambda h: hooks.get(h, [])
        ), patch.object(
            course_students.frappe, "get_attr", side_effect=lambda f: fns[f]
        ), patch.object(
            course_students.frappe, "log_error"
        ) as log:
            got = course_students._interaction(self.cs)
        self.assertEqual(calls, [self.cs])
        self.assertEqual(got, {"summary": None, "students": {}})
        log.assert_called_once()

        with patch("seminary.seminary.utils._aretenic_enabled", return_value=False):
            self.assertIsNone(course_students._interaction(self.cs))
