# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""The portal page carries the school's name, favicon and theme."""

import pathlib
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

import seminary
from seminary.www import seminary as portal


class TestPortalBrand(UnitTestCase):
    def settings(self, **values):
        return frappe._dict({"app_name": None, "favicon": None, **values})

    def test_the_school_name_and_favicon_win(self):
        with patch.object(frappe, "get_cached_doc", return_value=self.settings(app_name="Jala University", favicon="/files/j.png")):
            self.assertEqual(portal.portal_brand(), ("Jala University", "/files/j.png"))

    def test_without_them_it_is_seminary_erp(self):
        with patch.object(frappe, "get_cached_doc", return_value=self.settings()):
            self.assertEqual(portal.portal_brand(), (portal.DEFAULT_TITLE, portal.DEFAULT_FAVICON))

    def test_frappes_default_app_name_is_not_a_school(self):
        with patch.object(frappe, "get_cached_doc", return_value=self.settings(app_name="Frappe")):
            self.assertEqual(portal.portal_brand()[0], portal.DEFAULT_TITLE)

    def test_the_page_templates_read_the_context(self):
        """The built page is copied from frontend/index.html at build time;
        both must take title, favicon and the hooked stylesheets from context."""
        root = pathlib.Path(seminary.__file__).parent
        for page in (root / "www" / "seminary.html", root.parent / "frontend" / "index.html", root / "templates" / "pages" / "seminary_dev.html"):
            if not page.exists():
                continue
            html = page.read_text()
            self.assertIn("{{ title }}", html, page)
            self.assertIn("{{ favicon }}", html, page)
            self.assertIn("portal_css", html, page)
