# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""A school that is not a seminary turns seminary features off, and they leave
Desk navigation and the public site without being removed (institution.py)."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary import desk_nav
from seminary.seminary.institution import (
    SEMINARY_ONLY_DOCTYPES,
    seminary_features_enabled,
)


def _set(value):
    frappe.db.set_single_value("Seminary Settings", "seminary_features", value)
    # desk_nav memoises the names it has looked up for the request.
    frappe.local.desk_nav_names = None


class TestInstitutionProfile(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    def tearDown(self):
        _set(1)
        super().tearDown()

    def test_a_site_that_never_saved_the_switch_is_a_seminary(self):
        frappe.db.delete(
            "Singles", {"doctype": "Seminary Settings", "field": "seminary_features"}
        )
        frappe.local.desk_nav_names = None
        self.assertTrue(seminary_features_enabled())

    def test_a_seminary_is_the_default(self):
        self.assertTrue(seminary_features_enabled())
        for doctype in SEMINARY_ONLY_DOCTYPES:
            self.assertTrue(desk_nav.target_exists("DocType", doctype), doctype)

    def test_turning_it_off_hides_every_seminary_only_target(self):
        _set(0)
        self.assertFalse(seminary_features_enabled())
        for doctype in SEMINARY_ONLY_DOCTYPES:
            self.assertFalse(desk_nav.target_exists("DocType", doctype), doctype)

    def test_everything_else_stays(self):
        _set(0)
        for doctype in ("Program", "Course", "Student", "Program Enrollment"):
            self.assertTrue(desk_nav.target_exists("DocType", doctype), doctype)

    def test_the_gate_list_and_the_module_agree(self):
        gated = (frappe.get_hooks("desk_target_gates") or {}).get("DocType") or {}
        self.assertEqual(set(gated), set(SEMINARY_ONLY_DOCTYPES))

    def test_the_sidebar_loses_the_link_and_the_section_it_empties(self):
        _set(0)
        sidebars = {
            "Seminary": {
                "items": [
                    {"type": "Section Break", "label": "Worship"},
                    {"type": "Link", "link_type": "DocType", "link_to": "Chapel"},
                    {"type": "Section Break", "label": "Academics"},
                    {"type": "Link", "link_type": "DocType", "link_to": "Program"},
                ]
            }
        }
        desk_nav.prune_sidebar_items(sidebars)
        self.assertEqual(
            [i.get("label") or i.get("link_to") for i in sidebars["Seminary"]["items"]],
            ["Academics", "Program"],
        )

    def test_nothing_is_deleted(self):
        _set(0)
        for doctype in SEMINARY_ONLY_DOCTYPES:
            self.assertTrue(frappe.db.exists("DocType", doctype), doctype)

    def test_the_public_menu_loses_the_doctrine_link(self):
        from seminary.overrides import hide_seminary_only_menu_items

        def menu():
            return frappe._dict(
                top_bar_items=[
                    frappe._dict(label="Home", url="/"),
                    frappe._dict(label="What We Believe", url="/what-we-believe"),
                ]
            )

        seminary = menu()
        hide_seminary_only_menu_items(seminary)
        self.assertEqual(len(seminary.top_bar_items), 2)

        _set(0)
        other = menu()
        hide_seminary_only_menu_items(other)
        self.assertEqual([i.label for i in other.top_bar_items], ["Home"])

    def test_the_public_doctrine_page_is_gone(self):
        from seminary.www import what_we_believe

        _set(0)
        with self.assertRaises(frappe.PageDoesNotExistError):
            what_we_believe.get_context(frappe._dict())

    def test_the_public_doctrine_page_is_there_for_a_seminary(self):
        from seminary.www import what_we_believe

        context = frappe._dict()
        what_we_believe.get_context(context)
        self.assertEqual(context.title, "What We Believe")
