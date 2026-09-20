# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p010 Block B: abuse limits (A06-2, A09-4, A09-2, A04-5).

At baseline the app had exactly **four** `rate_limit` decorators, and all four
were on the *billable* geocoding and tax-ID calls -- the endpoints that cost the
school money, not the ones that cost it data. Nothing capped an anonymous
caller, and nothing counted a failed guess.

The first test here is a contract test rather than a behaviour test, for the
same reason F13 was: the guest surface is where a new endpoint is most likely to
be added without one, and a hand count is true only on the day it is made.
"""

import ast
import pathlib

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import security_log


def _decorator_names(node):
    out = []
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        while isinstance(target, ast.Attribute):
            target = target.value
        if isinstance(target, ast.Name):
            out.append(target.id)
        if isinstance(dec, ast.Call):
            func = dec.func
            if isinstance(func, ast.Attribute):
                out.append(func.attr)
            elif isinstance(func, ast.Name):
                out.append(func.id)
    return out


def _is_guest_endpoint(node):
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        func = dec.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name != "whitelist":
            continue
        for kw in dec.keywords:
            if kw.arg == "allow_guest" and getattr(kw.value, "value", False) is True:
                return True
    return False


class TestP010GuestSurface(IntegrationTestCase):
    def _guest_endpoints(self):
        root = pathlib.Path(frappe.get_app_path("seminary"))
        for path in root.rglob("*.py"):
            if "/tests/" in str(path) or "/patches/" in str(path):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and _is_guest_endpoint(node):
                    yield path, node

    def test_every_guest_endpoint_is_rate_limited(self):
        """17 guest endpoints, 4 decorated, and the 4 were the ones that cost
        money rather than the ones that leak or flood (p005a A06-2)."""
        found = list(self._guest_endpoints())
        # Guard against the vacuous pass: an AST walk that silently matches
        # nothing would satisfy the assertion below forever (the F13 lesson).
        self.assertGreaterEqual(
            len(found), 15, "the guest-surface sweep found almost nothing"
        )
        naked = [
            f"{path.name}:{node.name}"
            for path, node in found
            if "rate_limit" not in _decorator_names(node)
        ]
        self.assertEqual(naked, [], f"guest endpoint with no rate limit: {naked}")

    def test_the_limit_is_inside_the_whitelist(self):
        """Decorators apply bottom-up. With `@rate_limit` *above*
        `@frappe.whitelist`, the whitelist registry holds the **unwrapped**
        function and the limit silently never applies -- it looks right in the
        source and does nothing. Caught while writing this block."""
        for path, node in self._guest_endpoints():
            names = [
                (
                    d.func.attr
                    if isinstance(d.func, ast.Attribute)
                    else getattr(d.func, "id", "")
                )
                for d in node.decorator_list
                if isinstance(d, ast.Call)
            ]
            if "rate_limit" not in names or "whitelist" not in names:
                continue
            self.assertLess(
                names.index("whitelist"),
                names.index("rate_limit"),
                f"{path.name}:{node.name}: @rate_limit must sit below @frappe.whitelist",
            )


class TestP010CheckinCodes(IntegrationTestCase):
    """~24.9 bits, compared with `!=`, consumed by an endpoint with no limit
    (p005a A04-5). The code stays short on purpose -- it is read aloud in a
    classroom -- so the attempt counter is what makes it safe."""

    def _sources(self):
        for module in ("course_checkin.py", "chapel.py"):
            yield pathlib.Path(frappe.get_app_path("seminary", "seminary", module))

    def test_both_compares_are_constant_time(self):
        for path in self._sources():
            body = path.read_text(encoding="utf-8")
            self.assertIn("compare_digest", body, path.name)
            self.assertNotIn("given != expected", body, path.name)

    def test_both_consuming_endpoints_are_counted(self):
        for path in self._sources():
            body = path.read_text(encoding="utf-8")
            self.assertIn("rate_limit(", body, f"{path.name} has no attempt counter")

    def test_a_non_ascii_code_does_not_explode(self):
        """`hmac.compare_digest` raises TypeError on a non-ASCII `str`, so a
        student with an accented keyboard would have got a 500 rather than
        "incorrect code"."""
        from seminary.seminary import course_checkin

        settings = frappe._dict({"require_course_checkin_code": 1})
        with self.assertRaises(frappe.ValidationError):
            course_checkin._validate_code({"checkin_code": "ABCDE"}, settings, "ÁÇÕÉÑ")

    def test_a_correct_code_still_passes(self):
        from seminary.seminary import course_checkin

        settings = frappe._dict({"require_course_checkin_code": 1})
        # Lower case and padding, the way a student actually types it.
        course_checkin._validate_code({"checkin_code": "ABCDE"}, settings, "  abcde ")

    def test_a_wrong_code_is_recorded(self):
        from seminary.seminary import course_checkin

        settings = frappe._dict({"require_course_checkin_code": 1})
        setattr(frappe.local, security_log._FLAG, False)
        before = security_log.denial_counts().get("checkin_code", 0)
        with self.assertRaises(frappe.ValidationError):
            course_checkin._validate_code({"checkin_code": "ABCDE"}, settings, "ZZZZZ")
        after = security_log.denial_counts().get("checkin_code", 0)
        self.assertEqual(after, before + 1)


class TestP010AccessLogFlood(IntegrationTestCase):
    def test_a_guest_read_writes_no_access_log_row(self):
        """`storage.download_file` is allow_guest, and a *public* offloaded file
        resolves for anybody -- so every unauthenticated GET was a deferred
        insert plus a presign, with no rate limit (p005a A09-2). The row records
        no identity for a guest: a write with no reader."""
        body = pathlib.Path(
            frappe.get_app_path("seminary", "storage", "api.py")
        ).read_text(encoding="utf-8")
        guard = 'frappe.session.user != "Guest" and _is_initial_request()'
        self.assertIn(guard, body)

    def test_the_throttled_caller_is_logged_too(self):
        """frappe's `rate_limit` raises `RateLimitExceededError` directly, so
        without 429 here a throttled attacker is the one denial the hook
        misses."""
        from werkzeug.wrappers import Response

        setattr(frappe.local, security_log._FLAG, False)
        security_log.log_denied_response(response=Response("slow down", status=429))
        self.assertEqual(security_log.denial_counts().get("http_429", 0) >= 1, True)
