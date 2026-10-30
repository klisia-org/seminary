# 061b — Website language picker

**Date:** 2026-10-30
**Status:** Accepted 2026-10-30; implemented 2026-10-30
**Amends:** [061](061-public-website-platform-and-branding.md) (navbar)

## Context

Public pages are translated, but visitors cannot choose a language: Frappe's picker lives in its
own navbar, which 061 replaced. It would also offer every enabled Language, while a school's pages
are translated into only a few, and narrowing it means disabling Languages for users too.

## Decision

1. **Website Branding lists the Website Languages** (a table of Language links), in the order
   shown. Fewer than two, or a disabled Language, leaves nothing to choose, so the picker hides.
2. **The navbar shows a picker for guests,** before Login. Choosing sets Frappe's
   `preferred_language` cookie and reloads. Logged-in users read pages in their profile's language,
   so the picker hides for them, in the browser, because cached pages are shared.
3. A regional Language (`pt-BR`) uses its parent's translations (`pt`) where its own are missing.

## Consequences

Each school offers exactly the languages its pages are translated into. Frappe already caches
pages per language, so nothing else changes.
