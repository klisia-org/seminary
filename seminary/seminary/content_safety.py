# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""The server-side HTML policy (privatedocs p008 F4, F6).

MIRRORED by frontend/src/utils/htmlPolicy.js -- keep the two in step. The server
cleans what is stored; the client cleans what is rendered.

Frappe's ``sanitize_html`` is not enough on its own, for three reasons recorded
in p005 A05-1 and p005a A05-6:

* it returns its input unchanged when BeautifulSoup finds no tag in it, and
  ``<!--><img src=x onerror=...>-->`` parses as one comment -- the pre-parse
  bypass -- unless ``always_sanitize=True`` is passed, which the framework's own
  save-time call does not do;
* it skips anything that parses as JSON, which is every EditorJS lesson;
* even when it runs, its nh3 allow-list keeps ``<form>``, ``<input>`` and
  ``<button>`` and ~726 CSS properties including ``position`` and ``z-index``:
  enough to lay a fake sign-in form over the whole page with no script at all.

So :func:`clean_rich` calls nh3 directly with Frappe's own tag and attribute
lists -- nothing an editor produces is lost: tables, images, links, lists, RTL
and the rest of the style vocabulary all survive -- minus the two short
deny-lists below.
"""

import nh3
from bleach_allowlist import bleach_allowlist

import frappe
from frappe.utils.html_utils import (
    acceptable_attributes,
    acceptable_elements,
    mathml_elements,
    svg_attributes,
    svg_elements,
)

# No editor produces these; all of them survive Frappe's allow-list.
FORBIDDEN_TAGS = {
    "form",
    "input",
    "button",
    "textarea",
    "select",
    "option",
    "style",
    "base",
    "meta",
    "link",
}

# A DENY-list on purpose: authored content relies on the style vocabulary (table
# widths, floats, alignment, direction). These are what an overlay needs.
LAYOUT_ESCAPE = {
    "position",
    "z-index",
    "top",
    "right",
    "bottom",
    "left",
    "opacity",
    "transform",
    "pointer-events",
    "mix-blend-mode",
    "clip-path",
    "content",
    "behavior",
    "-moz-binding",
}

SAFE_STYLES = {
    p
    for p in bleach_allowlist.all_styles
    if p not in LAYOUT_ESCAPE and not p.startswith("inset")
}

_RICH_TAGS = (
    set(acceptable_elements) | set(svg_elements) | set(mathml_elements)
) - FORBIDDEN_TAGS
_RICH_ATTRIBUTES = {"*": set(acceptable_attributes), "svg": set(svg_attributes)}
_URL_SCHEMES = set(nh3.ALLOWED_URL_SCHEMES) | {"cid"}

# A highlighted code block: highlight.js spans and line structure, nothing else.
_CODE_TAGS = {"span", "br", "div"}
_CODE_ATTRIBUTES = {"span": {"class"}, "div": {"class"}}


def has_markup(value) -> bool:
    return isinstance(value, str) and ("<" in value or ">" in value)


def clean_rich(value):
    """Clean rich text. Non-strings and strings with no markup are returned as
    they are, so plain values (names, numbers, docnames) are never rewritten."""
    if not has_markup(value):
        return value
    return nh3.clean(
        value,
        tags=_RICH_TAGS,
        attributes=_RICH_ATTRIBUTES,
        # data-* stays, as in Frappe: the text editor marks checklists and
        # mentions with it, and the attributes are inert.
        generic_attribute_prefixes={"data-"},
        strip_comments=True,
        filter_style_properties=SAFE_STYLES,
        url_schemes=_URL_SCHEMES,
    )


def clean_code(value):
    """Clean a stored code block (highlight.js markup; see frontend code.ts)."""
    if not has_markup(value):
        return value
    return nh3.clean(
        value,
        tags=_CODE_TAGS,
        attributes=_CODE_ATTRIBUTES,
        strip_comments=True,
        url_schemes=set(),
    )
