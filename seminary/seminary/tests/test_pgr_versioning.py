# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Program Graduation Requirement versioning: Submit activates a policy, and
'Change Version' retires it in place and spawns a Draft successor (ADR 012).

Lives here rather than beside the doctype because a doctype-level test module
makes IntegrationTestCase load test records for every linked doctype, and that
walk reaches doctypes a Frappe-only site does not have."""

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase

from seminary.seminary.tests import cohort_fixtures as fx


class TestPolicyVersioning(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def _policy(self):
        program = fx.make_program("Credits-based")
        item = frappe.get_doc(
            {
                "doctype": "Graduation Requirement Item",
                "requirement_name": fx.uid("GRI"),
                "requirement_type": "Manual Verification",
                "mandatory": 1,
                "default_staff_evidence_required": 1,
            }
        ).insert(ignore_permissions=True)
        policy = frappe.get_doc(
            {
                "doctype": "Program Graduation Requirement",
                "program_name": program.name,
                "active_from": frappe.utils.today(),
                "pgr_items": [
                    {
                        "grad_requirement_item": item.name,
                        "activation_mode": "Always Active",
                        "mandatory": 1,
                        "quantity_required": 1,
                        "offset_anchor": "Expected Graduation Date",
                    }
                ],
            }
        ).insert(ignore_permissions=True)
        apply_workflow(policy, "Submit")
        policy.reload()
        return policy

    def test_submit_activates_the_policy(self):
        policy = self._policy()
        self.assertEqual(policy.workflow_state, "Active")
        self.assertEqual(policy.active, 1)

    def test_change_version_retires_in_place_and_spawns_a_draft(self):
        """'Change Version' moves a submitted policy Active -> Superseded. The
        state field has to be writable after submit for that to work at all."""
        policy = self._policy()
        # frappe.copy_doc keeps docstatus under in_test, which would make the
        # spawned successor a submitted (Active) doc instead of a Draft.
        with patch.object(frappe, "in_test", False):
            apply_workflow(policy, "Change Version")
        policy.reload()
        self.assertEqual(policy.workflow_state, "Superseded")
        self.assertEqual(policy.active, 0)
        self.assertTrue(policy.superseded_by)
        successor = frappe.get_doc("Program Graduation Requirement", policy.superseded_by)
        self.assertEqual(successor.docstatus, 0)
        self.assertEqual(successor.workflow_state, "Draft")
        self.assertEqual(successor.active, 0)
        self.assertEqual(successor.supersedes, policy.name)
        self.assertEqual(len(successor.pgr_items), 1)
