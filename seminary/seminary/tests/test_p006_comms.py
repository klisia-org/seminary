# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""p006 F13: server-side sanitising of student/partner-authored rich text uses
`frappe.utils.sanitize_html(..., always_sanitize=True)` — the nh3 allow-list,
with the JSON / no-tags short-circuit disabled so a comment-wrapped payload is
parsed rather than waved through."""

import frappe
from frappe.tests import IntegrationTestCase as FrappeTestCase
from frappe.utils import sanitize_html

from seminary.partner.portal import _clean

BYPASS_PAYLOAD = "<!--><img src=x onerror=alert(1)>-->"


class TestP006Sanitiser(FrappeTestCase):
    def test_comment_wrapped_payload_is_neutralised(self):
        out = sanitize_html(BYPASS_PAYLOAD, always_sanitize=True)
        self.assertNotIn("onerror", out)
        self.assertNotIn("alert(", out)

    def test_editor_formatting_survives(self):
        html = (
            '<p lang="pt"><strong>Graça</strong> e <em>paz</em> — '
            '<a href="https://example.test/x">link</a>'
            "<sup>1</sup></p><table><tr><td>a</td></tr></table>"
        )
        out = sanitize_html(html, always_sanitize=True)
        for fragment in (
            "<strong>Graça</strong>",
            "<em>paz</em>",
            'href="https://example.test/x"',
            "<sup>1</sup>",
            "<td>a</td>",
            'lang="pt"',
        ):
            self.assertIn(fragment, out, fragment)

    def test_partner_clean_targets_text_fields_only(self):
        # Text Editor: sanitised.
        self.assertNotIn(
            "onerror", _clean("Partner Job Opening", "description", BYPASS_PAYLOAD)
        )
        self.assertNotIn(
            "onerror", _clean("Partner Organization", "about_us", BYPASS_PAYLOAD)
        )
        # Data / Link / Check: passed through untouched.
        self.assertEqual(_clean("Partner Job Opening", "job_title", "A & B"), "A & B")
        self.assertEqual(_clean("Partner Job Opening", "open_alumni", 1), 1)
        self.assertIsNone(_clean("Partner Organization", "website", None))

    def test_personal_development_plan_sanitises_rich_text(self):
        doc = frappe.new_doc("Personal Development Plan")
        doc.reflection = BYPASS_PAYLOAD
        doc.append("goals", {"goal": BYPASS_PAYLOAD, "action_steps": BYPASS_PAYLOAD})
        doc.sanitize_rich_text()
        self.assertNotIn("onerror", doc.reflection)
        self.assertNotIn("onerror", doc.goals[0].goal)
        self.assertNotIn("onerror", doc.goals[0].action_steps)
