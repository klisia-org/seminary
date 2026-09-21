# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p009 S4: the isolated delivery origin (§2.2, §2.6, §2.7).

Two properties are under test, and they are the ones the whole feature rests on:

* **The origin split is real.** The app answers nothing on the delivery host and
  the delivery renderer answers nothing on the app host. Frappe routes on path
  and ignores `Host`, so this is entirely our doing and entirely testable here.
* **Addressing is deny-by-default.** A request names an inventory entry or it
  gets a 404. Nothing in the serving path computes or resolves a path, so there
  is no traversal to test for -- what is tested is that a path the package never
  declared is simply absent.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from seminary.scorm import delivery, tokens
from seminary.seminary.tests.test_p009_lifecycle import _ScormCase, _zip

DELIVERY_HOST = "scorm.test.invalid"
APP_HOST = "app.test.invalid"


class TestP009Delivery(_ScormCase):
    def setUp(self):
        super().setUp()
        self.conf = patch.dict(
            frappe.conf,
            {"scorm_delivery_host": DELIVERY_HOST, "host_name": f"https://{APP_HOST}"},
        )
        self.conf.start()
        self.addCleanup(self.conf.stop)

        self.chapter = self._chapter()
        self.package_name = self._unpack(
            self.chapter,
            _zip(
                [("A", "First", "index.html")],
                extra={"a/style.css": "body{}", "media/clip.mp4": b"\x00binary"},
                nonce=frappe.generate_hash(length=6),
            ),
        )
        self.package = frappe.get_doc("SCORM Package", self.package_name)
        self.assertEqual(self.package.status, "Ready", self.package.failure_reason)
        self.token = tokens.mint(
            "stu@test.invalid", self.package_name, self.chapter.name
        )

    # ------------------------------------------------------------- plumbing

    def _request(self, path, host=DELIVERY_HOST, headers=None):
        builder = EnvironBuilder(path=path, headers=headers or {})
        builder.host = host
        frappe.local.request = Request(builder.get_environ())
        return frappe.local.request

    def _get(self, member="", token=None, package_id=None, host=DELIVERY_HOST):
        token = self.token if token is None else token
        package_id = self.package.package_id if package_id is None else package_id
        path = f"/scorm/{token}/{package_id}/{member}"
        self._request(path, host=host)
        renderer = delivery.SCORMDelivery(path.strip("/"))
        if not renderer.can_render():
            return None
        return renderer.render()

    # -------------------------------------------------------- the host split

    def test_the_renderer_declines_every_request_on_the_app_host(self):
        self.assertIsNone(self._get("index.html", host=APP_HOST))

    def test_the_renderer_declines_when_no_delivery_host_is_configured(self):
        with patch.dict(frappe.conf, {"scorm_delivery_host": None}):
            self.assertIsNone(self._get("index.html"))

    def test_the_app_is_a_404_on_the_delivery_host(self):
        """Everything that reaches frappe, that is.

        `/assets/**` and `/files/**` are served by nginx (or the static
        middleware under `bench serve`) *before* the framework runs, so this
        hook never sees them and they do answer on the delivery host. That
        residual is public build output on a second public hostname -- no
        session, no escalation -- and is recorded in §2.2 rather than pretended
        away.
        """
        for path in (
            "/app/user",
            "/api/method/frappe.auth.get_logged_user",
            "/",
            "/seminary",
            "/login",
            "/private/files/anything.pdf",
        ):
            with self.subTest(path=path):
                self._request(path)
                with self.assertRaises(frappe.DoesNotExistError):
                    delivery.guard_delivery_host()

    def test_the_guard_lets_scorm_through_and_ignores_the_app_host(self):
        self._request("/scorm/x/y/z.html")
        delivery.guard_delivery_host()  # no raise

        self._request("/app/user", host=APP_HOST)
        delivery.guard_delivery_host()  # not our host; not our business

    # ------------------------------------------------------------- the token

    def test_a_forged_or_expired_token_is_a_404(self):
        for bad in ("", "x", "0" * 64, frappe.generate_hash(length=64)):
            with self.subTest(token=bad):
                response = self._get("index.html", token=bad)
                self.assertEqual(getattr(response, "status_code", 404), 404)

    def test_a_revoked_token_stops_working(self):
        self.assertEqual(self._get("index.html").status_code, 200)
        tokens.revoke(self.token)
        self.assertEqual(self._get("index.html").status_code, 404)

    def test_a_token_for_another_package_cannot_name_this_one(self):
        other = self._chapter("other")
        other_package = self._unpack(
            other,
            _zip([("B", "Other", "index.html")], nonce=frappe.generate_hash(length=6)),
        )
        stolen = tokens.mint("stu@test.invalid", other_package, other.name)
        response = self._get("index.html", token=stolen)
        self.assertEqual(response.status_code, 404)

    def test_the_session_decides_nothing(self):
        # The delivery origin has no session by design; authorisation is the
        # token and nothing else. Administrator without one gets a 404; a guest
        # with one gets the bytes.
        frappe.set_user("Administrator")
        self.assertEqual(self._get("index.html", token="0" * 64).status_code, 404)
        frappe.set_user("Guest")
        self.assertEqual(self._get("index.html").status_code, 200)
        frappe.set_user("Administrator")

    def test_a_token_survives_relaunch_so_the_cache_survives_with_it(self):
        again = tokens.mint("stu@test.invalid", self.package_name, self.chapter.name)
        self.assertEqual(again, self.token)

    # --------------------------------------------------------- addressing

    def test_a_member_the_package_never_declared_is_a_404(self):
        for path in (
            "nope.html",
            "a/nope.css",
            "../../../etc/passwd",
            "imsmanifest.xml/x",
        ):
            with self.subTest(path=path):
                self.assertEqual(self._get(path).status_code, 404)

    def test_every_declared_member_is_served(self):
        for member in ("index.html", "a/style.css", "media/clip.mp4"):
            with self.subTest(member=member):
                self.assertIn(self._get(member).status_code, (200, 302))

    def test_a_wrong_package_id_in_the_path_is_a_404(self):
        self.assertEqual(
            self._get("index.html", package_id="deadbeef").status_code, 404
        )

    def test_the_launcher_answers_at_the_package_root(self):
        response = self._get("")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("index.html", body)
        self.assertIn(APP_HOST, body)

    def test_the_launcher_carries_the_runtime_inline(self):
        # Inlined rather than served as a second file: any URL under the
        # package prefix is a member path, so a separate asset could be
        # shadowed by a package containing a file of that name.
        body = self._get("").get_data(as_text=True)
        self.assertIn("SeminaryScormRuntime", body)
        self.assertIn("LMSInitialize", body)
        self.assertNotIn("__RUNTIME__", body)
        self.assertNotIn("__CONFIG__", body)

    def test_the_launcher_posts_only_to_the_app_origin(self):
        body = self._get("").get_data(as_text=True)
        self.assertIn(f'"appOrigin": "https://{APP_HOST}"', body)
        self.assertNotIn('postMessage(message, "*")', body)

    def test_the_launcher_opens_the_sco_the_player_named(self):
        # A query string is right here and wrong for an asset: this is the
        # launcher, and nothing resolves relative to it.
        builder = EnvironBuilder(path="/scorm/x/y/", query_string="sco=B")
        builder.host = DELIVERY_HOST
        frappe.local.request = Request(builder.get_environ())

        two = frappe.get_doc("SCORM Package", self.package_name)
        two.append(
            "items", {"sco_identifier": "B", "title": "Second", "href": "a/style.css"}
        )
        two.save(ignore_permissions=True)

        path = f"scorm/{self.token}/{self.package.package_id}/"
        builder = EnvironBuilder(path="/" + path, query_string="sco=B")
        builder.host = DELIVERY_HOST
        frappe.local.request = Request(builder.get_environ())
        body = delivery.SCORMDelivery(path).render().get_data(as_text=True)
        self.assertIn('"index": 1', body)

    def test_an_unknown_sco_falls_back_to_the_first(self):
        path = f"scorm/{self.token}/{self.package.package_id}/"
        builder = EnvironBuilder(path="/" + path, query_string="sco=../../etc/passwd")
        builder.host = DELIVERY_HOST
        frappe.local.request = Request(builder.get_environ())
        body = delivery.SCORMDelivery(path).render().get_data(as_text=True)
        # Matched against the package's own items, never used as an index.
        self.assertIn('"index": 0', body)

    def test_the_launcher_seeds_the_package_state(self):
        body = self._get("").get_data(as_text=True)
        self.assertIn('"scos"', body)
        self.assertIn('"learner_id"', body)
        # Never the email, never the docname (§2.9).
        self.assertNotIn(frappe.session.user, body)

    def test_the_launcher_cannot_be_shadowed_by_a_member(self):
        # A member path can never be empty (the unpack job refuses it), so the
        # root is ours by construction rather than by a reserved name.
        self.assertNotIn("", self.package.get_inventory())

    # ------------------------------------------------------- how it is served

    def test_text_is_proxied_from_this_origin_with_the_recorded_type(self):
        response = self._get("index.html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(response.headers["Origin-Agent-Cluster"], "?1")
        self.assertIn(
            f"frame-ancestors 'self' https://{APP_HOST}",
            response.headers["Content-Security-Policy"],
        )
        # Read the iterable, not `get_data`: the response is in direct
        # passthrough mode because the member is *streamed* from the object
        # store rather than buffered into the worker.
        body = b"".join(response.response).decode()
        self.assertIn("<h1>index.html</h1>", body)

    def test_the_app_security_headers_stay_off_this_origin(self):
        """`X-Frame-Options: SAMEORIGIN` on a delivery response forbids the app
        from framing the package -- an empty player, in every browser, with
        nothing in any log. Found on the first live pass, not by any unit test,
        because it takes a real cross-origin request to see it."""
        from seminary.seminary import http_headers

        self._request("/scorm/x/y/z.html")
        response = Response()
        http_headers.apply_security_headers(response=response)
        self.assertNotIn("X-Frame-Options", response.headers)
        self.assertNotIn("Content-Security-Policy-Report-Only", response.headers)

        # ...and the app origin still gets all of them.
        self._request("/", host=APP_HOST)
        response = Response()
        http_headers.apply_security_headers(response=response)
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")

    def test_frame_ancestors_names_both_origins_and_only_those(self):
        """`'self'` **and** the app origin, and both are load-bearing.

        The app frames the launcher, so the app origin must be named. The
        launcher then frames the SCO, and the launcher is on the *delivery*
        origin -- so without `'self'` the inner frame's ancestor chain is
        [launcher@delivery, player@app], the delivery origin is not in the list,
        and the browser refuses it. The outer frame loads, the inner one does
        not, and the player is a grey box.

        This test asserted the opposite until the first real browser pass, which
        is the only place the ancestor chain exists: a server-side test renders
        one response and never stacks two documents inside each other.
        """
        policy = self._get("index.html").headers["Content-Security-Policy"]
        directive = [
            part.strip()
            for part in policy.split(";")
            if part.strip().startswith("frame-ancestors")
        ][0]
        sources = directive.split()[1:]

        self.assertIn("'self'", sources)
        self.assertIn(f"https://{APP_HOST}", sources)
        # Still a closed list -- this origin and the one app origin, nobody
        # else. A wildcard here would hand any site the ability to frame a
        # package and drive it.
        self.assertEqual(len(sources), 2, policy)
        self.assertNotIn("*", sources)

    def test_an_unknown_app_origin_refuses_to_serve(self):
        # A delivery origin that cannot name the origin allowed to frame it is
        # misconfigured; serving with the wrong `frame-ancestors` is worse than
        # not serving (§2.14 -- refuse rather than degrade).
        with patch.dict(frappe.conf, {"host_name": None, "scorm_app_origin": None}):
            self.assertEqual(self._get("index.html").status_code, 404)

    def test_a_dot_html_member_is_served_despite_the_router(self):
        """`resolve_path` strips a trailing `.html` before a renderer is
        consulted, so every HTML member of every package 404d while its
        stylesheets served fine. The renderer reads the URL, not the endpoint."""
        renderer = delivery.SCORMDelivery(
            # what frappe actually hands us for `.../index.html`
            f"scorm/{self.token}/{self.package.package_id}/index"
        )
        self._request(f"/scorm/{self.token}/{self.package.package_id}/index.html")
        self.assertEqual(renderer.render().status_code, 200)

    def test_media_redirects_to_a_presigned_url(self):
        response = self._get("media/clip.mp4")
        self.assertEqual(response.status_code, 302)
        self.assertIn("objectstore.invalid", response.headers["Location"])
        self.assertIn("private", response.headers["Cache-Control"])

    def test_a_stylesheet_is_proxied_not_redirected(self):
        # A stylesheet can carry `url(...)`, which would resolve against the
        # object store if the browser had been redirected to fetch it.
        self.assertEqual(self._get("a/style.css").status_code, 200)

    def test_an_etag_match_answers_304(self):
        first = self._get("index.html")
        etag = first.headers["ETag"]
        self._request(
            f"/scorm/{self.token}/{self.package.package_id}/index.html",
            headers={"If-None-Match": etag},
        )
        renderer = delivery.SCORMDelivery(
            f"scorm/{self.token}/{self.package.package_id}/index.html"
        )
        self.assertEqual(renderer.render().status_code, 304)
