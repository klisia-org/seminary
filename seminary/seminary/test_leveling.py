# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Unit tests for the leveling resolver: score → resolution, and the read-helper
that splits the plan into exempted / required / leveling-course sets. Pure logic +
mocks, no DB records. Scores live on the placement-assessment child (ADR 060)."""

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from seminary.seminary import leveling


def _pe(exam_scores=None, leveling_rows=None):
    placements = [
        frappe._dict(assessment=a, score=score, status="Scored")
        for a, score in (exam_scores or {}).items()
    ]
    return frappe._dict(
        placement_assessments=placements,
        graduation_requirements=[],
        leveling=[frappe._dict(r) for r in (leveling_rows or [])],
    )


class TestLevelingResolve(UnitTestCase):
    def test_course_exemption_and_requirement_waiver(self):
        pe = _pe(
            leveling_rows=[
                {"kind": "Course Exemption", "course": "Greek I"},
                {"kind": "Requirement Waiver", "graduation_requirement_item": "GRI-x"},
            ]
        )
        leveling._resolve_rows(pe)
        self.assertEqual(pe.leveling[0].resolution, "Exempt")
        self.assertEqual(pe.leveling[1].resolution, "Waived")

    def test_unconditional_leveling_course_is_required(self):
        pe = _pe(leveling_rows=[{"kind": "Leveling Course", "course": "Greek I"}])
        leveling._resolve_rows(pe)
        self.assertEqual(pe.leveling[0].resolution, "Required")

    def test_score_gated_tiers(self):
        rows = [
            {
                "kind": "Leveling Course",
                "course": "Greek I",
                "gating_assessment": "EXAM",
                "exempt_if_score_at_least": 60,
            },
            {
                "kind": "Leveling Course",
                "course": "Greek II",
                "gating_assessment": "EXAM",
                "exempt_if_score_at_least": 75,
            },
            {
                "kind": "Leveling Course",
                "course": "Greek III",
                "gating_assessment": "EXAM",
                "exempt_if_score_at_least": 90,
            },
        ]
        pe = _pe(exam_scores={"EXAM": 80}, leveling_rows=rows)
        leveling._resolve_rows(pe)
        self.assertEqual(
            [r.resolution for r in pe.leveling], ["Exempt", "Exempt", "Required"]
        )

    def test_unscored_gated_course_is_pending(self):
        pe = _pe(
            leveling_rows=[
                {
                    "kind": "Leveling Course",
                    "course": "Greek I",
                    "gating_assessment": "EXAM",
                    "exempt_if_score_at_least": 60,
                }
            ]
        )
        leveling._resolve_rows(pe)
        self.assertEqual(pe.leveling[0].resolution, "Pending")

    def test_overridden_row_is_not_recomputed(self):
        pe = _pe(
            exam_scores={"EXAM": 10},  # well below threshold
            leveling_rows=[
                {
                    "kind": "Leveling Course",
                    "course": "Greek I",
                    "gating_assessment": "EXAM",
                    "exempt_if_score_at_least": 60,
                    "overridden": 1,
                    "resolution": "Exempt",
                }
            ],
        )
        leveling._resolve_rows(pe)
        self.assertEqual(pe.leveling[0].resolution, "Exempt")  # manual pin survives


class TestLevelingSets(UnitTestCase):
    def test_sets_split(self):
        rows = [
            frappe._dict(kind="Course Exemption", course="A", resolution="Exempt"),
            frappe._dict(kind="Leveling Course", course="B", resolution="Required"),
            frappe._dict(kind="Leveling Course", course="C", resolution="Exempt"),
            frappe._dict(
                kind="Placement Assessment", course=None, resolution="Pending"
            ),
        ]
        with patch.object(leveling.frappe, "get_all", return_value=rows):
            exempted, required, leveling_courses = leveling.leveling_sets("PE-1")
        self.assertEqual(exempted, {"A", "C"})
        self.assertEqual(required, {"B"})
        self.assertEqual(leveling_courses, {"B", "C"})
