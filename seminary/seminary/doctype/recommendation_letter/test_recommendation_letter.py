# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests import IntegrationTestCase as FrappeTestCase

from seminary.seminary import recommender
from seminary.seminary.doctype.recommendation_letter.recommendation_letter import (
    regenerate_token,
)
from seminary.seminary.tests.cohort_fixtures import make_user

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = [
    "Communication",
    "Program Enrollment",
    "Recommendation Letter",
    "Student",
    "User",
    "Workflow State",
]  # p006: fixtures are built in-test; the app's Student/Instructor test records predate Person-first identity


class IntegrationTestRecommendationLetter(IntegrationTestCase):
    """
    Integration tests for RecommendationLetter.
    Use this class for testing interactions between multiple components.
    """

    pass


def _make_letter():
    """A draft letter with no enrollment behind it: enough for the token paths,
    which never touch the SGR. Rolled back with the test."""
    doc = frappe.get_doc(
        {
            "doctype": "Recommendation Letter",
            "recommender_name": "Prof. Test Recommender",
            "recommender_email": "recommender@example.test",
            "delivery_method": "Portal Form",
        }
    )
    doc.flags.ignore_mandatory = True
    doc.flags.ignore_links = True
    doc.insert(ignore_permissions=True)
    return doc


class TestRecommendationLetterToken(FrappeTestCase):
    """p006 F12: regenerate_token is a registrar action and never leaks the
    token; the guest token check is constant-time and non-enumerating."""

    def setUp(self):
        self.addCleanup(frappe.set_user, "Administrator")
        self.letter = _make_letter()

    def test_student_cannot_regenerate_token(self):
        student = make_user(roles=["Student"])
        frappe.set_user(student.name)
        with self.assertRaises(frappe.PermissionError):
            regenerate_token(self.letter.name)
        # The token was not touched by the refused call.
        self.assertEqual(
            frappe.db.get_value(
                "Recommendation Letter", self.letter.name, "request_token"
            ),
            self.letter.request_token,
        )

    def test_regenerate_token_rotates_without_returning_it(self):
        before = self.letter.request_token
        out = regenerate_token(self.letter.name)
        self.assertNotIn("token", out)
        self.assertIn("expires_on", out)
        self.assertIn("sent_to", out)
        after = frappe.db.get_value(
            "Recommendation Letter", self.letter.name, "request_token"
        )
        self.assertTrue(after)
        self.assertNotEqual(after, before)
        # Whatever the mail path did, the response never carries the secret.
        self.assertNotIn(after, str(out))

    def test_missing_letter_and_wrong_token_fail_identically(self):
        with self.assertRaises(frappe.PermissionError) as missing:
            recommender._validate_token("RL-DOES-NOT-EXIST", "x")
        with self.assertRaises(frappe.PermissionError) as wrong:
            recommender._validate_token(self.letter.name, "not-the-token")
        self.assertEqual(str(missing.exception), str(wrong.exception))
        self.assertEqual(str(wrong.exception), "Invalid or expired link.")

    def test_expired_token_fails_with_the_same_message(self):
        self.letter.db_set("token_expires_on", "2000-01-01", update_modified=False)
        with self.assertRaises(frappe.PermissionError) as expired:
            recommender._validate_token(self.letter.name, self.letter.request_token)
        self.assertEqual(str(expired.exception), "Invalid or expired link.")

    def test_valid_token_loads_the_letter(self):
        doc = recommender._validate_token(self.letter.name, self.letter.request_token)
        self.assertEqual(doc.name, self.letter.name)

    def test_only_a_file_attached_to_this_letter_counts_as_its_attachment(self):
        """submit_letter records `attachment_url` only when it names a File that
        upload_attachment attached to this very letter; anything else is
        ignored. Exercised at the seam, since saving the letter through
        submit_letter needs a full enrollment behind it."""

        def _file(attached_to):
            # Distinct content per file: Frappe dedupes Files by content hash
            # and would otherwise hand both rows the same file_url.
            doc = frappe.get_doc(
                {
                    "doctype": "File",
                    "file_name": f"p006-{attached_to}.txt",
                    "is_private": 1,
                    "attached_to_doctype": "Recommendation Letter",
                    "attached_to_name": attached_to,
                    "content": f"letter for {attached_to}".encode(),
                }
            )
            doc.save(ignore_permissions=True)
            return doc

        other = _make_letter()
        foreign = _file(other.name)
        own = _file(self.letter.name)

        self.assertFalse(
            recommender._is_own_attachment(self.letter.name, foreign.file_url)
        )
        self.assertFalse(
            recommender._is_own_attachment(self.letter.name, "/private/files/nope.pdf")
        )
        self.assertTrue(recommender._is_own_attachment(self.letter.name, own.file_url))
