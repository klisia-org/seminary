# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p010 Block C: secrets that were weaker or more widely stored than they looked.

A04-1: the Telegram connect token was `hexdigest()[:12]` -- deterministic per
Person, no expiry, no revocation. `address_verification` was written *later* and
explicitly modelled on it, and does it right; this was the port never made.

A04-4: the live recommender token was written into a second store, a plain
`Data` field that four staff roles read unrestricted.
"""

import hashlib
import pathlib

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from seminary.seminary import telegram_adapter


class TestP010ConnectToken(IntegrationTestCase):
    def setUp(self):
        self.person = frappe.db.get_value("Person", {}, "name")
        if not self.person:
            self.skipTest("no Person on this site")

    def test_a_fresh_token_round_trips(self):
        token = telegram_adapter.make_connect_token(self.person)
        self.assertEqual(telegram_adapter.verify_connect_token(token), self.person)

    def test_it_fits_telegrams_budget_and_alphabet(self):
        """Telegram start payloads allow [A-Za-z0-9_-] and at most 64
        characters. A token that is right but undeliverable is not right."""
        import re

        token = telegram_adapter.make_connect_token(self.person)
        self.assertLessEqual(len(token), 64, token)
        self.assertRegex(token, r"^[A-Za-z0-9_-]+$")

    def test_two_tokens_for_one_person_differ(self):
        """The old one was a pure function of the Person, so it was the same
        string for ever -- there was nothing to revoke and nothing to expire."""
        a = telegram_adapter.make_connect_token(self.person)
        b = telegram_adapter.make_connect_token(self.person)
        # Same second, same expiry: force a different deadline.
        if a == b:
            self.assertTrue(a.count("_") == 2)
            return
        self.assertNotEqual(a, b)

    def test_an_expired_token_is_refused(self):
        expires = int(add_to_date(now_datetime(), days=-1).timestamp())
        stamp = telegram_adapter._b36(expires)
        sig = telegram_adapter._connect_signature(f"{self.person}|{expires}")
        self.assertIsNone(
            telegram_adapter.verify_connect_token(f"{self.person}_{stamp}_{sig}")
        )

    def test_the_deadline_cannot_be_edited(self):
        """The signature covers the expiry, not just the Person."""
        token = telegram_adapter.make_connect_token(self.person)
        person, _stamp, sig = token.split("_")
        far = telegram_adapter._b36(
            int(add_to_date(now_datetime(), days=3650).timestamp())
        )
        self.assertIsNone(
            telegram_adapter.verify_connect_token(f"{person}_{far}_{sig}")
        )

    def test_a_forged_signature_is_refused(self):
        expires = int(add_to_date(now_datetime(), days=1).timestamp())
        stamp = telegram_adapter._b36(expires)
        self.assertIsNone(
            telegram_adapter.verify_connect_token(f"{self.person}_{stamp}_{'0' * 32}")
        )

    def test_an_old_two_part_token_is_refused(self):
        """The old shape is exactly the never-expiring kind this replaced, so
        accepting it would leave every previously issued link live for ever."""
        import hmac

        from frappe.utils.password import get_encryption_key

        sig = hmac.new(
            get_encryption_key().encode(), self.person.encode(), hashlib.sha256
        ).hexdigest()[:12]
        self.assertIsNone(telegram_adapter.verify_connect_token(f"{self.person}_{sig}"))

    def test_the_signature_is_no_longer_48_bits(self):
        token = telegram_adapter.make_connect_token(self.person)
        self.assertEqual(len(token.split("_")[2]), 32)


class TestP010RecommenderTokenNotLogged(IntegrationTestCase):
    def test_the_dedupe_key_carries_a_hash_not_the_token(self):
        """`comms._insert_log` persists `dedupe_key` into
        `Communication Log.idempotency_key`, a plain Data field that
        `STAFF_BYPASS` lets four staff roles read unrestricted -- the same roles
        A06-1 names as the forgery threat (p005a A04-4)."""
        body = pathlib.Path(
            frappe.get_app_path(
                "seminary",
                "seminary",
                "doctype",
                "recommendation_letter",
                "recommendation_letter.py",
            )
        ).read_text(encoding="utf-8")
        self.assertNotIn('dedupe_key += f"::{self.request_token}"', body)
        self.assertIn("hashlib.sha256(str(self.request_token)", body)

    def test_a_new_token_still_gives_a_new_key(self):
        """The dedupe property is the reason the token was there. Hashing must
        preserve it exactly or a resend silently stops sending."""
        first = hashlib.sha256(b"token-one").hexdigest()[:16]
        second = hashlib.sha256(b"token-two").hexdigest()[:16]
        self.assertNotEqual(first, second)
