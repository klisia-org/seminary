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

import json
import re

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


#: A `<` that actually opens a tag, a comment or a processing instruction. A bare
#: `<` or `>` in prose is not markup: "fixed deposits >3 months" and "a < b" were
#: being escaped to `&gt;3` and `a &lt; b`, and because the escape is itself
#: markup-free the damage compounded on every later save (p008 F6 dry run).
_TAGGISH = re.compile(r"<[A-Za-z/!?]")


def has_markup(value) -> bool:
    return isinstance(value, str) and bool(_TAGGISH.search(value))


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


#: Fieldtypes that may carry author-written markup. `Code` is deliberately out:
#: that is how `Communication Channel.svg_icon` stays hand-written SVG, and F1's
#: `svg` render profile closes the XSS at the sink instead.
RICH_FIELDTYPES = ("Text Editor", "HTML Editor", "Long Text", "Small Text", "Text")

#: Fields whose whole purpose is raw HTML. Sanitising these would break the
#: feature, so they are named here rather than silently mangled. Anything added
#: must be staff-only to write AND never rendered into another user's session.
RAW_HTML_FIELDS = {
    ("Letter Head", "content"),
    ("Letter Head", "footer"),
    ("Print Format", "html"),
    ("Web Page", "main_section"),
    ("Web Template", "template"),
    # EditorJS JSON, cleaned block by block in `editorjs_safety` (p008 F4);
    # running a tag sanitiser over the JSON string would corrupt it.
    ("Course Lesson", "content"),
    ("Course Lesson", "instructor_content"),
}


def _is_json_payload(value) -> bool:
    """True for a Text field holding JSON rather than prose.

    Frappe stores structured data in Text fields all over the place --
    `Workspace.content` and `Course Lesson.content` are both EditorJS block
    JSON -- and running a tag sanitiser over it corrupts the document: the dry
    run turned `class=\\"h4\\"` into `class="\\&quot;h4\\&quot;"` on twenty Desk
    workspaces. Detecting the shape beats naming every such field, because the
    next one will not be in any list we write today.
    """
    stripped = value.lstrip()
    if not stripped[:1] in ("{", "["):
        return False
    try:
        json.loads(value)
    except (ValueError, TypeError):
        return False
    return True


def sanitize_rich_text(doc, method=None):
    """Clean every rich-text field on every doctype (p008 F6, p005 A05-1b).

    Frappe's own save-time sanitiser is bypassed for most content:
    `BaseDocument._sanitize_content` calls `sanitize_html` without
    `always_sanitize`, and `html_utils.sanitize_html` returns the input
    **unchanged** when BeautifulSoup finds no tag -- which is the case for any
    value whose markup the parser does not recognise as an element. p006 F13
    closed seven named low-privilege fields; everything staff-authored still
    rode the bypassed path, including `Program.program_description`, which
    renders on the public website.

    Hung off the wildcard `before_validate` rather than per-controller, the
    pattern `person_fields.capture_snapshots` already uses: a new doctype is
    covered without anyone remembering to opt in, and it is a cheap loop over
    the meta for everything else.

    Repairs, never rejects -- the p008 rule throughout. A document written in
    2024 must still save.
    """
    if getattr(doc, "flags", None) and doc.flags.get("ignore_content_safety"):
        return
    doctype = doc.doctype
    for df in doc.meta.fields:
        if df.fieldtype not in RICH_FIELDTYPES:
            continue
        if df.get("ignore_xss_filter"):
            continue
        if (doctype, df.fieldname) in RAW_HTML_FIELDS:
            continue
        value = doc.get(df.fieldname)
        if not has_markup(value) or _is_json_payload(value):
            continue
        cleaned = clean_rich(value)
        if cleaned != value:
            doc.set(df.fieldname, cleaned)
