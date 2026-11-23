# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""The recommender's emailed link opens the form signed out (102b's seed found it didn't)."""

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.www import seminary as portal

WITH_TOKEN = {"token": frappe.generate_hash(length=10)}


class TestRecommenderLink(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.form_dict = frappe._dict()

	def _open(self, path, query=None):
		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict(query or {})
		with patch.object(portal.frappe, "request", SimpleNamespace(path=path), create=True):
			return portal._guest_may_open()

	def test_a_guest_with_a_token_may_open_the_form(self):
		self.assertTrue(self._open("/seminary/recommender-form/RL-000001", WITH_TOKEN))

	def test_without_a_token_a_guest_signs_in(self):
		self.assertFalse(self._open("/seminary/recommender-form/RL-000001"))

	def test_a_token_opens_no_other_portal_page(self):
		self.assertFalse(self._open("/seminary/courses", WITH_TOKEN))
		self.assertFalse(self._open("/seminary/recommender-form/RL-1/extra", WITH_TOKEN))

	def test_old_links_redirect_with_their_token(self):
		rules = [r for r in frappe.get_hooks("website_redirects") if "recommender-form" in r["source"]]
		self.assertEqual(rules[0]["target"], r"/seminary/recommender-form/\1")
		self.assertTrue(rules[0]["forward_query_parameters"])
