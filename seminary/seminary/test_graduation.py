# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Unit tests for the ADR 056 graduation-requirement logic: the Course Passed
activation gate and the emphasis applicability filter. These mock the DB reads
so they assert the decision logic, not the schema."""

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from seminary.seminary import graduation


def _pgr(applies=None, **kw):
    """A stand-in Program Grad Req Items row. applies_to_emphasis is a single
    Link (one Program Track) or None — Frappe forbids table fields on a child
    doctype, so it is not a multi-select (ADR 056)."""
    d = frappe._dict(kw)
    d["applies_to_emphasis"] = applies
    return d


class TestEmphasisScope(UnitTestCase):
    """_pgr_item_scope / _pgr_item_applies / _applicable_emphasis_tracks."""

    def test_unscoped_item_applies_to_everyone(self):
        self.assertTrue(graduation._pgr_item_applies(_pgr(), set()))
        self.assertTrue(graduation._pgr_item_applies(_pgr(), {"MDiv-Counseling"}))

    def test_scoped_item_requires_emphasis_overlap(self):
        item = _pgr(applies="MDiv-Counseling")
        self.assertFalse(graduation._pgr_item_applies(item, set()))
        self.assertFalse(graduation._pgr_item_applies(item, {"MDiv-Greek"}))
        self.assertTrue(graduation._pgr_item_applies(item, {"MDiv-Counseling"}))

    def test_scope_is_zero_or_one_element(self):
        self.assertEqual(graduation._pgr_item_scope(_pgr()), [])
        self.assertEqual(
            graduation._pgr_item_scope(_pgr(applies="MDiv-Counseling")),
            ["MDiv-Counseling"],
        )

    def test_applicable_tracks_excludes_advisory_and_inactive(self):
        pe = frappe._dict(
            emphases=[
                frappe._dict(emphasis_track="MDiv-Counseling", status="Active"),
                frappe._dict(emphasis_track="MDiv-Greek", status="Completed"),
                frappe._dict(emphasis_track="MDiv-Dropped", status="Dropped"),
                frappe._dict(emphasis_track="MDiv-Advisory", status="Active"),
            ]
        )
        # advisory lookup returns the advisory-only track, which must be dropped
        with patch.object(graduation.frappe, "get_all", return_value=["MDiv-Advisory"]):
            tracks = graduation._applicable_emphasis_tracks(pe)
        self.assertEqual(tracks, {"MDiv-Counseling", "MDiv-Greek"})

    def test_no_declared_emphases_skips_query(self):
        pe = frappe._dict(emphases=[])
        # get_all must not be hit when there are no candidate tracks
        with patch.object(
            graduation.frappe, "get_all", side_effect=AssertionError("queried")
        ):
            self.assertEqual(graduation._applicable_emphasis_tracks(pe), set())


class TestCoursePassedActivation(UnitTestCase):
    """evaluate_activation() Course Passed branch (single prerequisite course)."""

    def _eval(self, required_course, passed_courses):
        sgr = frappe._dict(pgr_item="PGRI-1")
        pe = frappe._dict(name="PE-1", graduation_requirements=[])
        item = frappe._dict(
            activation_mode="Course Passed",
            prerequisite_course=required_course,
        )

        # frappe.db.exists returns truthy iff a passing PEC row matches the filter
        def fake_exists(doctype, filters):
            return filters.get("course_name") in passed_courses

        from seminary.seminary import leveling as leveling_mod

        with (
            patch.object(graduation, "_load_pgr_item", return_value=item),
            patch.object(graduation.frappe.db, "exists", side_effect=fake_exists),
            patch.object(
                leveling_mod, "leveling_sets", return_value=(set(), set(), set())
            ),
        ):
            return graduation.evaluate_activation(sgr, pe)

    def test_active_when_required_course_passed(self):
        self.assertTrue(self._eval("C1", {"C1", "C2"}))

    def test_inactive_when_required_course_not_passed(self):
        self.assertFalse(self._eval("C1", {"C2"}))
        self.assertFalse(self._eval("C1", set()))

    def test_no_prerequisite_course_is_always_active(self):
        self.assertTrue(self._eval(None, set()))


class TestAfterRequirementActivation(UnitTestCase):
    """evaluate_activation() After Requirement branch (single prerequisite)."""

    def _eval(self, needed_lib, fulfilled):
        sgr = frappe._dict(pgr_item="PGRI-1")
        pe = frappe._dict(
            name="PE-1",
            graduation_requirements=[
                frappe._dict(grad_requirement_item=lib, status="Fulfilled")
                for lib in fulfilled
            ],
        )
        item = frappe._dict(
            activation_mode="After Requirement",
            prerequisite_requirement=needed_lib,
        )
        with patch.object(graduation, "_load_pgr_item", return_value=item):
            return graduation.evaluate_activation(sgr, pe)

    def test_active_when_prerequisite_fulfilled(self):
        self.assertTrue(self._eval("GRI-1", {"GRI-1", "GRI-2"}))

    def test_inactive_when_prerequisite_not_fulfilled(self):
        self.assertFalse(self._eval("GRI-1", {"GRI-2"}))

    def test_no_prerequisite_is_always_active(self):
        self.assertTrue(self._eval(None, set()))
