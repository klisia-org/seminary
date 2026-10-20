# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Language matching for per-language rows (aretenic decision 071)."""

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
