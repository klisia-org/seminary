"""Helpers for public website SEO meta tags (ADR 061).

Frappe's MetaTags component (frappe/website/website_components/metatags.py) reads
`context.metatags` and auto-expands the base keys (title, description, image)
into og:/twitter: tags, absolutising the image. So each public page only needs
to set those base keys via `page_metatags()`.
"""

import frappe
from frappe.utils import strip_html


def page_metatags(title, description=None, image=None):
    """Build the base metatags dict for a public page. Frappe expands it into
    Open Graph + Twitter card tags and makes the image absolute."""
    tags = {"title": title, "og:type": "website"}
    excerpt = clean_excerpt(description)
    if excerpt:
        tags["description"] = excerpt
    if image:
        tags["image"] = image
    return tags


def clean_excerpt(html, length=160):
    """Plain-text, length-capped excerpt from a (possibly rich-text) value, for
    meta descriptions. Returns None when there is no real text (e.g. an empty
    rich-text editor) so the tag is omitted."""
    if not html:
        return None
    text = " ".join(strip_html(html or "").split())
    if not text:
        return None
    if len(text) > length:
        text = text[:length].rsplit(" ", 1)[0].rstrip() + "…"
    return text
