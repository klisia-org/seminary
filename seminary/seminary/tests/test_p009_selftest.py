# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p009 S11: the setup check (`seminary.scorm.selftest`).

A selftest is only worth having if it fails when it should, so these tests are
mostly about the failures. The one that matters most is the registrable-domain
check: `scorm.example.net` beside `app.example.net` is the single configuration
mistake that looks entirely reasonable, passes every other arm, and quietly
undoes §2.2 -- a sibling subdomain can set a cookie the application host will
receive.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.scorm import selftest


class TestP009Registrable(IntegrationTestCase):
    def test_two_registrable_domains_are_different(self):
        self.assertNotEqual(
            selftest._registrable("tlink.aretenic.org"),
            selftest._registrable("tlink.aretenic.net"),
        )

    def test_siblings_under_one_domain_are_the_same(self):
        self.assertEqual(
            selftest._registrable("scorm.aretenic.net"),
            selftest._registrable("tlink.aretenic.net"),
        )

    def test_a_bare_domain_is_its_own_registrable_domain(self):
        self.assertEqual(selftest._registrable("aretenic.org"), "aretenic.org")

    def test_it_errs_towards_refusing(self):
        """`a.co.uk` and `b.co.uk` reduce to `co.uk` and are reported as
        sharing a domain. A false refusal an operator can overrule; the
        opposite error is the one §2.2 cannot tolerate."""
        self.assertEqual(
            selftest._registrable("a.co.uk"), selftest._registrable("b.co.uk")
        )


class TestP009SelftestConfig(IntegrationTestCase):
    def test_no_delivery_host_is_reported_not_crashed(self):
        with patch.dict(frappe.conf, {"scorm_delivery_host": None}):
            arm = selftest._config()
        self.assertFalse(arm["ok"])
        self.assertIn("scorm_delivery_host", arm["detail"])

    def test_a_delivery_host_with_no_app_origin_is_a_failure(self):
        """`delivery._app_origin` returns '' and the renderer then logs rather
        than raises, so without this arm the symptom is an empty iframe."""
        with patch.dict(
            frappe.conf,
            {
                "scorm_delivery_host": "scorm.test.invalid",
                "scorm_app_origin": None,
                "host_name": None,
            },
        ):
            arm = selftest._config()
        self.assertFalse(arm["ok"])
        self.assertIn("scorm_app_origin", arm["detail"])

    def test_a_sibling_subdomain_is_refused(self):
        with patch.dict(
            frappe.conf,
            {
                "scorm_delivery_host": "scorm.example.net",
                "scorm_app_origin": "https://app.example.net",
            },
        ):
            arm = selftest._config()
        self.assertFalse(arm["ok"])
        self.assertIn("registrable domain", arm["detail"])

    def test_two_registrable_domains_pass(self):
        with patch.dict(
            frappe.conf,
            {
                "scorm_delivery_host": "tlink.aretenic.org",
                "scorm_app_origin": "https://tlink.aretenic.net",
            },
        ):
            arm = selftest._config()
        self.assertTrue(arm["ok"], arm.get("detail"))

    def test_a_plaintext_delivery_origin_is_allowed_on_loopback(self):
        """The local two-origin pass runs over http on `*.localhost`, and that
        has to be permitted or the pass cannot be run at all -- which is how
        every browser-only bug in p009 came to be found one deploy at a time."""
        with patch.dict(
            frappe.conf,
            {
                "scorm_delivery_host": "scormdev.localhost",
                "scorm_delivery_origin": "http://scormdev.localhost:8006",
                "scorm_app_origin": "http://potestas.localhost:8006",
            },
        ):
            arm = selftest._config()
        self.assertTrue(arm["ok"], arm.get("detail"))
        self.assertEqual(arm["delivery_origin"], "http://scormdev.localhost:8006")

    def test_a_plaintext_delivery_origin_is_refused_anywhere_else(self):
        """Otherwise the developer override ships, and every launch token goes
        to the network in clear."""
        with patch.dict(
            frappe.conf,
            {
                "scorm_delivery_host": "tlink.aretenic.org",
                "scorm_delivery_origin": "http://tlink.aretenic.org",
                "scorm_app_origin": "https://tlink.aretenic.net",
            },
        ):
            arm = selftest._config()
        self.assertFalse(arm["ok"])
        self.assertIn("plaintext", arm["detail"])

    def test_a_bare_app_host_is_compared_without_its_scheme_or_port(self):
        with patch.dict(
            frappe.conf,
            {
                "scorm_delivery_host": "scorm.example.net",
                "scorm_app_origin": None,
                "host_name": "app.example.net:8006",
            },
        ):
            arm = selftest._config()
        self.assertFalse(arm["ok"])
        self.assertIn("registrable domain", arm["detail"])


