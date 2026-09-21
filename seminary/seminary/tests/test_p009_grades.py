# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p009 S10: grade passback, bounded (§2.12).

The question is not "does the number arrive" but **what it takes for a number
produced by third-party code in a browser the student controls to become a
grade**. The answer is meant to be: an explicit link an instructor set, and
nothing else. These tests are what makes that answer true rather than intended.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.scorm import grades
from seminary.seminary.tests.test_p009_runtime import _CommitCase


class TestP009Percentage(IntegrationTestCase):
    """The score conversion, which has no frappe in it."""

    def _attempt(self, **values):
        return frappe._dict(
            {
                "has_score": 1,
                "score_raw": None,
                "score_min": None,
                "score_max": None,
                "score_scaled": None,
            }
            | values
        )

    def test_no_score_is_not_a_zero(self):
        self.assertIsNone(grades.percentage_for(self._attempt(has_score=0)))

    def test_a_stored_zero_is_not_a_reported_zero(self):
        """The Float columns are NOT NULL, so an attempt read back from the
        database holds 0.0 in every score field whether the package set one or
        not. Reading that as a scaled zero turned a second commit of 90/100
        into a grade of 0 -- and no single-commit test could see it, because a
        *fresh* document really does hold None."""
        stored = self._attempt(
            has_score=0, score_raw=0.0, score_min=0.0, score_max=0.0, score_scaled=0.0
        )
        self.assertIsNone(grades.percentage_for(stored))

        # ...and with a real raw score beside a defaulted scaled, raw wins.
        real = self._attempt(
            score_raw=90.0, score_min=0.0, score_max=100.0, score_scaled=0.0
        )
        self.assertEqual(grades.percentage_for(real), 90.0)

    def test_scaled_wins_and_needs_no_range(self):
        self.assertEqual(grades.percentage_for(self._attempt(score_scaled=0.75)), 75.0)

    def test_a_raw_score_is_normalised_against_the_declared_range(self):
        self.assertEqual(
            grades.percentage_for(
                self._attempt(score_raw=15, score_min=0, score_max=30)
            ),
            50.0,
        )

    def test_no_declared_range_means_out_of_a_hundred(self):
        self.assertEqual(grades.percentage_for(self._attempt(score_raw=42)), 42.0)

    def test_a_contradictory_range_falls_back_rather_than_dividing_by_zero(self):
        self.assertEqual(
            grades.percentage_for(
                self._attempt(score_raw=42, score_min=90, score_max=10)
            ),
            42.0,
        )

    def test_everything_is_clamped_to_a_percentage(self):
        self.assertEqual(grades.percentage_for(self._attempt(score_scaled=99)), 100.0)
        self.assertEqual(grades.percentage_for(self._attempt(score_scaled=-5)), 0.0)
        self.assertEqual(
            grades.percentage_for(
                self._attempt(score_raw=9999, score_min=0, score_max=10)
            ),
            100.0,
        )


class _PassbackCase(_CommitCase):
    """A section, a roster, a criterion, a gradebook cell and a SCORM lesson.

    Not a `Test*` class, for the reason `_CommitCase` is not: `test_p009_mapping`
    builds on this fixture, and subclassing a class that holds tests would run
    every one of them a second time there.
    """

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.criteria = self._criterion()
        self.card = self._card(self.criteria)
        self.lesson = frappe.db.get_value(
            "Course Lesson",
            {"chapter": self.chapter.name, "scorm_sco_identifier": "A"},
            "name",
        )
        frappe.set_user(self.student)

    def _criterion(self):
        # The SCAC autonames from (course, criteria), so a fresh one per test
        # collides on the primary key. Find or create, both ends.
        existing = frappe.db.get_value(
            "Scheduled Course Assess Criteria",
            {"parent": self.course, "title": "SCORM unit"},
            "name",
        )
        if existing:
            return existing

        criteria = frappe.db.get_value(
            "Assessment Criteria", {"name": ["like", "%"]}, "name"
        )
        if not criteria:
            doc = frappe.get_doc(
                {"doctype": "Assessment Criteria", "assessment_criteria": "ZZT SCORM"}
            )
            doc.flags.ignore_permissions = True
            doc.insert()
            criteria = doc.name

        row = frappe.get_doc(
            {
                "doctype": "Scheduled Course Assess Criteria",
                "assesscriteria_scac": criteria,
                "parent": self.course,
                "parenttype": "Course Schedule",
                "parentfield": "courseassescrit_sc",
                "title": "SCORM unit",
                "type": "Quiz",
                "weight_scac": 10,
            }
        )
        row.flags.ignore_permissions = True
        row.insert()
        return row.name

    def _card(self, criteria):
        roster = frappe.db.get_value(
            "Scheduled Course Roster",
            {"course_sc": self.course, "stuemail_rc": self.student},
            ["name", "student"],
            as_dict=True,
        )
        existing = frappe.db.get_value(
            "Course Assess Results Detail",
            {"assessment_criteria": criteria, "student_card": roster.student},
            "name",
        )
        if existing:
            frappe.db.set_value(
                "Course Assess Results Detail",
                existing,
                {"rawscore_card": 0, "graded_card": 0, "scorm_reported_card": 0},
            )
            return existing

        card = frappe.get_doc(
            {
                "doctype": "Course Assess Results Detail",
                "parent": roster.name,
                "parenttype": "Scheduled Course Roster",
                "parentfield": "stdroster_grade",
                "assessment_criteria": criteria,
                "student_card": roster.student,
                "maximum_score": 100,
            }
        )
        card.flags.ignore_permissions = True
        card.insert()
        return card.name

    def _map(self):
        frappe.db.set_value(
            "Course Lesson", self.lesson, "scorm_assessment_criteria", self.criteria
        )

    def _cell(self):
        return frappe.db.get_value(
            "Course Assess Results Detail",
            self.card,
            ["rawscore_card", "graded_card", "scorm_reported_card"],
            as_dict=True,
        )

    def _pass(self, score="80"):
        return self._commit(
            {
                "cmi.core.lesson_status": "passed",
                "cmi.core.score.raw": score,
                "cmi.core.score.min": "0",
                "cmi.core.score.max": "100",
            }
        )


