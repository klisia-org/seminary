# Copyright (c) 2026, Seminary and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.website.utils import clear_website_cache

from seminary.seminary import contrast

#: What a blank colour falls back to on the public pages (website_brand.css).
CSS_FALLBACKS = {
	"primary_color": "#0d3049",
	"background_color": "#ffffff",
	"text_color": "#1a2330",
}

BAR_FIELDS = ("navbar_background", "footer_background")


def _colour(doc, fieldname):
	return (doc.get(fieldname) or "").strip() or CSS_FALLBACKS.get(fieldname, "")


def failing_pairs(doc):
	"""The colour pairs below the WCAG minimum (102 §8): a dict per pair with the
	fields it reads, its ratio and a message. A pair that can't be read is skipped."""
	label = doc.meta.get_label
	minimum = contrast.format_ratio(contrast.MIN_RATIO)
	background = _colour(doc, "background_color")
	pairs = [
		(
			("text_color", "background_color"),
			_colour(doc, "text_color"),
			background,
			_("{0} on {1} is {2}; it needs at least {3}.").format(
				label("text_color"), label("background_color"), "{ratio}", minimum
			),
		),
		(
			("primary_color", "background_color"),
			_colour(doc, "primary_color"),
			background,
			_("Links in {0} on {1} are {2}; they need at least {3}.").format(
				label("primary_color"), label("background_color"), "{ratio}", minimum
			),
		),
	]
	for field in BAR_FIELDS:
		# A blank bar takes Primary, and its text the ink bar_ink derives (061a).
		own = (doc.get(field) or "").strip()
		bar = own or _colour(doc, "primary_color")
		ink = contrast.bar_ink(bar, doc.get("text_color"))
		if not ink:
			continue
		reads = (field, "text_color") if own else (field, "primary_color", "text_color")
		pairs.append(
			(
				reads,
				ink,
				bar,
				_(
					"Text on the {0} reaches only {1}; it needs at least {2}. Choose a lighter or darker colour."
				).format(
					label(field) if own else _("{0} (blank, so Primary)").format(label(field)),
					"{ratio}",
					minimum,
				),
			)
		)

	out = []
	for fields, foreground, back, message in pairs:
		ratio = contrast.contrast_ratio(foreground, back)
		if ratio is not None and ratio < contrast.MIN_RATIO:
			out.append(
				{
					"fields": fields,
					"ratio": ratio,
					"message": message.replace("{ratio}", contrast.format_ratio(ratio)),
				}
			)
	return out


class WebsiteBranding(Document):
	def validate(self):
		self.check_colour_contrast()

	def check_colour_contrast(self):
		"""Refuse a colour changed in this save that leaves a pair below 4.5:1 (102 §8).

		Only a changed colour is refused: a school whose saved colours already fail can
		still save its other fields (the 102 patch lists those colours for them)."""
		before = self.get_doc_before_save()
		changed = {
			field
			for field in ("text_color", "background_color", "primary_color", *BAR_FIELDS)
			if (self.get(field) or "").strip().lower()
			!= ((before.get(field) if before else "") or "").strip().lower()
		}
		if not changed:
			return
		problems = [p["message"] for p in failing_pairs(self) if changed & set(p["fields"])]
		if problems:
			frappe.throw("<br>".join(problems), title=_("Text would be hard to read"))

	def on_update(self):
		# The brand colours/fonts are baked into the website <head> by
		# update_website_context (read via get_cached_doc). Saving the singleton
		# invalidates the doc cache, but cached rendered pages could still serve
		# the old :root block — clear the website cache so a reload reflects the
		# new scheme immediately (ADR 061).
		clear_website_cache()


@frappe.whitelist()
def public_website_enabled():
	"""Form helper: the hero and display options only serve the seminary's
	public pages, so the form hides them while those pages are off (093)."""
	from seminary.seminary import public_website

	return public_website.enabled()
