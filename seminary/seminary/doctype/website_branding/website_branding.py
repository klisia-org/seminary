# Copyright (c) 2026, Seminary and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.website.utils import clear_website_cache


class WebsiteBranding(Document):
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
