# 022 — Bible Reference Parser: Hand-coded EN+PT for Now, OpenBibleInfo Library Reserved

**Date:** 2026-05-23
**Status:** Accepted

## Context

The Scripture Matching and Scripture Memorization question types (ADR-pending)
take prof-typed references ("Jn 3:16", "Sl 23", "1 João 3:1") and need to
hand api.bible an OSIS-shaped passage ID like `JHN.3.16`. Two paths:

- Hand-code a Python map for the 66 Protestant-canon books with EN + PT
  aliases, plus a tiny regex parser.
- Adopt [openbibleinfo/Bible-Passage-Reference-Parser](https://github.com/openbibleinfo/Bible-Passage-Reference-Parser)
  — 46+ languages, cross-chapter ranges (`Jn 3:36-4:3`), multi-passage
  parsing (`Jn 3:16; Rom 8:28`), MIT, actively maintained (v3.2.0, Jan 2026).

The library is JavaScript-only (no PyPI). Adopting it server-side means a
Node subprocess; the alternative is moving parse-on-save to the frontend.
Either is significant plumbing for the ~5% of cases our hand map misses.

## Decision

Ship a hand-coded `seminary/seminary/integrations/bible_books.py` (66 books
× ~5 EN+PT aliases each) plus `parse_reference()` in `bible.py`. Covers
single verses and single-chapter ranges; throws on cross-chapter and
multi-passage with a clear hint. Sufficient for Seminary's bilingual EN+PT
scope; runs in-process at question save with no extra runtime.

Defer Bible-Passage-Reference-Parser to a documented future path. Triggers
to revisit: profs ask for cross-chapter ranges, multi-passage in one
question, or Crowdin gains a third UI language (ES/FR/DE/etc.).

When that trigger lands, the cleanest migration is **frontend-side
parsing**: import the library in `Modals/Question.vue` for live preview as
the prof types, ship the resolved OSIS string to the backend. The backend
then drops `parse_reference` and keeps only a static USFM map
(OSIS `John` → api.bible `JHN`, ~66 entries). No Node sidecar needed.

## Consequences

- Zero new dependencies; parser tests are pure-Python and fast.
- The hand-coded alias table needs a new entry only when a prof reports a
  miss — low rate given the canon is finite.
- **Open: trigger to migrate.** When the migration triggers fire, the
  Python parser plus its alias map gets deleted entirely; the USFM
  conversion map (smaller, deterministic) is the only surviving piece.
- **Open: client/server trust boundary on parsed refs.** If/when parsing
  moves to the frontend, the backend should still validate the OSIS shape
  (a regex check, not full parsing) before calling api.bible — a malicious
  client must not be able to inject arbitrary path segments.
