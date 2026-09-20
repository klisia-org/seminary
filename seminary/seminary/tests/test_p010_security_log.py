# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p010 Block A: the `seminary.security` logger and denial counter (A09-1, A09-3, A10-2).

p005a A09-3's sharpest observation is the reason this module exists: **a
successful privilege-escalation attempt leaves nothing.** Frappe renders
`PermissionError` as a bare 403 with no row anywhere, and not one of seminary's
own `frappe.throw(..., PermissionError)` sites logged first. Phases 0-2 made the
app refuse; nothing made the refusal *visible*.

Two of these tests are contract tests rather than behaviour tests -- the
`print()` sweep and the redaction rule -- because both are properties that decay
silently. p005a checked by hand that no secret reaches any log and found the app
clean; a hand check is true on the day it is made.
"""

import logging
import pathlib
import re

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.wrappers import Response

from seminary.seminary import security_log


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


class TestP010SecurityLog(IntegrationTestCase):
    def setUp(self):
        self.capture = _Capture()
        self.logger = security_log.logger()
        self.logger.addHandler(self.capture)
        self._reset_flag()

    def tearDown(self):
        self.logger.removeHandler(self.capture)
        self._reset_flag()

    def _reset_flag(self):
        setattr(frappe.local, security_log._FLAG, False)

    # ---------------------------------------------------------------- logging

    def test_a_denial_writes_one_line_naming_the_actor_and_the_gate(self):
        security_log.record_denial("permission", gate="require_grader")
        self.assertEqual(len(self.capture.lines), 1)
        line = self.capture.lines[0]
        self.assertIn('"kind": "permission"', line)
        self.assertIn('"gate": "require_grader"', line)
        self.assertIn(frappe.session.user, line)

    def test_the_counter_moves(self):
        before = security_log.denial_counts().get("permission", 0)
        security_log.record_denial("permission", gate="require_registrar")
        after = security_log.denial_counts().get("permission", 0)
        self.assertEqual(after, before + 1)

    def test_one_denial_is_counted_once(self):
        """A `guards` throw is also observed as a 403 by the `after_request`
        hook. Without the request-local flag every deliberate denial in the app
        would be double-counted, which would make the counter useless for
        exactly the question it exists to answer."""
        before = security_log.denial_counts()
        security_log.record_denial("permission", gate="require_enrolled")
        security_log.log_denied_response(response=Response("no", status=403))
        self.assertEqual(len(self.capture.lines), 1)
        after = security_log.denial_counts()
        self.assertEqual(
            after.get("http_403", 0), before.get("http_403", 0), "counted twice"
        )

    # -------------------------------------------------------------- redaction

    def test_sensitive_keys_are_dropped_by_name_before_formatting(self):
        """The property p005a verified by hand, enforced instead of trusted.
        A logger that leaks a token is worse than no logger."""
        security_log.record_denial(
            "permission",
            access_key="sekrit-value",
            request_token="tok_abc123",  # nosec B106 -- a fake token, the point of the test
            csrf_token="csrf_abc",
            api_secret="s3cret",  # pragma: allowlist secret
            password="hunter2",  # pragma: allowlist secret
            sid="abc.def",
            signature="deadbeef",
            payload={"card": "4111111111111111"},
            gate="require_grader",
        )
        line = self.capture.lines[0]
        for leaked in (
            "sekrit-value",
            "tok_abc123",
            "csrf_abc",
            "s3cret",
            "hunter2",
            "abc.def",
            "deadbeef",
            "4111111111111111",
        ):
            self.assertNotIn(leaked, line, f"{leaked} reached the log")
        self.assertIn("[redacted]", line)
        # And the harmless context still survives, or redaction is just deletion.
        self.assertIn("require_grader", line)

    def test_a_long_value_is_truncated(self):
        security_log.record_denial("permission", gate="g", target="x" * 5000)
        self.assertLess(len(self.capture.lines[0]), 1000)

    # ------------------------------------------------------------- the 403 hook

    def test_the_hook_is_registered(self):
        self.assertIn(
            "seminary.seminary.security_log.log_denied_response",
            frappe.get_hooks("after_request") or [],
        )

    def test_a_good_response_is_not_logged(self):
        security_log.log_denied_response(response=Response("ok", status=200))
        self.assertEqual(self.capture.lines, [])

    def test_a_403_is_logged(self):
        security_log.log_denied_response(response=Response("no", status=403))
        self.assertEqual(len(self.capture.lines), 1)
        self.assertIn('"kind": "http_403"', self.capture.lines[0])

    def test_logging_never_costs_the_response(self):
        """`after_request` runs on the way out. Raising there turns a good
        response into a 500, and turning a 403 into a 500 would be this
        module making the site *less* safe than no logging at all."""

        class Exploding:
            @property
            def status_code(self):
                raise RuntimeError("boom")

        security_log.log_denied_response(response=Exploding())
        security_log.record_denial("permission", gate=object())  # unformattable

    # ----------------------------------------------- the gates feed the logger

    def test_a_guards_denial_is_logged(self):
        from seminary.seminary import guards

        self.assertTrue(hasattr(guards, "_deny"))
        with self.assertRaises(frappe.PermissionError):
            guards._deny("nope", "require_registrar", target="PE-0001")
        self.assertEqual(len(self.capture.lines), 1)
        self.assertIn("require_registrar", self.capture.lines[0])
        self.assertIn("PE-0001", self.capture.lines[0])


class TestP010LogHygiene(IntegrationTestCase):
    """Contract tests. Both properties decay silently, and a hand sweep is only
    true on the day it is made (p005a counted 3 stray prints, then 10, then 36)."""

    #: `bench` console output by design -- a migration or a seed says what it did.
    _CONSOLE_OK = (
        "/patches/",
        "/demo/",
        "/tests/",
        "workspaces_bootstrap.py",
        "test_course_pack.py",
        # Documented `bench execute` entry point; prints the registered URL.
        "telegram_adapter.py",
    )

    def _sources(self):
        root = pathlib.Path(frappe.get_app_path("seminary"))
        for path in root.rglob("*.py"):
            text = str(path)
            if any(marker in text for marker in self._CONSOLE_OK):
                continue
            yield path

    def test_no_request_path_module_prints_to_stdout(self):
        """A `print` in a request path goes to the worker's stdout: unrotated,
        unattributed, and mixed into every other site's output on a shared
        bench. `api.py` was printing an entire assessment payload on every
        grade write (p010 H2)."""
        offenders = []
        pattern = re.compile(r"^\s*print\(", re.MULTILINE)
        for path in self._sources():
            for match in pattern.finditer(path.read_text(encoding="utf-8")):
                line = path.read_text(encoding="utf-8")[: match.start()].count("\n") + 1
                offenders.append(f"{path.name}:{line}")
        self.assertEqual(offenders, [], f"stray print(): {offenders}")

    def test_the_webhook_gives_one_message_for_every_failure(self):
        """`comms.webhook` is `allow_guest`. Three distinguishable errors let an
        anonymous caller enumerate Channel Provider Account names and their
        enabled state -- the last of p005's three error-text oracles."""
        source = pathlib.Path(
            frappe.get_app_path("seminary", "seminary", "comms.py")
        ).read_text(encoding="utf-8")
        body = source[
            source.index("def webhook(") : source.index("def _webhook_payload")
        ]
        # The *throw*, not the string: the comment above the fix legitimately
        # quotes the two old messages to say what was wrong with them.
        self.assertNotIn('_("Unknown account.")', body)
        self.assertNotIn('_("Account disabled.")', body)
        self.assertEqual(body.count('_("Webhook rejected.")'), 1)
        # The distinction is kept -- in the log, where a prober cannot read it.
        for reason in ("unknown-account", "account-disabled", "verification-failed"):
            self.assertIn(reason, body)
