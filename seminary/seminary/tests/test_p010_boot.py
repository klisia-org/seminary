# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p010 Block F, A02-1 residual: what the SPA boot ships to the browser.

`www/seminary.py` builds a dict that `seminary.html` splats onto `window[key]`.
p006 F8 removed the session id and deferred `sysdefaults` "pending a field
inventory". The inventory: `frappe.defaults.get_defaults()` returned 92 keys,
**none** of them read by `frontend/src`, `portal-shell/src`, `seminary/public`
or frappe-ui -- and among them a security-posture inventory (lockout
thresholds, whether 2FA is on, password policy strength, session expiry,
whether backups are encrypted).

These tests pin the boot surface both ways: the removed key stays removed, and
the key the SPA genuinely depends on stays present.
"""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.www.seminary import get_boot_data

# Ships to every page load; each one an attacker would otherwise read for free.
POSTURE_KEYS = (
    "allow_error_traceback",
    "enable_two_factor_auth",
    "allow_consecutive_login_attempts",
    "minimum_password_score",
    "session_expiry",
    "encrypt_backup",
    "document_share_key_expiry",
    "max_signups_allowed_per_hour",
)


class TestP010Boot(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def test_sysdefaults_is_not_in_boot(self):
        self.assertNotIn("sysdefaults", get_boot_data())

    def test_no_posture_value_reaches_the_page_under_any_key(self):
        """Not just the key: the values must not arrive by another route."""
        boot = get_boot_data()
        flat = frappe.as_json(boot)
        for key in POSTURE_KEYS:
            self.assertNotIn(key, flat, f"{key} is still reaching the browser")

    def test_csrf_token_is_still_shipped(self):
        """The one boot value the SPA really uses -- 25 call sites."""
        boot = get_boot_data()
        self.assertTrue(boot.get("csrf_token"))

    def test_boot_surface_is_exactly_what_is_declared(self):
        """A new key must be a deliberate edit, not a silent addition."""
        self.assertEqual(
            set(get_boot_data()),
            {"user", "csrf_token", "sitename", "session"},
        )

    def test_session_carries_only_the_user(self):
        """p006 F8: the sid stays in the cookie."""
        self.assertEqual(set(get_boot_data()["session"]), {"user"})
