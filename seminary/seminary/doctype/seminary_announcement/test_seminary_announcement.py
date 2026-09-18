# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt

import frappe
from jinja2.exceptions import SecurityError, UndefinedError
from frappe.tests import IntegrationTestCase
from frappe.tests import IntegrationTestCase as FrappeTestCase

from seminary.seminary.author_templates import get_env, render_author_text

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = [
    "Academic Term",
    "Communication Channel",
    "Course Schedule",
    "DocType",
    "Letter Head",
    "Mailing Label Format",
    "Program",
    "Seminary Announcement",
    "User",
]  # p006: fixtures are built in-test; the app's Student/Instructor test records predate Person-first identity


class IntegrationTestSeminaryAnnouncement(IntegrationTestCase):
    """
    Integration tests for SeminaryAnnouncement.
    Use this class for testing interactions between multiple components.
    """

    pass


class TestAuthorTextRendering(FrappeTestCase):
    """p006 F10: author-written text is not a template with Frappe access."""

    def test_no_frappe_global(self):
        env = get_env()
        for name in ("frappe", "session", "user", "get_url", "get_lesson_count"):
            self.assertNotIn(name, env.globals, name)
        self.assertIn("_", env.globals)

    def test_frappe_sql_raises_and_does_not_execute(self):
        marker = "p006-f10-marker"
        tpl = (
            '{{ frappe.db.sql("update `tabUser` set middle_name=%r '
            "where name='Administrator'\") }}" % marker
        )
        with self.assertRaises(UndefinedError):
            render_author_text(tpl, {})
        self.assertNotEqual(
            frappe.db.get_value("User", "Administrator", "middle_name"), marker
        )
        with self.assertRaises(UndefinedError):
            render_author_text('{{ frappe.db.sql("select 1") }}', {})

    def test_recipient_tokens_render(self):
        out = render_author_text(
            "Hello {{ recipient.first_name }}", {"recipient": {"first_name": "Ana"}}
        )
        self.assertEqual(out, "Hello Ana")

    def test_filters_work(self):
        ctx = {"recipient": {"first_name": "Ana"}, "items": [1, 2, 3]}
        self.assertEqual(
            render_author_text("{{ recipient.first_name | upper }}", ctx), "ANA"
        )
        self.assertEqual(render_author_text("{{ items | length }}", ctx), "3")
        self.assertEqual(
            render_author_text("{{ items | json }}", ctx), frappe.as_json([1, 2, 3])
        )

    def test_unknown_token_raises(self):
        # StrictUndefined: a missing name or a missing key on a plain dict
        # raises. (A frappe._dict answers a missing key with None instead, so
        # the announcement sample context uses plain dicts.)
        with self.assertRaises(UndefinedError):
            render_author_text(
                "{{ recipient.first }}", {"recipient": {"first_name": "Ana"}}
            )
        with self.assertRaises(UndefinedError):
            render_author_text("{{ nothing_here }}", {})

    def test_plain_text_returned_as_is(self):
        self.assertEqual(render_author_text("No tokens {here}", {}), "No tokens {here}")
        self.assertEqual(render_author_text("", {}), "")
        self.assertEqual(render_author_text(None, {}), "")

    def test_document_methods_are_not_callable(self):
        user = frappe.get_doc("User", "Administrator")
        self.assertEqual(
            render_author_text("{{ doc.name }}", {"doc": user}), "Administrator"
        )
        for tpl in (
            "{{ doc.delete() }}",
            "{{ doc.db_set('middle_name', 'x') }}",
            "{{ doc.__class__ }}",
        ):
            with self.assertRaises((SecurityError, UndefinedError), msg=tpl):
                render_author_text(tpl, {"doc": user})

    def test_validate_templates_rejects_frappe_call(self):
        doc = frappe.new_doc("Seminary Announcement")
        doc.subject = '{{ frappe.db.sql("select 1") }}'
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc._validate_templates()
        self.assertIn("Personalization error in", str(ctx.exception))

    def test_validate_templates_accepts_recipient_tokens(self):
        doc = frappe.new_doc("Seminary Announcement")
        doc.subject = "Hello {{ recipient.first_name }}"
        doc.message = "<p>{{ recipient.last_name | upper }}</p>"
        doc._validate_templates()  # no exception