class TestP009SelftestHooks(IntegrationTestCase):
    def test_the_registered_hooks_are_found(self):
        arm = selftest._hooks()
        self.assertTrue(arm["ok"], arm.get("missing"))

    def test_a_missing_renderer_is_named(self):
        with patch.object(frappe, "get_hooks", return_value=[]):
            arm = selftest._hooks()
        self.assertFalse(arm["ok"])
        self.assertEqual(len(arm["missing"]), 2)


class TestP009SelftestOrigin(IntegrationTestCase):
    """Arm 4 with the network replaced. What the HTTP hop proves is asserted
    here; that it can make one is not this suite's business."""

    HOST = {"scorm_delivery_host": "scorm.test.invalid"}

    OK = {
        selftest.PROBE_DESK: {
            "status": 404,
            "content_type": "text/html",
            "length": 900,
        },
        selftest.PROBE_API: {"status": 404, "content_type": "text/html", "length": 900},
        selftest.PROBE_SCORM: {
            "status": 404,
            "content_type": "text/plain",
            "length": 0,
        },
        selftest.PROBE_HTML: {
            "status": 404,
            "content_type": "text/plain",
            "length": 0,
        },
    }

    def _run(self, probes):
        with patch.dict(frappe.conf, self.HOST):
            with patch.object(
                selftest, "_fetch", side_effect=lambda origin, p: probes[p]
            ):
                return selftest._origin()

    def test_a_correctly_isolated_host_passes(self):
        arm = self._run(self.OK)
        self.assertTrue(arm["ok"], arm.get("failures"))

    def test_desk_answering_on_the_delivery_host_fails(self):
        probes = dict(self.OK)
        probes[selftest.PROBE_DESK] = {
            "status": 200,
            "content_type": "text/html",
            "length": 5000,
        }
        arm = self._run(probes)
        self.assertFalse(arm["ok"])
        self.assertIn("isolation", " ".join(arm["failures"]))

    def test_the_api_answering_on_the_delivery_host_fails(self):
        probes = dict(self.OK)
        probes[selftest.PROBE_API] = {
            "status": 200,
            "content_type": "application/json",
            "length": 40,
        }
        arm = self._run(probes)
        self.assertFalse(arm["ok"])

    def test_a_website_404_on_scorm_means_the_renderer_is_not_reached(self):
        """The discriminator: frappe's 404 is an HTML page, `_missing` is an
        empty `text/plain`. Both are 404s, and only one means SCORM works."""
        probes = dict(self.OK)
        probes[selftest.PROBE_SCORM] = {
            "status": 404,
            "content_type": "text/html",
            "length": 1200,
        }
        arm = self._run(probes)
        self.assertFalse(arm["ok"])
        self.assertIn("website router", " ".join(arm["failures"]))

    def test_an_html_member_path_that_gets_rewritten_fails(self):
        """Frappe's nginx template rewrites `.html` away with a 301, before the
        request reaches Python. Measured on tlink 2026-09-21: every HTML member
        of every package 404s, and `index.html` redirects to the launcher's own
        URL, so the launcher frames itself. No local test can see it -- `bench
        serve` has no nginx."""
        probes = dict(self.OK)
        probes[selftest.PROBE_HTML] = {
            "status": 301,
            "content_type": "text/html",
            "length": 162,
        }
        arm = self._run(probes)
        self.assertFalse(arm["ok"])
        self.assertIn("rewriting `.html` away", " ".join(arm["failures"]))

    def test_an_html_member_path_that_reaches_the_renderer_passes(self):
        """A 404 from our own renderer is the *correct* answer here: the probe
        names no real member. What is being asserted is that it arrived."""
        arm = self._run(self.OK)
        self.assertTrue(arm["ok"], arm.get("failures"))

    def test_an_unreachable_host_says_so_once_rather_than_four_times(self):
        probes = dict.fromkeys(self.OK, {"error": "NXDOMAIN"})
        arm = self._run(probes)
        self.assertFalse(arm["ok"])
        self.assertIn("Could not reach", arm["detail"])
        self.assertNotIn("failures", arm)


class TestP009SelftestRun(IntegrationTestCase):
    def test_arm_four_is_skipped_when_the_configuration_is_already_wrong(self):
        """Running it would report a connection failure and bury the finding
        arm 1 has already made."""
        with patch.dict(frappe.conf, {"scorm_delivery_host": None}):
            with patch.object(selftest, "_fetch") as fetch:
                report = selftest.run()
        fetch.assert_not_called()
        self.assertFalse(report["ok"])
        self.assertFalse(report["arms"]["origin"]["ok"])
        self.assertIn("config", report["arms"]["origin"]["detail"])

    def test_a_student_cannot_run_it(self):
        from seminary.seminary.tests.test_p006_api import _make_user

        student = _make_user("Student", "p9-selftest")
        frappe.set_user(student)
        try:
            with self.assertRaises(frappe.PermissionError):
                selftest.run()
        finally:
            frappe.set_user("Administrator")
