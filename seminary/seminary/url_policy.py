# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""URL scheme allow-list (privatedocs p008 F7). Mirrored by
frontend/src/utils/urlPolicy.js.

``frappe.utils.validate_url`` accepts ``javascript:`` unless it is told which
schemes are valid, and no caller in this app told it. This module is the one
place that does.
"""

from urllib.parse import urlparse

import frappe
from frappe import _

WEB_SCHEMES = ("http", "https")
LINK_SCHEMES = ("http", "https", "mailto", "tel")


def _strip_controls(value) -> str:
    # Browsers drop tabs, newlines and other control characters before resolving
    # a scheme, so "java<newline>script:" IS javascript:. Strip them first.
    return "".join(c for c in str(value or "") if ord(c) > 31 and ord(c) != 127).strip()


def is_safe_url(value, *, schemes=LINK_SCHEMES, allow_relative=True) -> bool:
    """True for an empty value, a same-site relative path (when allowed), or an
    absolute URL whose scheme is in ``schemes``. Protocol-relative ``//host`` is
    refused: it is an absolute URL to somebody else's server."""
    v = _strip_controls(value)
    if not v:
        return True
    if v.startswith(("//", "\\")):
        return False
    scheme = urlparse(v).scheme.lower()
    if not scheme:
        return bool(allow_relative)
    return scheme in schemes


def require_safe_url(value, label, **kw):
    if not is_safe_url(value, **kw):
        frappe.throw(
            _("{0} must be a web address (https://…).").format(label),
            frappe.ValidationError,
        )
    return value


def safe_embed_url(value) -> str:
    """An absolute http(s) URL on ANOTHER host, or ''. For iframes: an embed must
    never point back at a file uploaded to this site (p005 A02-4)."""
    v = _strip_controls(value)
    if not is_safe_url(v, schemes=WEB_SCHEMES, allow_relative=False):
        return ""
    host = (urlparse(v).hostname or "").lower()
    if not host:
        return ""
    site = (urlparse(frappe.utils.get_url()).hostname or "").lower()
    request_host = ""
    if getattr(frappe.local, "request", None):
        request_host = (frappe.local.request.host or "").split(":")[0].lower()
    if host in {site, request_host} - {""}:
        return ""
    return v


#: URLs not typed as `Data(options="URL")`, so `_validate_data_fields` never sees
#: them. Frappe walks the typed ones itself and hands them to the scheme-blind
#: `validate_url`; these need naming.
URL_FIELDS = {
    ("Course Schedule", "web_meeting"),
    ("Course Schedule Meeting", "cs_web_meeting"),
    ("Website Branding", "hero_cta_link"),
    ("Website Social Link", "url"),
    ("Seminary Help Entry", "mkdocs_url"),
    ("Channel Provider Account", "public_url"),
    ("Communication Log", "media_url"),
}


def validate_urls(doc, method=None):
    """Refuse a dangerous scheme in any URL field (p008 F7, p005 A05-2 rows 9-10).

    Two passes: every `Data` field with `options: "URL"` -- the exact set
    `BaseDocument._validate_data_fields` already walks and hands to the
    scheme-blind `frappe.utils.validate_url`, so new fields are covered without
    being listed -- plus the named `URL_FIELDS` for URLs stored in plain fields.

    **Only changed values on an existing document.** A `mailto:` or `//host`
    value stored before this existed must not make an unrelated edit to the same
    record impossible; it is refused when someone next touches *that* field.
    On insert everything is checked.
    """
    is_new = doc.is_new()
    for df in doc.meta.fields:
        typed = df.fieldtype == "Data" and (df.options or "").upper() == "URL"
        if not typed and (doc.doctype, df.fieldname) not in URL_FIELDS:
            continue
        value = doc.get(df.fieldname)
        if not value:
            continue
        if not is_new and not doc.has_value_changed(df.fieldname):
            continue
        require_safe_url(value, _(df.label or df.fieldname))
