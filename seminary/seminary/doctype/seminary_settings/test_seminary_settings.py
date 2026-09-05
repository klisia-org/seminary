# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""Seminary Settings publishes site defaults; they have to be real.

`seminary_keydict` maps a `frappe.db.set_default` key to the field it is read
from, and `on_update` walks it on every save. A field that does not exist
publishes an empty default — silently, because `Document.get` returns None for
an unknown key and `set_default` is happy to store it.

That is not hypothetical: `academic_year` and `academic_term` were published
this way for as long as the ERPNext decoupling had been done, pointing at
`current_academic_year` / `current_academic_term`, which had been removed from
this doctype. Everything downstream read nothing and degraded quietly.
"""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.doctype.seminary_settings.seminary_settings import (
    seminary_keydict,
)

EXTRA_TEST_RECORD_DEPENDENCIES = []

# Seminary Settings links User, which links Email Account, which links
# erpnext's Company — and `erpnext.tests.utils` inserts the standard price
# lists at import time, colliding with a site that already has them before a
# single test runs. Every direct link target is listed because the ignore list
# is applied to a doctype's *direct* links only; these tests read meta and a
# module constant, and create nothing.
IGNORE_TEST_RECORD_DEPENDENCIES = [
    "User",
    "Google Calendar",
    "Grading Scale",
    "Letter Head",
    "Portal Messaging Rule",
    "Web Form",
]


class TestTheKeydictPublishesRealFields(IntegrationTestCase):
    def test_every_published_default_reads_a_field_that_exists(self):
        meta = frappe.get_meta("Seminary Settings")
        for key, fieldname in seminary_keydict.items():
            with self.subTest(default_key=key, fieldname=fieldname):
                self.assertTrue(
                    meta.get_field(fieldname),
                    "Seminary Settings publishes the site default %r from %r, "
                    "which is not a field on it — the default is written empty "
                    "on every save" % (key, fieldname),
                )

    def test_the_retired_keys_are_not_back(self):
        """`Academic Term.iscurrent_acterm` is the app-wide answer, maintained
        by `tasks._update_term_flags` and read through
        `api.current_academic_term()`. A settings field restating it would be a
        second source of truth kept in step by hand. `validate_course` went the
        same way — its field was missing too, and nothing read the default."""
        for key in ("academic_term", "academic_year", "validate_course"):
            with self.subTest(default_key=key):
                self.assertNotIn(key, seminary_keydict)
