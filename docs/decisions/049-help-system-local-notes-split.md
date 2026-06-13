# 049 — Help system: native doc link + local-notes split

**Date:** 2026-06-12
**Status:** Accepted (supersedes part of ADR 001)

## Context

ADR 001 gave each seminary a **Seminary Help Entry** doctype: a rich-text
"how we do it here" note plus a `mkdocs_url` (required) link to the operational
docs, surfaced inline on Frappe forms. In practice the implementation only ever
rendered the external link as a "Help Docs" button — `local_notes` was stored
but shown nowhere — and you had to hand-create an entry just to get a docs link
on a doctype. Once Tier 3 moved to VitePress (`docs.seminaryerp.org`), the
external link is a per-doctype constant that belongs *on the doctype*, not in a
side table. The local notes — the single most reassuring thing for under-staffed
seminaries ("will my people learn this?") — were the part going unseen.

## Decision

Split the two concerns by source of truth:

1. **External documentation → the doctype itself.** Frappe's core DocType
   already has a built-in `documentation` ("Documentation Link") property, sent
   to the client as `frm.meta.documentation`, but Frappe renders it only in the
   list-view empty-state, never in form view. A shared, generic Desk fix
   (`seminary_doc_link.js`, registered in `docs/frappe-workarounds.md` #5) wraps
   `Form.prototype.refresh` and adds a header Help icon opening that URL — no
   backend call, no Seminary Help Entry needed. Setting a doctype's Documentation
   Link is now all it takes.

2. **Local notes → Seminary Help Entry, shown inline.** The entry is reframed
   around `local_notes`, rendered as a collapsible dashboard section by
   `seminary_help.js` (cached per-doctype to avoid a call on every refresh).
   `mkdocs_url` becomes optional (still used by frontend Vue pages, which have no
   doctype meta) and `autoname()` is target-first so it no longer depends on the
   URL.

## Consequences

Easier: documentation links cost one property on the doctype; the local "how we
do it here" guidance is finally visible where staff work. Two clean sources of
truth instead of one overloaded table. On the Vue frontend a shared `HelpWidget`
(used by both Desktop and Mobile layouts) surfaces `local_notes` and the doc link
in a popover, keyed by the route name via `useHelp`. Harder/Open: frontend pages
must be matched by route name (the `frontend_page` field; `.vue` suffixes are
normalised away) — there is no compile-time check that a help entry's
`frontend_page` still names a real route.
