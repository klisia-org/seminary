# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p017: the portal theme slot.

Without an app supplying a theme the portal page must be byte-for-byte what it was;
with one, only allow-listed variables, colour values, fonts and logo options get
through. The hook is a theme, not a channel for arbitrary CSS.
"""

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from seminary.seminary import portal_theme

THEME = {
    "light": {"--surface-white": "#fafafa", "--portal-brand": "rgb(13, 48, 73)"},
    "dark": {"--surface-white": "#101010"},
    "fonts": {"heading": "Poppins", "body": "Inter"},
    "logo": {"placement": "Wide", "size": "Large"},
}


_current = {}


def _hook():
    return _current.get("theme")


class TestP017PortalTheme(UnitTestCase):
    def _with(self, theme):
        _current["theme"] = theme
        hooks = ["seminary.seminary.tests.test_p017_portal_theme._hook"]
        return patch.object(
            frappe,
            "get_hooks",
            lambda name, *a, **k: hooks if name == "portal_theme" else [],
        )

    def test_no_hook_renders_nothing(self):
        with patch.object(frappe, "get_hooks", lambda *a, **k: []):
            theme = portal_theme.get_portal_theme()
        self.assertIsNone(theme)
        self.assertEqual(portal_theme.render_head(theme), "")
        self.assertIsNone(portal_theme.boot_logo(theme))

    def test_theme_renders_both_modes(self):
        with self._with(THEME):
            theme = portal_theme.get_portal_theme()
        head = str(portal_theme.render_head(theme))
        self.assertIn(
            "html:not([data-theme='dark']){--portal-brand:rgb(13, 48, 73);--surface-white:#fafafa;}",
            head,
        )
        self.assertIn("html[data-theme='dark']{--surface-white:#101010;}", head)
        self.assertIn('font-family:"Poppins"', head)
        self.assertIn("brand_fonts.css", head)
        self.assertEqual(
            portal_theme.boot_logo(theme), {"placement": "Wide", "size": "Large"}
        )

    def test_inter_only_does_not_load_the_font_file(self):
        theme = portal_theme.clean({"fonts": {"heading": "Inter", "body": "Inter"}})
        self.assertNotIn("brand_fonts.css", str(portal_theme.render_head(theme)))

    def test_only_allowed_values_get_through(self):
        theme = portal_theme.clean(
            {
                "light": {
                    "--surface-white": "#fff;}</style><script>alert(1)</script>",
                    "--ink-red-4": "#ff0000",  # status colours are not themeable
                    "background": "#fff",
                    "--ink-gray-8": "var(--x)",
                    "--ink-gray-9": "#123456",
                },
                "fonts": {"body": "Comic Sans", "heading": '"><script>'},
                "logo": {"placement": "Floating", "size": "Huge"},
            }
        )
        self.assertEqual(theme["light"], {"--ink-gray-9": "#123456"})
        self.assertEqual(theme["fonts"], {})
        self.assertEqual(theme["logo"], {})
        head = str(portal_theme.render_head(theme))
        self.assertNotIn("<script", head)
        self.assertNotIn("brand_fonts.css", head)

    def test_failing_hook_leaves_the_portal_unthemed(self):
        def boom():
            raise RuntimeError("theme broke")

        with (
            patch.object(frappe, "get_hooks", lambda *a, **k: ["x.y"]),
            patch.object(frappe, "get_attr", lambda path: boom),
            patch.object(frappe, "log_error"),
        ):
            self.assertIsNone(portal_theme.get_portal_theme())
