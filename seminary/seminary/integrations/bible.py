# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

"""api.bible (https://scripture.api.bible) domain wrapper.

Reads credentials and per-language defaults from the `Bible API Settings` Single
DocType, resolves which Bible to query based on the caller's language, and
delegates the actual HTTP call to `integrations.client.get`.

The `lookup` whitelisted function is the single entry point for the Vue
frontend so the API key never leaves the server.
"""

import re

import frappe
from frappe import _

from seminary.seminary.integrations import client
from seminary.seminary.integrations.bible_books import BOOK_ALIASES, normalize


_REF_PATTERN = re.compile(r"^\s*(\S.*?)\s+(\d+)(?::(\d+)(?:-(\d+))?)?\s*$")


def parse_reference(ref: str) -> str:
    """Convert a human-typed Bible reference into api.bible's OSIS format.

    Examples:
        "Jn 3:16"      → "JHN.3.16"
        "John 3:16-17" → "JHN.3.16-JHN.3.17"
        "1 João 3:1"   → "1JN.3.1"
        "Sl 23"        → "PSA.23"  (whole-chapter ref)

    Out of scope for v1: cross-chapter ranges ("Jn 3:36-4:3") and
    multi-passage refs ("Jn 3:16; Rom 8:28") — both throw with a hint.
    """
    if not ref or not ref.strip():
        frappe.throw(_("Bible reference is empty."))
    raw = ref.strip()
    if ";" in raw or "," in raw:
        frappe.throw(
            _(
                "Multi-passage references are not supported. Split '{0}' into separate questions or rows."
            ).format(raw)
        )
    m = _REF_PATTERN.match(raw)
    if not m:
        frappe.throw(
            _(
                "Could not parse '{0}'. Expected formats: 'Jn 3:16', 'Jn 3:16-17', or 'Sl 23'."
            ).format(raw)
        )
    book_raw, chapter, verse_start, verse_end = m.groups()
    osis = BOOK_ALIASES.get(normalize(book_raw))
    if not osis:
        frappe.throw(
            _(
                "Unknown book '{0}'. Try a standard abbreviation like Jn, Sl, Rm, Ap (EN or PT)."
            ).format(book_raw)
        )
    if verse_start is None:
        return f"{osis}.{chapter}"
    if verse_end is None:
        return f"{osis}.{chapter}.{verse_start}"
    return f"{osis}.{chapter}.{verse_start}-{osis}.{chapter}.{verse_end}"


def fetch_text_for_passage(ref: str, bible_id: str | None = None) -> dict:
    """Parse a human-typed ref, fetch the passage, return clean plain text.

    Returns {"resolved_ref": "JHN.3.16", "reference": "John 3:16", "text": "..."}.
    Asks api.bible for plain-text output (no HTML, no verse numbers, no titles)
    so the result can be tokenized and rendered directly.
    """
    settings = _get_settings()
    resolved_id = parse_reference(ref)
    actual_bible_id = _resolve_bible_id(settings, bible_id)
    payload = client.get(
        base_url=settings.base_url,
        path=f"bibles/{actual_bible_id}/passages/{resolved_id}",
        auth_header="api-key",
        auth_value=_get_api_key(settings),
        params={
            "content-type": "text",
            "include-notes": "false",
            "include-titles": "false",
            "include-chapter-numbers": "false",
            "include-verse-numbers": "false",
            "include-verse-spans": "false",
        },
    )
    data = (payload or {}).get("data") or {}
    text = (data.get("content") or "").strip()
    if not text:
        frappe.throw(_("api.bible returned no text for {0}.").format(ref))
    return {
        "resolved_ref": resolved_id,
        "reference": data.get("reference") or ref,
        "text": text,
    }


def _get_settings():
    settings = frappe.get_single("Bible API Settings")
    if not settings.enabled:
        frappe.throw(_("Bible API integration is disabled in Bible API Settings."))
    if not settings.base_url:
        frappe.throw(_("Bible API Settings is missing a Base URL."))
    return settings


