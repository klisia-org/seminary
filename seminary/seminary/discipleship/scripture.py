"""Scripture drill-down tree for a cohort's posts (ADR 064 extension).

Aggregates the verse-ordinal ranges on a cohort's *visible* posts into a
Book → Chapter → Verse tree with tallies. Book/chapter counts are distinct
posts (a post spanning several verses counts once); verse counts are per-verse
(a range contributes to each verse it covers) — whole-chapter tags are not
exploded to every verse.
"""

import frappe

from seminary.seminary.integrations.bible_books import (
    BOOK_NAMES,
    BOOK_ORDER,
    OSIS_BY_ORDER,
    decode_ordinal,
)

_MAX_VERSE = 176  # longest chapter (Ps 119) — bounds open-ended tails


def _visible_post_ids(cohort):
    # get_list applies the visibility permission clause for the caller.
    return frappe.get_list(
        "Cohort Post",
        filters={"cohort": cohort, "status": ["in", ["published", "pinned"]]},
        pluck="name",
    )


def _refs_for(cohort):
    ids = _visible_post_ids(cohort)
    if not ids:
        return []
    return frappe.get_all(
        "Cohort Post Scripture Ref",
        filters={"parent": ["in", ids]},
        fields=["parent", "verse_start_ord", "verse_end_ord"],
    )


@frappe.whitelist()
def scripture_books(cohort):
    books = {}
    for r in _refs_for(cohort):
        b1 = decode_ordinal(r.verse_start_ord)[0]
        b2 = decode_ordinal(r.verse_end_ord)[0]
        for bi in range(b1, b2 + 1):
            books.setdefault(bi, set()).add(r.parent)
    out = []
    for bi, posts in books.items():
        osis = OSIS_BY_ORDER.get(bi)
        if osis:
            out.append(
                {
                    "osis": osis,
                    "name": BOOK_NAMES.get(osis, osis),
                    "index": bi,
                    "count": len(posts),
                    "start_ord": bi * 1_000_000,
                    "end_ord": bi * 1_000_000 + 999_999,
                }
            )
    out.sort(key=lambda x: x["index"])
    return out


@frappe.whitelist()
def scripture_chapters(cohort, book):
    bi = BOOK_ORDER.get(book)
    if not bi:
        return []
    lo, hi = bi * 1_000_000, bi * 1_000_000 + 999_999
    chapters = {}
    for r in _refs_for(cohort):
        s, e = max(r.verse_start_ord, lo), min(r.verse_end_ord, hi)
        if s > e:
            continue
        for ch in range(decode_ordinal(s)[1], decode_ordinal(e)[1] + 1):
            chapters.setdefault(ch, set()).add(r.parent)
    out = [
        {
            "chapter": ch,
            "count": len(posts),
            "start_ord": bi * 1_000_000 + ch * 1_000,
            "end_ord": bi * 1_000_000 + ch * 1_000 + 999,
        }
        for ch, posts in chapters.items()
    ]
    out.sort(key=lambda x: x["chapter"])
    return out


@frappe.whitelist()
def scripture_verses(cohort, book, chapter):
    bi = BOOK_ORDER.get(book)
    if not bi:
        return []
    chapter = int(chapter)
    clo = bi * 1_000_000 + chapter * 1_000
    chi = clo + 999
    verses = {}
    for r in _refs_for(cohort):
        s, e = max(r.verse_start_ord, clo), min(r.verse_end_ord, chi)
        if s > e:
            continue
        v1, v2 = decode_ordinal(s)[2], decode_ordinal(e)[2]
        if v1 == 0:
            continue  # whole-chapter tag — counted at the chapter level only
        for v in range(v1, min(v2, _MAX_VERSE) + 1):
            verses.setdefault(v, set()).add(r.parent)
    out = [
        {"verse": v, "count": len(posts), "start_ord": clo + v, "end_ord": clo + v}
        for v, posts in verses.items()
    ]
    out.sort(key=lambda x: x["verse"])
    return out


@frappe.whitelist()
def posts_in_range(cohort, start_ord, end_ord):
    """Visible posts whose scripture overlaps the ordinal range [start, end]."""
    from seminary.seminary.discipleship.feed_api import _scoped_posts

    start_ord, end_ord = int(start_ord), int(end_ord)
    ids = _visible_post_ids(cohort)
    if not ids:
        return []
    rows = frappe.get_all(
        "Cohort Post Scripture Ref",
        filters={
            "parent": ["in", ids],
            "verse_start_ord": ["<=", end_ord],
            "verse_end_ord": [">=", start_ord],
        },
        pluck="parent",
    )
    return _scoped_posts(set(rows))
