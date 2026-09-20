# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p010 Block F, A05-7: author text rendered with `autoescape=False`.

`author_templates` runs staff-written Announcement and Communication Template
text through a Jinja sandbox. The sandbox was sound -- no `frappe` global, no
session, strict undefined -- but it rendered with autoescaping off, so every
value interpolated from the context reached the output raw. Recipient names are
context values, and a recipient controls their own name.

The point autoescaping turns on is the *interpolated value*, not the template.
A template's own markup is literal text to Jinja and is never escaped, so the
author's formatting is untouched; only what comes out of `{{ ... }}` changes.

Two things stop this being a formatting regression:

* the mode follows the sink -- HTML for Email/In-App/Print, plain for SMS,
  WhatsApp, Telegram, Voice and every `Data` subject, because escaping a text
  message puts `&#39;` where an apostrophe belongs;
* a context value that is genuinely HTML opts back in with `| safe_html`,
  which repairs it through `content_safety.clean_rich` rather than dropping it
  (the p008 F1 policy).
"""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.author_templates import render_author_text

HOSTILE = '<img src=x onerror="alert(1)">Bob'
CTX = {"recipient": {"first_name": HOSTILE, "last_name": "O'Brien & Sons"}}


class TestP010AuthorText(IntegrationTestCase):
    # ------------------------------------------------ the finding itself

    def test_hostile_recipient_name_is_escaped_in_an_html_body(self):
        out = render_author_text(
            "<p>Dear {{ recipient.first_name }},</p>", CTX, html=True
        )
        # `onerror` survives as inert TEXT -- that is the point. What must not
        # survive is a live tag, so assert on the markup, not the substring.
        self.assertNotIn("<img", out)
        self.assertIn("&lt;img", out)
        # The only raw tags left are the author's own <p>...</p>.
        self.assertEqual(out.count("<"), 2)

    def test_plain_default_still_does_not_escape(self):
        """The default is unchanged, so an undecided caller keeps old behaviour."""
        out = render_author_text("Dear {{ recipient.first_name }}", CTX)
        self.assertIn("<img", out)

    # ------------------------------------------------ and what must NOT break

    def test_author_markup_survives_autoescaping(self):
        """Only the interpolation is escaped; the template is literal text."""
        out = render_author_text(
            "<b>Bold</b> <i>it</i> {{ recipient.last_name }}", CTX, html=True
        )
        self.assertIn("<b>Bold</b>", out)
        self.assertIn("<i>it</i>", out)
        self.assertIn("&#39;", out)  # the value, escaped

    def test_plain_sink_is_not_entity_mangled(self):
        """An SMS must not read `O&#39;Brien &amp; Sons`."""
        out = render_author_text("Hi {{ recipient.last_name }}", CTX, html=False)
        self.assertEqual(out, "Hi O'Brien & Sons")

    def test_safe_html_repairs_rather_than_drops(self):
        ctx = {"doc": {"body": "<p>Real <b>markup</b></p><script>alert(1)</script>"}}
        escaped = render_author_text("{{ doc.body }}", ctx, html=True)
        self.assertNotIn("<b>", escaped)

        repaired = render_author_text("{{ doc.body | safe_html }}", ctx, html=True)
        self.assertIn("<b>markup</b>", repaired)
        self.assertNotIn("<script>", repaired)

    # ------------------------------------------------ the sandbox is unchanged

    def test_sandbox_still_refuses_frappe_and_dunders(self):
        """Each probe must fail for its OWN reason, not merely fail.

        `frappe` is absent from the globals, so it is an undefined name; the
        dunder is present but refused by the sandbox. Asserting one shared
        `Exception` would let a typo in either probe pass vacuously.
        """
        from jinja2.exceptions import SecurityError, UndefinedError

        with self.assertRaises(UndefinedError):
            render_author_text("{{ frappe.db.sql('select 1') }}", CTX, html=True)
        with self.assertRaises(SecurityError):
            render_author_text("{{ ''.__class__ }}", CTX, html=True)

    # ------------------------------------------------ the callers pick a sink

    def test_announcement_renders_the_rich_body_escaped(self):
        from seminary.seminary.doctype.seminary_announcement import (
            seminary_announcement as ann,
        )

        self.assertNotIn(
            "<img", ann._render("{{ recipient.first_name }}", CTX, html=True)
        )
        # subject and short_message stay plain
        self.assertIn("<img", ann._render("{{ recipient.first_name }}", CTX))

    def test_comms_html_channels_are_the_rich_ones(self):
        from seminary.seminary import comms

        self.assertEqual(
            comms.HTML_CHANNELS,
            {comms.EMAIL_CHANNEL, comms.IN_APP_CHANNEL, comms.PRINT_CHANNEL},
        )
        for plain in (
            comms.SMS_CHANNEL,
            comms.WHATSAPP_CHANNEL,
            comms.TELEGRAM_CHANNEL,
        ):
            self.assertNotIn(plain, comms.HTML_CHANNELS)
