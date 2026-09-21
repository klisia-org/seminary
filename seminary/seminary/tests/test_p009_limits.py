# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p009 S11: the rate limits, and the request context that makes them run.

**These tests exist because the suite could not see the bug.**
`frappe.rate_limiter.rate_limit` returns early when `frappe.request` is unset
(`rate_limiter.py:133`), so under `bench run-tests`, `bench console` and
`bench execute` the decorator is a complete no-op. Five SCORM endpoints carried
`@rate_limit(key="scorm_<name>", ip_based=False)`, where `key` names a *request
parameter* and not a label -- so with no such parameter and no IP the limiter
had no identity, threw `ValidationError`, and answered **417 to every browser**,
while every test, every console call and every `bench execute` passed.

So the point of `_with_request` below is not ceremony. It is the one thing that
separates what the suite sees from what a user sees, and every test here runs
inside it.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from seminary.scorm import launch as launch_module, limits, runtime, tokens
from seminary.seminary.tests.test_p009_runtime import _CommitCase


class _RequestCase(IntegrationTestCase):
    """Runs its body with a real `frappe.local.request` in place."""

    def _with_request(self, path="/api/method/test", data=None):
        builder = EnvironBuilder(
            path=path,
            method="POST",
            data=data or {},
            environ_base={"REMOTE_ADDR": "203.0.113.9"},
        )
        request = Request(builder.get_environ())
        patcher = patch.object(frappe.local, "request", request, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        return request


class TestP009Limits(_RequestCase):
    def setUp(self):
        super().setUp()
        self._with_request()
        self.bucket = "test-" + frappe.generate_hash(length=8)

    def test_it_counts_and_then_refuses(self):
        for _ in range(3):
            self.assertFalse(limits.exceeded(self.bucket, 3, 3600))
        self.assertTrue(limits.exceeded(self.bucket, 3, 3600))

    def test_enforce_raises_once_over(self):
        limits.enforce(self.bucket, 1, 3600)
        with self.assertRaises(frappe.TooManyRequestsError):
            limits.enforce(self.bucket, 1, 3600)

    def test_two_users_do_not_share_a_bucket(self):
        """The reason this is not IP-based: a whole school behind one NAT must
        not spend each other's allowance."""
        self.assertFalse(limits.exceeded(self.bucket, 1, 3600, who="u:a@x.invalid"))
        self.assertTrue(limits.exceeded(self.bucket, 1, 3600, who="u:a@x.invalid"))
        self.assertFalse(limits.exceeded(self.bucket, 1, 3600, who="u:b@x.invalid"))

    def test_identity_is_the_user_when_there_is_one(self):
        self.assertEqual(limits.identity(), "u:%s" % frappe.session.user)

    def test_identity_falls_back_to_the_address_for_a_guest(self):
        frappe.set_user("Guest")
        try:
            self.assertEqual(limits.identity(), "ip:203.0.113.9")
        finally:
            frappe.set_user("Administrator")

    def test_a_limiter_that_cannot_count_does_not_refuse(self):
        """Fails open, deliberately: redis being unreachable must not take
        playback down with it."""
        with patch.object(frappe.cache, "incrby", side_effect=RuntimeError("no redis")):
            self.assertFalse(limits.exceeded(self.bucket, 1, 3600))


class TestP009EndpointsUnderRequest(_CommitCase):
    """The regression test proper: every whitelisted SCORM endpoint, called the
    way a browser calls it -- with a request in `frappe.local` -- must answer.

    Before the fix each of these raised `ValidationError` (HTTP 417) here and
    nowhere else.
    """

    def setUp(self):
        super().setUp()
        builder = EnvironBuilder(
            path="/api/method/seminary.scorm.launch.launch",
            method="POST",
            environ_base={"REMOTE_ADDR": "203.0.113.9"},
        )
        patcher = patch.object(
            frappe.local, "request", Request(builder.get_environ()), create=True
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_launch_answers_with_a_request_in_flight(self):
        payload = launch_module.launch(self.chapter.name)
        self.assertEqual(payload["status"], "Ready")

    def test_heartbeat_answers_with_a_request_in_flight(self):
        self.assertTrue(launch_module.heartbeat(self.token)["ok"])

    def test_end_answers_with_a_request_in_flight(self):
        self.assertTrue(launch_module.end(self.token)["ok"])

    def test_commit_answers_with_a_request_in_flight(self):
        result = self._commit({"cmi.location": "page-1"})
        self.assertTrue(result["ok"], result)

    def test_state_answers_with_a_request_in_flight(self):
        self._commit({"cmi.location": "page-2"})
        self.assertEqual(runtime.state(self.token, "A").get("location"), "page-2")

    def test_the_limit_still_bites(self):
        """Not merely "it no longer throws" -- it has to still refuse."""
        with patch.object(limits, "exceeded", return_value=True):
            with self.assertRaises(frappe.TooManyRequestsError):
                launch_module.launch(self.chapter.name)

    def test_a_second_launch_is_not_refused(self):
        """The bucket is per user per window, and a player legitimately
        re-launches when a student reopens a lesson."""
        for _ in range(3):
            self.assertEqual(launch_module.launch(self.chapter.name)["status"], "Ready")

    def test_tokens_still_resolve_after_a_limited_call(self):
        payload = launch_module.launch(self.chapter.name)
        self.assertIsNotNone(tokens.resolve(payload["token"]))