def _get_api_key(settings) -> str:
    key = settings.get_password("api_key", raise_exception=False)
    if not key:
        frappe.throw(_("Bible API Settings is missing an API Key."))
    return key


def _resolve_bible_id(settings, explicit: str | None) -> str:
    if explicit:
        return explicit
    user_lang = frappe.local.lang
    if user_lang:
        for row in settings.language_defaults or []:
            if row.language == user_lang:
                return row.bible_id
    if settings.default_bible_id:
        return settings.default_bible_id
    frappe.throw(
        _(
            "No Bible configured for language {0}. Set a Default Bible ID or add a Language Default in Bible API Settings."
        ).format(user_lang or _("unknown"))
    )


def lookup_passage(passage_ref: str, bible_id: str | None = None) -> dict:
    """Fetch a passage (e.g. 'JHN.3.16' or 'JHN.3.16-JHN.3.17')."""
    settings = _get_settings()
    resolved = _resolve_bible_id(settings, bible_id)
    return client.get(
        base_url=settings.base_url,
        path=f"bibles/{resolved}/passages/{passage_ref}",
        auth_header="api-key",
        auth_value=_get_api_key(settings),
    )


def search(query: str, bible_id: str | None = None, limit: int = 10) -> dict:
    """Full-text search within a Bible."""
    settings = _get_settings()
    resolved = _resolve_bible_id(settings, bible_id)
    return client.get(
        base_url=settings.base_url,
        path=f"bibles/{resolved}/search",
        auth_header="api-key",
        auth_value=_get_api_key(settings),
        params={"query": query, "limit": limit},
    )


@frappe.whitelist()
def get_bible_name(bible_id: str) -> str:
    """Fetch the human-readable name for a Bible ID from api.bible.

    Used when configuring per-language defaults, so it skips the `enabled`
    gate that `_get_settings` enforces (admins may need to look up names
    while the integration is still disabled).
    """
    frappe.only_for(["System Manager", "Seminary Manager"])
    settings = frappe.get_single("Bible API Settings")
    if not settings.base_url:
        frappe.throw(_("Bible API Settings is missing a Base URL."))
    payload = client.get(
        base_url=settings.base_url,
        path=f"bibles/{bible_id}",
        auth_header="api-key",
        auth_value=_get_api_key(settings),
    )
    data = (payload or {}).get("data") or {}
    name = data.get("name") or data.get("nameLocal")
    if not name:
        frappe.throw(_("api.bible returned no name for Bible ID {0}.").format(bible_id))
    return name


@frappe.whitelist()
def list_bibles(language: str | None = None) -> dict:
    """Discover available Bibles, optionally filtered by language code (e.g. 'eng', 'por').

    Admin-only: used by the Bible API Settings form to populate the default and
    per-language Bible IDs. Not for end-user/frontend use.
    """
    frappe.only_for(["System Manager", "Seminary Manager"])
    settings = _get_settings()
    params = {"language": language} if language else None
    return client.get(
        base_url=settings.base_url,
        path="bibles",
        auth_header="api-key",
        auth_value=_get_api_key(settings),
        params=params,
    )


@frappe.whitelist()
def test_connection() -> dict:
    """Verify the configured api.bible credentials work. Used by the settings form."""
    frappe.only_for(["System Manager", "Seminary Manager"])
    try:
        result = list_bibles()
        count = len(result.get("data", [])) if isinstance(result, dict) else 0
        return {
            "ok": True,
            "message": _("Connected successfully. {0} Bibles available.").format(count),
        }
    except frappe.PermissionError:
        raise
    except Exception as e:
        return {"ok": False, "message": str(e) or _("Unknown error")}


@frappe.whitelist()
def lookup(passage_ref: str, bible_id: str | None = None) -> dict:
    return lookup_passage(passage_ref, bible_id)