class TestP009Passback(_PassbackCase):
    """The write itself, against a real roster, criterion and gradebook cell."""

    # --------------------------------------------------- the default: nothing

    def test_an_unmapped_package_reaches_no_grade(self):
        result = self._pass()
        self.assertTrue(result["stored"])
        self.assertFalse(result["reported"])
        cell = self._cell()
        self.assertEqual(cell.graded_card, 0)
        self.assertIn(cell.rawscore_card, (0, None))

    # --------------------------------------------------- the mapped behaviour

    def test_a_mapped_passing_attempt_reports_its_score(self):
        self._map()
        self.assertTrue(self._pass()["reported"])
        cell = self._cell()
        self.assertEqual(cell.rawscore_card, 80.0)
        self.assertEqual(cell.graded_card, 1)
        self.assertEqual(
            cell.scorm_reported_card, 1, "the grader cannot see where it came from"
        )

    def test_an_unfinished_attempt_reports_nothing(self):
        self._map()
        result = self._commit(
            {"cmi.core.lesson_status": "incomplete", "cmi.core.score.raw": "80"}
        )
        self.assertFalse(result["reported"])
        self.assertEqual(self._cell().graded_card, 0)

    def test_a_finished_attempt_with_no_score_reports_nothing(self):
        self._map()
        self.assertFalse(self._commit({"cmi.core.lesson_status": "passed"})["reported"])
        self.assertEqual(self._cell().graded_card, 0)

    def test_a_later_attempt_updates_the_cell_it_owns(self):
        self._map()
        self._pass("60")
        self.assertEqual(self._cell().rawscore_card, 60.0)
        self._pass("90")
        self.assertEqual(self._cell().rawscore_card, 90.0)

    # ------------------------------------------------ the instructor's number

    def test_a_grader_who_edits_the_cell_keeps_it_for_good(self):
        self._map()
        self._pass("60")

        # A grader corrects it by hand.
        frappe.db.set_value(
            "Course Assess Results Detail", self.card, "rawscore_card", 75
        )

        result = self._pass("100")
        self.assertFalse(result["reported"], "a package overwrote a grader")
        self.assertEqual(self._cell().rawscore_card, 75.0)

        # ...and stays refused, not just for one commit.
        self.assertFalse(self._pass("100")["reported"])
        self.assertEqual(self._cell().rawscore_card, 75.0)

    def test_a_cell_graded_by_something_else_is_never_taken_over(self):
        self._map()
        frappe.db.set_value(
            "Course Assess Results Detail",
            self.card,
            {"rawscore_card": 55, "graded_card": 1},
        )
        self.assertFalse(self._pass("100")["reported"])
        self.assertEqual(self._cell().rawscore_card, 55.0)

    # ------------------------------------------------------------ competency

    def test_a_competency_section_is_left_to_its_own_rollup(self):
        # The same cell holds a level (1-4) there, written by cbe; a percentage
        # would be read back as a level (ADR 065 §7).
        self._map()
        with patch("seminary.seminary.cbe.framework_for", return_value="ZZT-framework"):
            result = self._pass("100")
        self.assertFalse(result["reported"])
        self.assertEqual(self._cell().graded_card, 0)

    # ---------------------------------------------------------------- review

    def test_a_staff_preview_reports_nothing(self):
        from seminary.scorm import launch as launch_module
        from seminary.scorm import runtime

        self._map()
        with patch.object(runtime, "_mode", return_value=launch_module.MODE_REVIEW):
            result = runtime.commit(
                self.token,
                "A",
                {"cmi.core.lesson_status": "passed", "cmi.core.score.raw": "100"},
            )
        self.assertFalse(result.get("reported", False))
        self.assertEqual(self._cell().graded_card, 0)
