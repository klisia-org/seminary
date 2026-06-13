"""Text normalization, tokenization and word-shingle helpers for the internal
plagiarism engine.

Deliberately pure-stdlib (no frappe, no numpy) so the similarity engine in
internal.py can be unit-tested standalone — the only heavyweight work (parsing
PDF/DOCX) lives in extract.py, which is the part that touches frappe.
"""

import html
import re
import unicodedata

# A small, generic English stoplist. Kept for TF-IDF (so shared function words
# don't inflate cosine) but NOT for shingles — function words are part of the
# copied phrasing a shingle is meant to catch.
STOPWORDS = frozenset(
    """
    a an and are as at be by for from has have he in is it its of on that the
    to was were will with this these those or nor not but if then else when
    which who whom whose what where why how all any both each few more most
    other some such no only own same so than too very can just into about
    """.split()
)

_TAG_RE = re.compile(r"<[^>]+>")
_NON_WORD_RE = re.compile(r"[^a-z0-9]+")


def strip_html(text: str) -> str:
    """Best-effort HTML → plain text: drop tags, unescape entities. Block-level
    tags become spaces so adjacent words don't fuse (``</p><p>`` → a gap)."""
    if not text:
        return ""
    text = re.sub(r"<(br|/p|/div|/li|/h[1-6])[^>]*>", " ", text, flags=re.I)
    text = _TAG_RE.sub(" ", text)
    return html.unescape(text)


def normalize(text: str) -> str:
    """Lowercase + NFKC + punctuation→space + whitespace collapse. The single
    canonical form every comparison runs on, so smart quotes / casing / spacing
    differences never hide a verbatim copy."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).lower()
    text = _NON_WORD_RE.sub(" ", text)
    return text.strip()


def tokenize(text: str, *, is_html: bool = False) -> list:
    """Ordered word tokens. Order is retained because difflib needs it for
    contiguous-passage detection."""
    if is_html:
        text = strip_html(text)
    norm = normalize(text)
    return norm.split() if norm else []


def shingles(tokens: list, n: int) -> set:
    """Set of word n-grams (as joined strings). The near-duplicate primitive:
    a shared 5-gram is a strong copied-phrasing signal, robust to reordering of
    distant paragraphs. Falls back to single tokens when the text is shorter
    than one shingle."""
    if n < 1:
        n = 1
    if len(tokens) < n:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}
