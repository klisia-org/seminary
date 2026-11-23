# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""102 §8: school colours below 4.5:1 are refused when they change, never before."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import contrast
from seminary.seminary.portal_theme import failing_pairs

COLOUR_FIELDS = (
	"primary_color",
	"background_color",
	"text_color",
	"navbar_background",
	"footer_background",
)

#: A scheme that passes every pair: dark text and links on white, white on navy bars.
GOOD = {
	"primary_color": "#0d3049",
	"background_color": "#ffffff",
	"text_color": "#1a2330",
	"navbar_background": "",
	"footer_background": "",
}


class TestContrastArithmetic(IntegrationTestCase):
	def test_ratios(self):
		self.assertAlmostEqual(contrast.contrast_ratio("#000", "#fff"), 21.0)
		self.assertAlmostEqual(contrast.contrast_ratio("#777777", "#777777"), 1.0)
		self.assertAlmostEqual(
			contrast.contrast_ratio("rgb(0, 0, 0)", "#ffffff"), contrast.contrast_ratio("#000", "#fff")
		)
		self.assertIsNone(contrast.contrast_ratio("rgba(0,0,0,0.5)", "#fff"))
		self.assertIsNone(contrast.contrast_ratio("", "#fff"))

	def test_a_ratio_just_short_never_reads_as_the_minimum(self):
		self.assertEqual(contrast.format_ratio(4.4999), "4.49:1")

	def test_old_names_still_work(self):
		from seminary.overrides import _contrast, _luminance, bar_ink

		self.assertEqual(bar_ink("#0d3049"), "#ffffff")
		self.assertAlmostEqual(_contrast(_luminance("#000"), _luminance("#fff")), 21.0)


class TestWebsiteBrandingContrast(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		branding = frappe.get_single("Website Branding")
		self.saved = {f: branding.get(f) for f in (*COLOUR_FIELDS, "hero_headline")}
		# Start from a passing scheme, written directly so this setup is not itself
		# refused by whatever the site holds.
		for field, value in GOOD.items():
			frappe.db.set_single_value("Website Branding", field, value)

	def tearDown(self):
		frappe.set_user("Administrator")
		for field, value in self.saved.items():
			frappe.db.set_single_value("Website Branding", field, value)
		frappe.clear_document_cache("Website Branding", "Website Branding")

	def _save(self, **fields):
		branding = frappe.get_single("Website Branding")
		branding.update(fields)
		branding.save(ignore_permissions=True)

	def test_light_text_on_white_is_refused_with_the_ratio(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			self._save(text_color="#999999")
		message = str(caught.exception)
		self.assertIn(contrast.format_ratio(contrast.contrast_ratio("#999999", "#ffffff")), message)
		self.assertIn("4.50:1", message)

	def test_a_mid_tone_primary_fails_links_and_the_bars(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			self._save(primary_color="#6f8aa3")
		message = str(caught.exception)
		self.assertIn("Links", message)
		self.assertIn("Navbar Background", message)
		self.assertIn("Footer Background", message)

	def test_a_mid_tone_bar_is_refused(self):
		# Neither white nor near-black reaches 4.5:1 on this grey.
		with self.assertRaises(frappe.ValidationError):
			self._save(navbar_background="#777777")

	def test_a_passing_change_saves(self):
		self._save(text_color="#000000", navbar_background="#ffffff")
		self.assertEqual(frappe.db.get_single_value("Website Branding", "navbar_background"), "#ffffff")

	def test_unchanged_failing_colours_do_not_block_other_fields(self):
		frappe.db.set_single_value("Website Branding", "text_color", "#cccccc")
		frappe.clear_document_cache("Website Branding", "Website Branding")
		self._save(hero_headline="ZZT 102 headline")
		self.assertEqual(frappe.db.get_single_value("Website Branding", "hero_headline"), "ZZT 102 headline")

	def test_the_patch_reports_and_changes_nothing(self):
		from seminary.seminary.patches import adr102_report_colour_contrast

		frappe.db.set_single_value("Website Branding", "text_color", "#cccccc")
		frappe.clear_document_cache("Website Branding", "Website Branding")
		before = frappe.db.count("Error Log")
		adr102_report_colour_contrast.execute()
		self.assertEqual(frappe.db.get_single_value("Website Branding", "text_color"), "#cccccc")
		self.assertEqual(frappe.db.count("Error Log"), before + 1)
		log = frappe.get_last_doc("Error Log")
		self.assertIn("contrast minimum", log.method)
		log.delete(ignore_permissions=True)


class TestPortalThemePairs(IntegrationTestCase):
	def test_no_theme_has_no_failures(self):
		self.assertEqual(failing_pairs(None), [])
		self.assertEqual(failing_pairs({"light": {}, "dark": {}}), [])

	def test_a_set_side_is_checked_against_the_default(self):
		[pair] = failing_pairs({"light": {"--ink-gray-8": "#bbbbbb"}})
		self.assertEqual(
			(pair["mode"], pair["text"], pair["background"], pair["background_value"]),
			("light", "--ink-gray-8", "--surface-cards", "#ffffff"),
		)
		self.assertLess(pair["ratio"], 4.5)
		self.assertTrue(pair["ratio_text"].endswith(":1"))

	def test_each_mode_is_checked_on_its_own(self):
		# White page in dark mode: frappe-ui's light-grey dark inks fail on it.
		found = failing_pairs({"dark": {"--surface-white": "#ffffff"}})
		self.assertTrue(found)
		self.assertEqual({p["mode"] for p in found}, {"dark"})

	def test_brand_is_text_on_the_page(self):
		[pair] = failing_pairs({"light": {"--portal-brand": "#ffeb3b"}})
		self.assertEqual((pair["text"], pair["background"]), ("--portal-brand", "--surface-white"))
		self.assertEqual(failing_pairs({"light": {"--portal-brand": "#0d3049"}}), [])

	def test_button_text_on_the_button(self):
		[pair] = failing_pairs({"light": {"--surface-gray-7": "#fde047"}})
		self.assertEqual((pair["text"], pair["background"]), ("--ink-white", "--surface-gray-7"))
		self.assertEqual(
			failing_pairs({"light": {"--surface-gray-7": "#fde047", "--ink-white": "#0f0f0f"}}), []
		)

	def test_a_link_alone_is_checked_only_when_its_page_is_known(self):
		# frappe-ui's own link colour is not filled in, so a page alone is not judged by it.
		self.assertEqual(failing_pairs({"light": {"--surface-white": "#fafafa"}}), [])
		self.assertTrue(failing_pairs({"light": {"--ink-blue-link": "#9ecbff"}}))

	def test_a_translucent_colour_is_skipped(self):
		self.assertEqual(failing_pairs({"light": {"--ink-gray-9": "rgba(0,0,0,0.2)"}}), [])
