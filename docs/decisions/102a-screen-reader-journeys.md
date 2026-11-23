# 102a — Screen-reader journeys

**Date:** 2026-11-23
**Status:** Accepted 2026-11-23; implemented 2026-11-23
**Amends:** 102 §3 (what the automated check covers), §5 (what the manual rows rest on)
**Related:** 103 (keyboard course outline)

## Context

axe reads the page's structure. It can't tell what a screen reader says, or in what order, as
someone moves through a task. A probe with Guidepup's virtual screen reader on the portal heard
every sidebar icon read out as "graphics-document", which axe passes. The virtual reader only
simulates one. It hears changes to live regions already on the page, but not alerts added
later, such as toasts. Real screen readers need Windows or macOS.

## Decision

1. **Each app lists a few journeys** in `docs/accessibility/journeys.yaml`. A journey is a visit
   from the check's plan (a route and a role), a list of moves, and what must and must not be
   heard. Moves include next item, next landmark, focus, key press and click.
2. **The check runs each journey with the virtual screen reader** (`@guidepup/virtual-screen-reader`)
   in the same Chromium and with the same sign-ins as axe. A phrase that isn't heard fails the
   test, and so does one that must not be heard. Matching is on part of a phrase, never the
   whole log.
3. **Journeys stay few and cover tasks, not pages:** the portal shell (skip link, landmarks,
   names), a menu, a form's errors, and anything a past fix depends on.
4. **NVDA runs the same journeys on a Windows machine, on demand.** `scripts/screen-reader`
   has a script that drives NVDA through Guidepup on the URLs and sessions the bench exports.
   It records what NVDA said but asserts nothing, since NVDA words things differently. A person
   reads the record and uses it for the manual rows. The person then removes the sessions.
5. **Toasts and other added alerts are checked by NVDA only,** until the virtual reader hears
   them.

## Consequences

Each run adds a few seconds per journey. Spoken wording can change between versions of the
virtual reader, so journeys match short phrases. The NVDA run needs a person and a Windows
machine, and it fills manual rows rather than gating a commit.

## As built

- The first journeys found sidebar and empty-state icons read out as "graphics-document". They
  now have `aria-hidden`. The portal-shell journey must not hear any icon.
- `export_journeys` and `end_exported_sessions` in `accessibility.py` give the NVDA script its
  URLs and sessions. The script is `scripts/screen-reader/nvda.mjs` (Guidepup 0.40.0), and it
  hasn't been run on Windows yet.
- An app that plans its own visits passes `planner` on its `Target`, so its journeys use its
  plan.
