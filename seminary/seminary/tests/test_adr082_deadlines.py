# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/082: a student's own due dates, the cut-off, and late deductions."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, get_datetime, now_datetime

from seminary.seminary import deadlines
from seminary.seminary.tests import cohort_fixtures as fx


def _scale(kind="Points"):
    doc = frappe.get_doc(
        {
            "doctype": "Grading Scale",
            "name": fx.uid("GS"),
            "grading_scale_name": fx.uid("GS"),
            "grscale_type": kind,
            "maxnumgrade": 100,
        }
    )
    doc.db_insert()
    return doc.name


def _section(scale, **policy):
    cs = frappe.get_doc(
        {
            "doctype": "Course Schedule",
            "name": fx.uid("CS"),
            "workflow_state": "Grading",
            "open_ended": 1,
            "gradesc_cs": scale,
            "maxnumgrade": 100,
            **policy,
        }
    )
    cs.db_insert()
    return cs.name


def _row(cs, due, kind="Assignment", **values):
    row = frappe.get_doc(
        {
            "doctype": "Scheduled Course Assess Criteria",
            "name": fx.uid("SCAC"),
            "parent": cs,
            "parenttype": "Course Schedule",
            "parentfield": "courseassescrit_sc",
            "title": fx.uid("Essay"),
            "type": kind,
            "weight_scac": 100,
            "due_date": due,
            **values,
        }
    )
    row.db_insert()
    return row.name


def _roster(cs, student):
    doc = frappe.get_doc(
        {
            "doctype": "Scheduled Course Roster",
            "name": f"{cs}-{student}",
            "course_sc": cs,
            "student": student,
            "stuname_roster": student,
            "active": 1,
            "audit_bool": 0,
        }
    )
    doc.db_insert()
    return doc.name


def _card(roster, row, student):
    doc = frappe.get_doc(
        {
            "doctype": "Course Assess Results Detail",
            "name": frappe.generate_hash(length=10),
            "parent": roster,
            "parenttype": "Scheduled Course Roster",
            "parentfield": "stdroster_grade",
            "assessment_criteria": row,
            "student_card": student,
            "maximum_score": 100,
        }
    )
    doc.db_insert()
    return doc.name


def _graded_assignment(cs, row, student, member, submitted_on, percentage):
    doc = frappe.get_doc(
        {
            "doctype": "Assignment Submission",
            "name": fx.uid("ASUB"),
            "course": cs,
            "course_assess": row,
            "student": student,
            "member": member,
            "status": "Graded",
            "grade": percentage,
            "percentage": percentage,
            "submitted_on": submitted_on,
        }
    )
    doc.db_insert()
    return frappe.get_doc("Assignment Submission", doc.name)


POLICY = {
    "late_policy_enabled": 1,
    "late_deduction": 10,
    "late_interval": "Day",
    "late_grace_minutes": 15,
    "late_floor": 50,
    "missing_reply_deduction": 5,
}


