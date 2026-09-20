# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p008 F14: security response headers (p005a A02-9).

The app shipped none. What protected the site was the bench-generated
`config/nginx.conf` -- outside this repo, absent under `bench serve` or any other
proxy, dropped entirely inside `location` blocks that declare their own headers,
and skipped for non-2xx/3xx, so every error page was bare. Neither layer had a
CSP at all.
"""

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.wrappers import Response

from seminary.seminary import http_headers


class TestP008SecurityHeaders(IntegrationTestCase):
    def tearDown(self):
        frappe.conf.pop("seminary_csp_enforce", None)

    def _headers(self):
        response = Response("ok")
        http_headers.apply_security_headers(response=response)
        return response.headers

    def test_the_hook_is_registered(self):
        self.assertIn(
            "seminary.seminary.http_headers.apply_security_headers",
            frappe.get_hooks("after_request") or [],
        )

    def test_csp_ships_report_only_until_deliberately_enforced(self):
        """An enforcing CSP that is wrong shows a blank page, not a warning."""
        headers = self._headers()
        self.assertIn("Content-Security-Policy-Report-Only", headers)
        self.assertNotIn("Content-Security-Policy", headers.keys())

    def test_enforcing_is_one_site_config_flag(self):
        frappe.conf["seminary_csp_enforce"] = 1
        headers = self._headers()
        self.assertIn("Content-Security-Policy", headers.keys())
        self.assertNotIn("Content-Security-Policy-Report-Only", headers.keys())

    def test_the_framing_and_plugin_directives_are_closed(self):
        policy = http_headers.policy()
        # 'self', not 'none'. The app frames its own PDFs (`embed_renderer`'s
        # pdf branch), and 'none' broke that in the owner's browser pass --
        # cross-origin framing is what the directive is here to refuse.
        self.assertIn("frame-ancestors 'self'", policy)
        self.assertNotIn("frame-ancestors 'none'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertIn("base-uri 'self'", policy)
        self.assertIn("form-action 'self'", policy)

    def test_script_src_names_every_origin_that_can_run_code(self):
        policy = http_headers.policy()
        for origin in http_headers.SCRIPT_ORIGINS:
            self.assertIn(origin, policy, f"{origin} must be named, not implied")
        # Anything not named cannot execute.
        self.assertNotIn("script-src *", policy)

    def test_the_other_headers_are_set(self):
        headers = self._headers()
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        # SAMEORIGIN, tracking `frame-ancestors 'self'`: a browser honouring
        # both applies the stricter, so DENY here would undo the CSP.
        self.assertEqual(headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(headers["Referrer-Policy"], "strict-origin-when-cross-origin")

    def test_an_existing_header_is_not_overwritten(self):
        """A page that sets its own policy (a web form, an embed view) wins."""
        response = Response("ok")
        # Deliberately not the default value, or the test cannot distinguish
        # "kept the page's header" from "wrote its own".
        response.headers["X-Frame-Options"] = "DENY"
        http_headers.apply_security_headers(response=response)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_a_header_failure_never_costs_the_response(self):
        """`after_request` runs on the way out; raising there would turn a good
        response into a 500."""
        http_headers.apply_security_headers(response=None)  # must not raise
        http_headers.apply_security_headers(response=object())  # nor this

    def test_the_storage_redirect_sets_nosniff(self):
        """That endpoint hands the browser attacker-uploadable content."""
        import inspect

        from seminary.storage import api as storage_api

        source = inspect.getsource(storage_api.download_file)
        self.assertIn("X-Content-Type-Options", source)
