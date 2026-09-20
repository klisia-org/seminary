# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p009 S11: the grade mapping as the SPA reaches it (§2.12).

S10 built the passback and left the link Desk-only. These are the tests for the
two endpoints the picker calls, and the question they answer is the one the
picker makes newly askable: **can an instructor name a criterion that is not
theirs?** The link is a write capability into a gradebook, so it is scoped the
same way every other course write is -- and scoping it in the UI would not be
scoping it at all.
"""

import frappe

from seminary.scorm import grades
from seminary.seminary.tests.test_p009_grades import _PassbackCase


class TestP009Mapping(_PassbackCase):
    """Reuses S10's section, roster, criterion, gradebook cell and SCORM lesson."""

    def _staff(self):
        frappe.set_user("Administrator")

    # ------------------------------------------------------------- the listing

    def test_staff_see_their_own_sections_criteria_and_the_current_mapping(self):
        self._staff()
        payload = grades.criteria_for_lesson(self.lesson)
        self.assertEqual(payload["course"], self.course)
        self.assertIsNone(payload["current"])
        self.assertIn(self.criteria, [row["name"] for row in payload["criteria"]])

    def test_every_criterion_offered_belongs_to_this_section(self):
        """The picker's list and the setter's gate are the same list."""
        self._staff()
        for row in grades.criteria_for_lesson(self.lesson)["criteria"]:
            self.assertEqual(
                frappe.db.get_value(
                    "Scheduled Course Assess Criteria", row["name"], "parent"
                ),
                self.course,
            )

    # ---------------------------------------------------------------- the gate

    def test_a_student_cannot_read_the_mapping(self):
        frappe.set_user(self.student)
        with self.assertRaises(frappe.PermissionError):
            grades.criteria_for_lesson(self.lesson)

    def test_a_student_cannot_set_the_mapping(self):
        frappe.set_user(self.student)
        with self.assertRaises(frappe.PermissionError):
            grades.set_criteria(self.lesson, self.criteria)
        self.assertIsNone(
            frappe.db.get_value(
                "Course Lesson", self.lesson, "scorm_assessment_criteria"
            )
        )

    def test_a_lesson_that_does_not_exist_is_refused_like_one_you_may_not_see(self):
        """Not `DoesNotExistError`: answering "no such lesson" to a caller who
        would have been refused anyway turns this into a way to probe which
        lessons exist."""
        self._staff()
        with self.assertRaises(frappe.PermissionError):
            grades.criteria_for_lesson("does-not-exist-" + frappe.generate_hash(8))

    # ------------------------------------------------------- the scoping rule

    def test_a_criterion_from_another_section_is_refused(self):
        from seminary.seminary.tests.test_p007_docperms import _any_course_schedule

        _mine, other = _any_course_schedule()
        self.assertNotEqual(other.name, self.course)
        foreign = self._criterion_on(other.name)

        self._staff()
        with self.assertRaises(frappe.PermissionError):
            grades.set_criteria(self.lesson, foreign)
        self.assertIsNone(
            frappe.db.get_value(
                "Course Lesson", self.lesson, "scorm_assessment_criteria"
            )
        )

    def test_a_criterion_that_does_not_exist_is_refused(self):
        self._staff()
        with self.assertRaises(frappe.DoesNotExistError):
            grades.set_criteria(self.lesson, "nope-" + frappe.generate_hash(8))

    def _criterion_on(self, course):
        existing = frappe.db.get_value(
            "Scheduled Course Assess Criteria",
            {"parent": course, "title": "SCORM foreign"},
            "name",
        )
        if existing:
            return existing
        criteria = frappe.db.get_value(
            "Assessment Criteria", {"name": ["like", "%"]}, "name"
        )
        row = frappe.get_doc(
            {
                "doctype": "Scheduled Course Assess Criteria",
                "assesscriteria_scac": criteria,
                "parent": course,
                "parenttype": "Course Schedule",
                "parentfield": "courseassescrit_sc",
                "title": "SCORM foreign",
                "type": "Quiz",
                "weight_scac": 10,
            }
        )
        row.flags.ignore_permissions = True
        row.insert()
        return row.name

    # ------------------------------------------------------------ the round trip

    def test_setting_and_clearing_the_mapping(self):
        self._staff()
        self.assertTrue(grades.set_criteria(self.lesson, self.criteria)["ok"])
        self.assertEqual(
            frappe.db.get_value(
                "Course Lesson", self.lesson, "scorm_assessment_criteria"
            ),
            self.criteria,
        )
        self.assertEqual(
            grades.criteria_for_lesson(self.lesson)["current"], self.criteria
        )

        grades.set_criteria(self.lesson, "")
        self.assertFalse(
            frappe.db.get_value(
                "Course Lesson", self.lesson, "scorm_assessment_criteria"
            )
        )

    def test_a_mapping_set_through_the_endpoint_is_the_one_passback_reads(self):
        """The half the two halves have to agree on: the picker writes the field
        `push_from_attempt` looks up, and a pass then lands in the cell."""
        self._staff()
        grades.set_criteria(self.lesson, self.criteria)

        frappe.set_user(self.student)
        self.assertTrue(self._pass("80")["reported"])

        cell = self._cell()
        self.assertAlmostEqual(cell.rawscore_card, 80.0)
        self.assertTrue(cell.graded_card)
        self.assertTrue(cell.scorm_reported_card)
