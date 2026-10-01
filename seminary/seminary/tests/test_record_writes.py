# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""The two doors into the official record (record_writes.py): every grade write
reaches the seminary_record_write hooks, and the plan can be substituted through
seminary_curriculum_resolver."""

import pathlib
import re
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

import seminary
from seminary.seminary import graduation_candidate, record_writes
from seminary.seminary.api import _program_audit
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr083_bulk_enrollment import _course

HERE = "seminary.seminary.tests.test_record_writes"
SEEN = []


def _record(change):
    SEEN.append(change)
    change.seen_by_test = True


def _no_opinion(pe, program):
    return None


def _small_plan(pe, program):
    return frappe._dict(
        frozen=True,
        frozen_on="2026-01-01",
        courses=[],
        credits_complete=1,
        terms_complete=0,
        min_graduation_gpa=0,
    )


def _hooks(mapping):
    real = frappe.get_hooks

    def fake(hook=None, *args, **kwargs):
        if hook in mapping:
            return list(mapping[hook])
        return real(hook, *args, **kwargs)

    return patch.object(frappe, "get_hooks", side_effect=fake)


def _row(pe, course, **values):
    """A transcript row as enrollment leaves it: no grade yet."""
    doc = frappe.get_doc(
        {
            "doctype": "Program Enrollment Course",
            "name": frappe.generate_hash(length=10),
            "parent": pe.name,
            "parenttype": "Program Enrollment",
            "parentfield": "courses",
            "course_name": course,
            "credits": 3,
            "status": "Enrolled",
            "count_in_gpa": 1,
            **values,
        }
    )
    doc.db_insert()
    return doc.name


class TestGradeWritesReachTheHooks(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        SEEN.clear()
        self.course = _course()
        self.pe = fx.make_enrollment(fx.make_student(), fx.make_program("Credits-based"))
        self.row = _row(self.pe, self.course)
        self.hooks = _hooks({record_writes.WRITE_HOOK: [f"{HERE}._record"]})
        self.hooks.start()

    def tearDown(self):
        self.hooks.stop()
        super().tearDown()

    def _post(self, **kw):
        return record_writes.write_grade(
            self.row,
            {"pec_finalgradecode": "B", "pec_finalgradenum": 88.0, "status": "Pass"},
            total_credits=3,
            source="test",
            **kw,
        )

    def test_the_write_happens(self):
        self._post()
        self.assertEqual(
            frappe.db.get_value("Program Enrollment Course", self.row, "pec_finalgradecode"), "B"
        )
        self.assertEqual(frappe.db.get_value("Program Enrollment", self.pe.name, "totalcredits"), 3)

    def test_the_hook_sees_before_and_after(self):
        change = self._post()
        self.assertEqual(len(SEEN), 1)
        self.assertIs(SEEN[0], change)
        self.assertEqual(change.before["status"], "Enrolled")
        self.assertEqual(change.after["pec_finalgradecode"], "B")
        self.assertEqual((change.credits_before, change.credits_after), (0, 3))
        self.assertEqual(change.program_enrollment, self.pe.name)
        self.assertEqual(change.row, self.row)
        self.assertTrue(change.changed)

    def test_the_action_defaults_to_posted_then_changed(self):
        self.assertEqual(self._post().action, record_writes.POSTED)
        change = record_writes.write_grade(
            self.row, {"pec_finalgradecode": "A"}, source="test"
        )
        self.assertEqual(change.action, record_writes.CHANGED)

    def test_a_named_action_and_reason_are_passed_on(self):
        change = self._post(action=record_writes.WITHDRAWN, reason="WR-1")
        self.assertEqual((change.action, change.reason, change.source), (record_writes.WITHDRAWN, "WR-1", "test"))

    def test_repeating_the_same_write_is_marked_unchanged(self):
        self._post()
        self.assertFalse(self._post().changed)

    def test_a_hook_can_annotate_what_the_caller_gets_back(self):
        self.assertTrue(self._post().seen_by_test)

    def test_a_credit_recomputation_reaches_the_hook(self):
        change = record_writes.set_total_credits(self.pe.name, 9, source="test")
        self.assertEqual((change.action, change.credits_after, change.row), (record_writes.CREDITS_RECOMPUTED, 9, None))
        self.assertTrue(change.changed)
        self.assertFalse(record_writes.set_total_credits(self.pe.name, 9, source="test").changed)

    def test_a_row_born_with_a_result_reaches_the_hook(self):
        born = _row(self.pe, _course(), pec_finalgradecode="A", status="Pass")
        change = record_writes.announce_new_row(born, source="test", reason="BATCH-1")
        self.assertEqual((change.before, change.after["pec_finalgradecode"]), ({}, "A"))
        self.assertEqual(change.action, record_writes.TRANSFER)

    def test_a_hook_that_raises_stops_the_caller(self):
        with _hooks({record_writes.WRITE_HOOK: ["frappe.throw"]}):
            with self.assertRaises(Exception):
                self._post()


class TestThePlanCanBeSubstituted(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.course = _course()
        self.program = fx.make_program("Credits-based")
        self.program.append(
            "courses",
            {"course": self.course, "course_name": self.course, "required": 1, "pgmcourse_credits": 3, "course_term": 1},
        )
        self.program.save(ignore_permissions=True)
        frappe.db.set_value("Program", self.program.name, "credits_complete", 3)
        frappe.clear_document_cache("Program", self.program.name)
        self.pe = fx.make_enrollment(fx.make_student(), self.program)

    def test_by_default_the_plan_is_the_program(self):
        with _hooks({record_writes.CURRICULUM_HOOK: []}):
            plan = record_writes.get_curriculum(self.pe)
        self.assertFalse(plan.frozen)
        self.assertEqual(plan.credits_complete, 3)
        self.assertEqual([(c.course, c.required, c.credits) for c in plan.courses], [(self.course, 1, 3)])

    def test_the_audit_reads_the_default_plan(self):
        with _hooks({record_writes.CURRICULUM_HOOK: []}):
            audit = _program_audit(self.pe.name)
        self.assertEqual(audit["credits_required"], 3)
        self.assertFalse(audit["curriculum_frozen"])
        self.assertEqual({m["course"] for m in audit["mandatory_courses"]}, {self.course})

    def test_a_resolver_can_substitute_the_plan(self):
        with _hooks({record_writes.CURRICULUM_HOOK: [f"{HERE}._small_plan"]}):
            audit = _program_audit(self.pe.name)
        self.assertEqual(audit["credits_required"], 1)
        self.assertTrue(audit["curriculum_frozen"])
        self.assertEqual(audit["mandatory_courses"], [])

    # Each test names the resolvers it runs with, so another installed app's
    # resolver cannot change what these tests see.

    def test_a_resolver_without_an_opinion_falls_through(self):
        with _hooks({record_writes.CURRICULUM_HOOK: [f"{HERE}._no_opinion"]}):
            self.assertEqual(record_writes.get_curriculum(self.pe).credits_complete, 3)

    def test_the_last_registered_resolver_is_asked_first(self):
        with _hooks({record_writes.CURRICULUM_HOOK: [f"{HERE}._no_opinion", f"{HERE}._small_plan"]}):
            self.assertEqual(record_writes.get_curriculum(self.pe).credits_complete, 1)

    def test_graduation_candidacy_reads_the_plan_through_the_door(self):
        with patch.object(record_writes, "get_curriculum", wraps=record_writes.get_curriculum) as door:
            graduation_candidate._compute(self.pe)
        self.assertTrue(door.called)


class TestNothingWritesAroundTheDoor(UnitTestCase):
    """A direct write to a grade or to the credit total bypasses the hooks, so
    none may exist outside record_writes.py."""

    ROOT = pathlib.Path(seminary.__file__).parent
    SKIP = ("/tests/", "/test_", "/patches/", "/demo/", "record_writes.py")

    def _offenders(self, pattern):
        found = []
        for path in self.ROOT.rglob("*.py"):
            if any(part in str(path) for part in self.SKIP):
                continue
            source = path.read_text()
            for match in re.finditer(pattern, source, flags=re.S):
                line = source.count("\n", 0, match.start()) + 1
                found.append(f"{path.relative_to(self.ROOT)}:{line}")
        return found

    def test_no_direct_write_to_a_transcript_row(self):
        self.assertEqual(
            self._offenders(
                r"""set_value\(\s*["']Program Enrollment Course["']"""
                r"""|UPDATE\s+`tabProgram Enrollment Course`"""
            ),
            [],
        )

    def test_no_direct_write_to_the_credit_total(self):
        self.assertEqual(
            self._offenders(
                r"""set_value\(\s*["']Program Enrollment["']\s*,[^)]*?["']totalcredits["']"""
                r"""|db_set\(\s*["']totalcredits["']"""
            ),
            [],
        )