class ADR082Case(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.student = fx.make_student()
        self.scale = _scale()
        self.cs = _section(self.scale, **POLICY)
        self.due = get_datetime("2026-03-02 23:59:00")
        self.row = _row(self.cs, self.due)
        self.roster = _roster(self.cs, self.student.name)
        self.card = _card(self.roster, self.row, self.student.name)

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def override(self, **values):
        return frappe.get_doc(
            {
                "doctype": "Student Due Date Override",
                "course_schedule": self.cs,
                "course_assess": self.row,
                "student": self.student.name,
                "reason": "Hospital stay",
                **values,
            }
        ).insert()


class TestDeduction(ADR082Case):
    def pol(self):
        return deadlines.policy(self.cs)

    def test_grace_period_is_not_late(self):
        at = add_to_date(self.due, minutes=15)
        self.assertEqual(deadlines.interval_deduction(self.pol(), self.due, at), 0)

    def test_every_started_day_costs_a_step(self):
        at = add_to_date(self.due, minutes=16)
        self.assertEqual(deadlines.interval_deduction(self.pol(), self.due, at), 10)
        at = add_to_date(self.due, days=2, minutes=1)
        self.assertEqual(deadlines.interval_deduction(self.pol(), self.due, at), 30)

    def test_hourly_interval(self):
        frappe.db.set_value("Course Schedule", self.cs, "late_interval", "Hour")
        at = add_to_date(self.due, hours=3)
        self.assertEqual(deadlines.interval_deduction(self.pol(), self.due, at), 30)

    def test_no_policy_on_a_descriptive_scale(self):
        frappe.db.set_value(
            "Course Schedule", self.cs, "gradesc_cs", _scale("Descriptive")
        )
        self.assertIsNone(self.pol())

    def test_card_holds_the_score_less_the_deduction_with_a_floor(self):
        sub = _graded_assignment(
            self.cs,
            self.row,
            self.student.name,
            self.student.user,
            add_to_date(self.due, days=1, hours=1),
            90,
        )
        card = frappe.get_doc("Course Assess Results Detail", self.card)
        deadlines.apply_to_card(card, sub)
        self.assertEqual(
            (card.late_base_card, card.late_deduction_card, card.rawscore_card),
            (90, 20, 70),
        )

        late = _graded_assignment(
            self.cs,
            self.row,
            self.student.name,
            self.student.user,
            add_to_date(self.due, days=9),
            80,
        )
        deadlines.apply_to_card(card, late)
        self.assertEqual(card.rawscore_card, 50)  # floor, not 0

        poor = _graded_assignment(
            self.cs,
            self.row,
            self.student.name,
            self.student.user,
            add_to_date(self.due, days=9),
            40,
        )
        deadlines.apply_to_card(card, poor)
        self.assertEqual(card.rawscore_card, 40)  # already below the floor

    def test_exempt_row_and_extra_credit_take_nothing(self):
        frappe.db.set_value(
            "Scheduled Course Assess Criteria", self.row, "late_policy_exempt", 1
        )
        sub = _graded_assignment(
            self.cs,
            self.row,
            self.student.name,
            self.student.user,
            add_to_date(self.due, days=3),
            90,
        )
        self.assertEqual(deadlines.computed_deduction(sub), 0)

    def test_an_override_moves_the_due_date(self):
        self.override(due_date=add_to_date(self.due, days=5))
        sub = _graded_assignment(
            self.cs,
            self.row,
            self.student.name,
            self.student.user,
            add_to_date(self.due, days=3),
            90,
        )
        self.assertEqual(deadlines.computed_deduction(sub), 0)

    def test_instructor_waives_the_deduction(self):
        _graded_assignment(
            self.cs,
            self.row,
            self.student.name,
            self.student.user,
            add_to_date(self.due, days=1, hours=1),
            90,
        )
        with self.assertRaises(frappe.ValidationError):
            deadlines.set_late_adjustment(self.card, 0, reason="")
        out = deadlines.set_late_adjustment(self.card, 0, reason="Power cut")
        self.assertEqual((out["rawscore_card"], out["late_deduction_card"]), (90, 0))
        out = deadlines.set_late_adjustment(self.card, None)
        self.assertEqual(out["rawscore_card"], 70)


class TestRefresh(ADR082Case):
    def priced(self):
        sub = _graded_assignment(
            self.cs,
            self.row,
            self.student.name,
            self.student.user,
            add_to_date(self.due, days=1, hours=1),
            90,
        )
        from seminary.seminary.api import quizresult_to_card

        quizresult_to_card(sub, None)
        return frappe.db.get_value(
            "Course Assess Results Detail", self.card, "rawscore_card"
        )

    def test_an_override_reprices_the_card(self):
        self.assertEqual(self.priced(), 70)
        self.override(due_date=add_to_date(self.due, days=3))
        self.assertEqual(
            frappe.db.get_value(
                "Course Assess Results Detail", self.card, "rawscore_card"
            ),
            90,
        )

    def test_sent_grades_are_frozen(self):
        self.assertEqual(self.priced(), 70)
        frappe.db.set_value("Scheduled Course Roster", self.roster, "active", 0)
        self.override(due_date=add_to_date(self.due, days=3))
        self.assertEqual(
            frappe.db.get_value(
                "Course Assess Results Detail", self.card, "rawscore_card"
            ),
            70,
        )

    def test_a_grade_typed_in_the_gradebook_is_left_alone(self):
        self.assertEqual(self.priced(), 70)
        frappe.db.set_value(
            "Course Assess Results Detail", self.card, "rawscore_card", 77
        )
        self.override(due_date=add_to_date(self.due, days=3))
        self.assertEqual(
            frappe.db.get_value(
                "Course Assess Results Detail", self.card, "rawscore_card"
            ),
            77,
        )


class TestCutoff(ADR082Case):
    def submission(self):
        return frappe.get_doc(
            {
                "doctype": "Assignment Submission",
                "course": self.cs,
                "course_assess": self.row,
                "student": self.student.name,
                "member": self.student.user,
                "answer": "My essay",
            }
        )

    def test_student_is_refused_after_the_cutoff(self):
        frappe.db.set_value(
            "Scheduled Course Assess Criteria",
            self.row,
            "cutoff_date",
            add_to_date(now_datetime(), hours=-1),
        )
        frappe.set_user(self.student.user)
        with self.assertRaises(frappe.ValidationError):
            deadlines.guard_submission(self.submission())

    def test_an_override_reopens_it_and_records_lateness(self):
        frappe.db.set_value(
            "Scheduled Course Assess Criteria",
            self.row,
            {
                "cutoff_date": add_to_date(now_datetime(), hours=-1),
                "due_date": add_to_date(now_datetime(), hours=-2),
            },
        )
        self.override(cutoff_date=add_to_date(now_datetime(), days=2))
        frappe.set_user(self.student.user)
        doc = self.submission()
        deadlines.guard_submission(doc)
        self.assertTrue(doc.submitted_on)
        self.assertGreaterEqual(doc.late, 7000)

    def test_staff_saving_a_grade_is_not_refused(self):
        frappe.db.set_value(
            "Scheduled Course Assess Criteria",
            self.row,
            "cutoff_date",
            add_to_date(now_datetime(), hours=-1),
        )
        deadlines.guard_submission(self.submission())  # Administrator


class TestOverride(ADR082Case):
    def test_needs_something_to_change(self):
        with self.assertRaises(frappe.ValidationError):
            self.override()

    def test_one_per_student_and_assessment(self):
        self.override(extra_minutes=30)
        with self.assertRaises(frappe.ValidationError):
            self.override(extra_attempts=1)

    def test_cutoff_before_due_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            self.override(cutoff_date=add_to_date(self.due, days=-1))

    def test_student_not_on_roster_is_refused(self):
        other = fx.make_student()
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Student Due Date Override",
                    "course_assess": self.row,
                    "student": other.name,
                    "due_date": self.due,
                    "reason": "x",
                }
            ).insert()


