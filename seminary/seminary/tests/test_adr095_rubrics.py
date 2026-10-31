# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/095: rubrics on school scales, versioned per activity."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import rubrics
from seminary.seminary.tests import cohort_fixtures as fx


def _grading_scale(kind="Points", maximum=10):
    doc = frappe.get_doc(
        {
            "doctype": "Grading Scale",
            "name": fx.uid("GS"),
            "grading_scale_name": fx.uid("GS"),
            "grscale_type": kind,
            "maxnumgrade": maximum,
        }
    )
    doc.db_insert()
    return doc.name


def _rubric_scale(name=None, default=0):
    return frappe.get_doc(
        {
            "doctype": "Rubric Scale",
            "scale_name": name or fx.uid("RS"),
            "is_default": default,
            "levels": [
                {
                    "label": "Excellent",
                    "percent": 100,
                    "description": "Beyond the brief",
                },
                {
                    "label": "Proficient",
                    "percent": 85,
                    "meets_expectations": 1,
                    "description": "Does what is asked",
                },
                {"label": "Developing", "percent": 70, "description": "Partly there"},
                {"label": "Beginning", "percent": 50, "description": "Not yet"},
            ],
        }
    ).insert()


def _graded(sub, level):
    return [{"criterion_code": c, "level": level} for c in sub]


