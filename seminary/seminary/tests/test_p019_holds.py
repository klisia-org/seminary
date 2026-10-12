# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""p019: another app holds a Person from a category through the
`communication_holds` hook. A held send is logged Cancelled with the app's
reason, reachability says "held", and Emergency is never held."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase as FrappeTestCase

from seminary.seminary import comms
from seminary.seminary.person import ensure_person

HOOK = "seminary.seminary.tests.test_p019_holds.fake_hold"


def fake_hold(person, channel, category, reference_doctype, reference_name):
    if category != "Promotional":
        return None
    if reference_name == "LET-ME-THROUGH":
        return None
    return "On hold: test"


def _hooks(name, *args, **kwargs):
    if name == comms.HOLD_HOOK:
        return [HOOK]
    return _real_get_hooks(name, *args, **kwargs)


_real_get_hooks = frappe.get_hooks


class TestP019Holds(FrappeTestCase):
    def setUp(self):
        self.person = frappe.get_doc(
            "Person",
            ensure_person("p019-held@example.com", first_name="Hal", last_name="Held"),
        )
        # Promotional needs opt-in, so the hold is what stops the message.
        if not any(c.category == "Promotional" for c in self.person.consents):
            self.person.append(
                "consents",
                {
                    "channel": comms.EMAIL_CHANNEL,
                    "category": "Promotional",
                    "status": "Opted In",
                },
            )
            self.person.save(ignore_permissions=True)

    def test_a_held_send_is_cancelled_with_the_reason(self):
        with patch("frappe.get_hooks", side_effect=_hooks):
            log = comms.send_message(
                channel=comms.EMAIL_CHANNEL,
                person=self.person,
                subject="Give now",
                message="<p>Appeal</p>",
                category="Promotional",
            )
            row = frappe.db.get_value(
                "Communication Log", log, ["status", "error"], as_dict=True
            )
            self.assertEqual((row.status, row.error), ("Cancelled", "On hold: test"))
            self.assertEqual(
                comms.reachability(self.person, comms.EMAIL_CHANNEL, "Promotional"),
                "held",
            )

    def test_other_categories_and_a_let_through_reference_pass(self):
        with patch("frappe.get_hooks", side_effect=_hooks):
            self.assertIsNone(
                comms.hold_reason(self.person, comms.EMAIL_CHANNEL, "Transactional")
            )
            self.assertIsNone(
                comms.hold_reason(
                    self.person,
                    comms.EMAIL_CHANNEL,
                    "Promotional",
                    "Seminary Announcement",
                    "LET-ME-THROUGH",
                )
            )
            self.assertIsNone(
                comms.hold_reason(self.person, comms.EMAIL_CHANNEL, "Emergency")
            )
