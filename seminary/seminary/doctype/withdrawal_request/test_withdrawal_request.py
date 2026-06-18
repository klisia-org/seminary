# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt

import json
from itertools import product
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from seminary.seminary import withdrawal


class _FakeDoc:
    """Minimal stand-in for a Withdrawal Request, enough for the edge-based
    dispatcher: a current workflow_state, a prior one (via get_doc_before_save),
    and the is_parent flag."""

    def __init__(self, prev_state, cur_state, is_parent=0):
        self._prev = prev_state
        self.workflow_state = cur_state
        self.is_parent = is_parent

    def get_doc_before_save(self):
        if self._prev is None:
            return None
        return frappe._dict(workflow_state=self._prev)


class TestWithdrawalDispatch(UnitTestCase):
    """Locks the transition -> side-effect table in dispatch_withdrawal_effects.

    Effects are bound to the edge (prev -> cur), not the resulting state, so
    these cases are the contract: which of academic / financial / completion
    runs for each transition, including the parent guard.
    """

    def _dispatch(self, prev, cur, is_parent=0):
        with (
            patch.object(withdrawal, "process_academic_approval") as acad,
            patch.object(withdrawal, "process_financial_approval") as fin,
            patch.object(withdrawal, "process_completion") as comp,
        ):
            withdrawal.dispatch_withdrawal_effects(_FakeDoc(prev, cur, is_parent))
        return acad.called, fin.called, comp.called

    # --- single-course (non-parent) edges ---------------------------------
    def test_academic_review_to_financial_review_runs_academic(self):
        self.assertEqual(
            self._dispatch("Academic Review", "Financial Review"), (True, False, False)
        )

    def test_academic_review_to_completed_runs_academic_and_completion(self):
        # No-refund "Approve Academically & Conclude": academic not yet applied.
        self.assertEqual(
            self._dispatch("Academic Review", "Completed"), (True, False, True)
        )

    def test_financial_review_to_completed_runs_financial_and_completion(self):
        # Academic already applied on entry to Financial Review.
        self.assertEqual(
            self._dispatch("Financial Review", "Completed"), (False, True, True)
        )

    def test_draft_fastpath_to_financial_review_runs_academic(self):
        self.assertEqual(
            self._dispatch("Draft", "Financial Review"), (True, False, False)
        )

    def test_draft_fastpath_to_completed_runs_academic_and_completion(self):
        # ongoing + free / no-refund single course: must still withdraw the CEI.
        self.assertEqual(self._dispatch("Draft", "Completed"), (True, False, True))

    def test_submit_to_academic_review_is_noop(self):
        self.assertEqual(
            self._dispatch("Draft", "Academic Review"), (False, False, False)
        )

    def test_reject_is_noop(self):
        self.assertEqual(
            self._dispatch("Academic Review", "Rejected"), (False, False, False)
        )
        self.assertEqual(
            self._dispatch("Financial Review", "Rejected"), (False, False, False)
        )

    # --- program-separation parent: no per-CEI effects, completion only ----
    def test_parent_never_runs_per_cei_effects(self):
        # Parent into Financial Review: academic is the children's job.
        self.assertEqual(
            self._dispatch("Academic Review", "Financial Review", 1),
            (False, False, False),
        )
        # Parent into Completed via finance: no per-CEI financial, completion runs.
        self.assertEqual(
            self._dispatch("Financial Review", "Completed", 1), (False, False, True)
        )
        # Parent fast-path into Completed: completion only (children gate it).
        self.assertEqual(self._dispatch("Draft", "Completed", 1), (False, False, True))


class TestWithdrawalWorkflowRouting(UnitTestCase):
    """The 5-state workflow must expose exactly one Submit-family / approval
    button per (role, program-flag) combination, or a request can stall (no
    button) or branch ambiguously (two buttons)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path = frappe.get_app_path("seminary", "fixtures", "workflow.json")
        with open(path) as fh:
            workflows = json.load(fh)
        cls.wf = next(w for w in workflows if w["name"] == "Course Withdrawal")

    def _matches(self, state, role, flags):
        """Transitions from `state` for `role` whose condition holds for flags."""
        out = []
        for t in self.wf["transitions"]:
            if t["state"] != state or t["allowed"] != role:
                continue
            cond = t.get("condition")
            # Mirror how Frappe's workflow engine evaluates transition conditions
            # (restricted AST) instead of a raw eval.
            ok = (
                True
                if not cond
                else bool(frappe.safe_eval(cond, None, {"doc": frappe._dict(flags)}))
            )
            if ok:
                out.append(t["action"])
        return out

    def test_states_are_the_five(self):
        self.assertEqual(
            [s["state"] for s in self.wf["states"]],
            ["Draft", "Academic Review", "Financial Review", "Completed", "Rejected"],
        )

    def test_exactly_one_registrar_submit_per_combo(self):
        for is_ongoing, is_free, refund_due in product((0, 1), repeat=3):
            flags = dict(is_ongoing=is_ongoing, is_free=is_free, refund_due=refund_due)
            actions = self._matches("Draft", "Registrar", flags)
            self.assertEqual(len(actions), 1, f"Registrar Draft {flags}: {actions}")

    def test_exactly_one_student_submit_per_combo(self):
        for is_ongoing, is_free, refund_due in product((0, 1), repeat=3):
            flags = dict(is_ongoing=is_ongoing, is_free=is_free, refund_due=refund_due)
            actions = self._matches("Draft", "Student", flags)
            self.assertEqual(len(actions), 1, f"Student Draft {flags}: {actions}")

    def test_exactly_one_academic_decision_per_combo(self):
        # Reject is always available, so exactly one of the two *approval*
        # actions (Financial Review vs Conclude) must apply per combo.
        for is_free, refund_due in product((0, 1), repeat=2):
            flags = dict(is_free=is_free, refund_due=refund_due)
            actions = [
                a
                for a in self._matches("Academic Review", "Registrar", flags)
                if a != "Reject"
            ]
            self.assertEqual(len(actions), 1, f"Academic Review {flags}: {actions}")
