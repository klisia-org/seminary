# 001 — Documentation Architecture

**Date:** 2026-04-06
**Status:** Accepted

## Context

SeminaryERP targets small, pastor-run seminaries with minimal technical staff. Documentation needs to serve contributors (architecture decisions), administrators (setup and workflows), and translators (multilingual communities) — each with different needs and maintenance cadences.

## Decision

Three-tier documentation strategy:

1. **Tier 1 — Architecture Decision Records (ADRs):** Hand-written at the moment of decision. Live in `docs/decisions/`, excluded from the public docs site. ~200 words each, Context/Decision/Consequences format.

2. **Tier 2 — Structural (system shape):** Folded into ADRs or inline Python docstrings. Auto-generated schema docs were considered and rejected — Frappe's doctype JSON is already readable. The value is in explaining *why* fields exist, cross-doctype relationships, and what is intentionally absent.

3. **Tier 3 — Operational (user workflows):** VitePress deployed via GitHub Actions to GitHub Pages. Crowdin manages translations from `docs/en/` source files. Core docs describe what SeminaryERP does out of the box; each seminary adds local context via a Seminary Help Entry doctype with rich-text notes surfaced inline on Frappe forms.

Single repo with `docs/` subfolder so code and doc changes land in the same PR.

## Consequences

- ADRs capture reasoning while fresh; no retroactive documentation debt.
- Crowdin + folder-based i18n means translators never touch git.
- Deferred user docs until features stabilize avoids maintaining stale content.
- Seminary Help Entry creates a clean separation: ESWA maintains the *what*, each seminary maintains the *how we do it here*.
- Screenshots require per-language maintenance — mitigated by English fallback and deferred localization of images.