class ADR095Case(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.scale = _rubric_scale()
        self.grading_scale = _grading_scale()
        self.course = fx.uid("CRS")
        frappe.get_doc(
            {
                "doctype": "Course",
                "name": self.course,
                "course": self.course,
                "coursecode": self.course,
            }
        ).db_insert()
        self.activity = frappe.get_doc(
            {
                "doctype": "Assignment Activity",
                "title": "Exegetical paper",
                "type": "Text",
                "course": self.course,
            }
        ).insert()
        self.cs = frappe.get_doc(
            {
                "doctype": "Course Schedule",
                "name": fx.uid("CS"),
                "workflow_state": "Grading",
                "open_ended": 1,
                "gradesc_cs": self.grading_scale,
                "maxnumgrade": 10,
            }
        )
        self.cs.db_insert()
        self.row = frappe.get_doc(
            {
                "doctype": "Scheduled Course Assess Criteria",
                "name": fx.uid("SCAC"),
                "parent": self.cs.name,
                "parenttype": "Course Schedule",
                "parentfield": "courseassescrit_sc",
                "title": "Paper",
                "type": "Assignment",
                "assignment": self.activity.name,
                "weight_scac": 100,
            }
        )
        self.row.db_insert()
        self.student = fx.make_student()
        self.sub = frappe.get_doc(
            {
                "doctype": "Assignment Submission",
                "name": fx.uid("ASUB"),
                "assignment": self.activity.name,
                "course": self.cs.name,
                "course_assess": self.row.name,
                "student": self.student.name,
                "member": self.student.user,
                "type": "Text",
                "answer": "My paper",
                "status": "Not Graded",
            }
        )
        self.sub.db_insert()

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def make_rubric(self):
        return rubrics.save_rubric(
            "Assignment Activity",
            self.activity.name,
            self.scale.name,
            [
                {
                    "title": "Exegesis",
                    "weight": 40,
                    "cells": {"Excellent": "Finds the chiasm"},
                },
                {"title": "Context"},
                {"title": "Application"},
            ],
        )

    def test_typed_weights_are_fixed_and_blank_ones_share_the_rest(self):
        def pct(*weights):
            share = rubrics.shares(
                [{"criterion_code": str(i), "weight": w} for i, w in enumerate(weights)]
            )
            return [round(share[str(i)] * 100, 2) for i in range(len(weights))]

        self.assertEqual(pct(None, None, None, None, None), [20.0] * 5)
        self.assertEqual(pct(None, None, None, None, 5), [23.75] * 4 + [5.0])
        self.assertEqual(pct(35, None, None, None, 5), [35.0, 20.0, 20.0, 20.0, 5.0])
        # All fixed and off 100: rescaled, the one case the editor warns about.
        self.assertEqual(pct(30, 30, 30), [33.33, 33.33, 33.33])

    def test_fixed_weights_must_leave_room_for_blank_ones(self):
        self.assertRaises(
            frappe.ValidationError,
            rubrics.save_rubric,
            "Assignment Activity",
            self.activity.name,
            self.scale.name,
            [
                {"title": "A", "weight": 60},
                {"title": "B", "weight": 40},
                {"title": "C"},
            ],
        )

    def test_scale_needs_one_meets_expectations_level_and_descending_percents(self):
        doc = frappe.get_doc(
            {
                "doctype": "Rubric Scale",
                "scale_name": fx.uid("RS"),
                "levels": [
                    {"label": "A", "percent": 100},
                    {"label": "B", "percent": 60},
                ],
            }
        )
        self.assertRaises(frappe.ValidationError, doc.insert)
        doc.levels[1].meets_expectations = 1
        doc.levels[1].percent = 100
        self.assertRaises(frappe.ValidationError, doc.insert)

    def test_editor_codes_criteria_and_shows_shares(self):
        ed = self.make_rubric()
        criteria = ed["rubric"]["criteria"]
        self.assertEqual(
            [c["criterion_code"] for c in criteria],
            ["exegesis", "context", "application"],
        )
        self.assertEqual([c["share"] for c in criteria], [40.0, 30.0, 30.0])
        self.assertEqual(ed["rubric"]["cells"][0]["descriptor"], "Finds the chiasm")
        self.assertEqual(
            frappe.db.get_value("Assignment Activity", self.activity.name, "rubric"),
            ed["rubric"]["name"],
        )

    def test_grade_follows_once_every_criterion_has_a_level(self):
        self.make_rubric()
        res = rubrics.save_scores(
            "Assignment Submission",
            self.sub.name,
            [
                {"criterion_code": "exegesis", "level": "Excellent"},
                {"criterion_code": "context", "level": "Proficient"},
            ],
        )
        self.assertIsNone(res["grade"])
        res = rubrics.save_scores(
            "Assignment Submission",
            self.sub.name,
            [{"criterion_code": "application", "level": "Developing"}],
        )
        # 40% x 100% + 30% x 85% + 30% x 70% = 86.5% of a section graded out of 10
        self.assertEqual(res["grade"], 8.65)
        sub = frappe.get_doc("Assignment Submission", self.sub.name)
        self.assertEqual(
            (sub.grade, sub.percentage, sub.status), (8.65, 8.65, "Graded")
        )

        # A whole-document save from a grading page cannot drift from the rubric.
        sub.grade = 2
        sub.save()
        self.assertEqual(sub.grade, 8.65)

    def test_a_used_rubric_becomes_a_new_version_and_old_grades_keep_theirs(self):
        first = self.make_rubric()["rubric"]["name"]
        rubrics.save_scores(
            "Assignment Submission",
            self.sub.name,
            _graded(["exegesis", "context", "application"], "Excellent"),
        )
        self.assertTrue(rubrics.is_locked(first))

        calls = []
        real = frappe.get_hooks

        def hooks(name=None, *a, **kw):
            if name == "rubric_replaced":
                return ["seminary.seminary.tests.test_adr095_rubrics.record_replaced"]
            return real(name, *a, **kw)

        with patch("frappe.get_hooks", side_effect=hooks), patch(
            "seminary.seminary.tests.test_adr095_rubrics.record_replaced",
            side_effect=lambda *a: calls.append(a),
        ):
            ed = rubrics.save_rubric(
                "Assignment Activity",
                self.activity.name,
                self.scale.name,
                [{"criterion_code": "exegesis", "title": "Exegesis", "weight": 1}],
            )
        second = ed["rubric"]["name"]
        self.assertNotEqual(first, second)
        self.assertEqual(ed["rubric"]["version"], 2)
        self.assertEqual(
            calls, [("Assignment Activity", self.activity.name, first, second)]
        )

        rubric = frappe.get_doc("Rubric", first)
        rubric.criteria[0].title = "Changed"
        self.assertRaises(frappe.ValidationError, rubric.save)
        self.assertEqual(
            frappe.db.get_value("Assignment Submission", self.sub.name, "grade"), 10
        )
        self.assertEqual(
            rubrics.scored_rubric(
                frappe.get_doc("Assignment Submission", self.sub.name)
            ),
            first,
        )

    def test_scale_in_use_cannot_change_its_levels(self):
        self.make_rubric()
        rubrics.save_scores(
            "Assignment Submission",
            self.sub.name,
            [{"criterion_code": "context", "level": "Beginning"}],
        )
        scale = frappe.get_doc("Rubric Scale", self.scale.name)
        scale.levels[0].percent = 99
        self.assertRaises(frappe.ValidationError, scale.save)
        scale.reload()
        scale.enabled = 0
        scale.save()

    def test_criterion_scores_only_counts_graded_work(self):
        self.make_rubric()
        rubrics.save_scores(
            "Assignment Submission",
            self.sub.name,
            [{"criterion_code": "context", "level": "Proficient"}],
        )
        self.assertEqual(rubrics.criterion_scores(self.row.name), [])
        rubrics.save_scores(
            "Assignment Submission",
            self.sub.name,
            _graded(["exegesis", "application"], "Developing"),
        )
        rows = {r["criterion_code"]: r for r in rubrics.criterion_scores(self.row.name)}
        self.assertEqual(rows["context"]["percent"], 85)
        self.assertEqual(rows["context"]["meets_expectations_percent"], 85)
        self.assertAlmostEqual(rows["exegesis"]["share"], 0.4)
        self.assertEqual(rows["exegesis"]["student"], self.student.name)

    def test_descriptive_section_stands_down(self):
        self.make_rubric()
        frappe.db.set_value(
            "Grading Scale", self.grading_scale, "grscale_type", "Descriptive"
        )
        self.assertFalse(
            rubrics.get_grading("Assignment Submission", self.sub.name)["active"]
        )

    def test_student_sees_rubric_and_own_levels_once_graded(self):
        self.make_rubric()
        rubrics.save_scores(
            "Assignment Submission",
            self.sub.name,
            [{"criterion_code": "context", "level": "Proficient", "comment": "Good"}],
        )
        frappe.set_user(self.student.user)
        view = rubrics.get_student_view(
            "Assignment Activity", self.activity.name, self.sub.name
        )
        self.assertEqual(len(view["rubric"]["criteria"]), 3)
        self.assertEqual(view["scores"], [])  # not graded yet: levels stay hidden
        frappe.set_user("Administrator")
        rubrics.save_scores(
            "Assignment Submission",
            self.sub.name,
            _graded(["exegesis", "application"], "Excellent"),
        )
        frappe.set_user(self.student.user)
        view = rubrics.get_student_view(
            "Assignment Activity", self.activity.name, self.sub.name
        )
        self.assertEqual(
            {s["criterion_code"]: s["level"] for s in view["scores"]}["context"],
            "Proficient",
        )


def record_replaced(*args):
    pass
