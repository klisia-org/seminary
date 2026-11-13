# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Language matching for per-language rows (aretenic decision 071), and language names.

Frappe names its Language rows in their own script (ಕನ್ನಡ), which an editor choosing a language
from a Link cannot read. Each migrate gives Frappe's rows their English ISO 639 name, but only
while a row still has Frappe's name, so a site's own edit stays. Pages for readers (the language
picker, a book's language) show the native name, which is derived, never stored.
"""

import csv
from functools import lru_cache

import frappe
from frappe.translate import get_parent_language


def language_candidates(lang: str | None) -> list[str]:
    """The language, then its parent: a `pt` row serves a `pt-BR` user.

    Communication Template versions and Bible API Language Defaults try these in order
    before their own default, so adding a language stays data entry.
    """
    if not lang:
        return []
    parent = get_parent_language(lang)
    return [lang, parent] if parent and parent != lang else [lang]


# Frappe's sr-CS is Serbian in Latin script ("Srpski"), on the retired code for Serbia and
# Montenegro.
ENGLISH = {"sr-CS": "Serbian (Latin)"}
# Frappe's eo is its in-context translation tool, not Esperanto.
FRAPPE_ONLY = {"eo"}


@lru_cache
def frappe_names():
    """Frappe's own languages and their names, from the file Frappe syncs them from."""
    path = frappe.get_app_path("frappe", "geo", "languages.csv")
    with open(path, encoding="utf-8") as f:
        return {row["language_code"]: row["language_name"] for row in csv.DictReader(f)}


def iso_language(code):
    """The ISO 639 language of a code such as `pt`, `pt-BR` or `grc`, or None."""
    import pycountry

    base = (code or "").replace("_", "-").split("-")[0].lower()
    if len(base) == 2:
        return pycountry.languages.get(alpha_2=base)
    if len(base) == 3:
        return pycountry.languages.get(alpha_3=base)
    return None


def english_name(code):
    """The language's English ISO name, with the region for a regional code: "Portuguese (Brazil)".
    None when ISO has no such language or the region is unknown."""
    if code in ENGLISH:
        return ENGLISH[code]
    lang = iso_language(code)
    if not lang:
        return None
    name = lang.name.removesuffix(" (macrolanguage)")
    region = code.replace("_", "-").partition("-")[2]
    if region:
        from babel import Locale

        place = Locale("en").territories.get(region.upper())
        if not place:
            return None
        name = f"{name} ({place})"
    return name


def native_name(code, stored=None):
    """What a reader sees: Frappe's name for one of its languages, else Babel's, else the stored
    name. Ancient languages have no Babel locale, so they keep the stored one."""
    if not code:
        return stored or ""
    if code in frappe_names():
        return frappe_names()[code]
    from babel import Locale, UnknownLocaleError

    try:
        name = Locale.parse(code.replace("_", "-"), sep="-").display_name
    except (ValueError, UnknownLocaleError):
        name = None
    if name:
        return name[:1].upper() + name[1:]
    return stored or frappe.db.get_value("Language", code, "language_name") or code


def native_choices(codes=None, enabled_only=False):
    """Languages as (code, native name), sorted by that name, for a reader's list."""
    filters = {"name": ["in", list(codes)]} if codes is not None else {}
    if enabled_only:
        filters["enabled"] = 1
    rows = frappe.get_all("Language", filters=filters, fields=["name", "language_name"])
    choices = [(r.name, native_name(r.name, r.language_name)) for r in rows]
    return sorted(choices, key=lambda c: c[1].casefold())


def rename_frappe_languages():
    """Give Frappe's own Language rows their English names, while they still have Frappe's.

    Frappe sets a Language's name only once, so it is written directly, and the caches the
    Language's own save would clear are cleared here.
    """
    renamed = False
    for code, frappe_name in frappe_names().items():
        if code in FRAPPE_ONLY:
            continue
        name = english_name(code)
        if not name or name == frappe_name:
            continue
        if frappe.db.get_value("Language", code, "language_name") != frappe_name:
            continue
        frappe.db.set_value(
            "Language", code, "language_name", name, update_modified=False
        )
        frappe.clear_document_cache("Language", code)
        renamed = True
    if renamed:
        frappe.cache.delete_value("languages_with_name")
        frappe.client_cache.delete_value("languages")