class TestDiscussionReplies(ADR082Case):
    def test_missing_replies_cost_each(self):
        activity = frappe.get_doc(
            {
                "doctype": "Discussion Activity",
                "discussion_name": fx.uid("Disc"),
                "post_before": 1,
                "min_replies_required": 2,
            }
        ).insert()
        row = _row(
            self.cs,
            self.due,
            kind="Discussion",
            discussion=activity.name,
            replies_due_date=add_to_date(self.due, days=3),
        )
        sub = frappe._dict(
            doctype="Discussion Submission",
            course_assess=row,
            student=self.student.name,
            creation=add_to_date(self.due, hours=-1),
        )
        # Initial post on time, both replies missing: 2 x 5.
        self.assertEqual(deadlines.computed_deduction(sub), 10)
        self.assertTrue(deadlines.effective(row, self.student.name).replies_due_date)


class TestTemplateImport(ADR082Case):
    def test_policy_is_copied_and_dates_are_not(self):
        from seminary.seminary.doctype.course_schedule.course_schedule import (
            _SCAC_COPYABLE_FIELDS,
            _copy_late_policy,
        )

        target = _section(self.scale)
        _copy_late_policy(self.cs, target)
        self.assertEqual(
            frappe.db.get_value("Course Schedule", target, "late_deduction"), 10
        )
        self.assertIn("late_policy_exempt", _SCAC_COPYABLE_FIELDS)
        self.assertNotIn("cutoff_date", _SCAC_COPYABLE_FIELDS)
