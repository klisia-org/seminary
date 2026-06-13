# 048 — Donor ↔ Person soft cross-app link

**Date:** 2026-06-12
**Status:** Accepted

## Context

Donors live in **frappe_giving**, a separate donation-management app sharing
the bench (and the `portal-shell`) with Seminary but deliberately installable on
its own. ADR 042 envisioned donors as Persons directly, but where both apps run
the same human is often a `Donor` *and* a Person (alumnus, member). We want them
linked — without making frappe_giving depend on Seminary, and without breaking a
frappe_giving-only install. So a native `Person.donor` Link is out: it would
fail to migrate whenever `Donor` is absent.

## Decision

Keep the dependency one-directional and optional, owned entirely by Seminary.
The **canonical FK is `Donor.person`** — a Custom Field created programmatically
in `setup_donor_person_field()` (run from `after_migrate`) **only when the
`Donor` doctype exists**, re-checked every migrate so installing frappe_giving
later still wires it. A read-only `Person.donor` reverse mirror is kept in sync
by `seminary.seminary.integrations.giving` via `doc_events` on `"Donor"` — a
hook on a missing doctype never fires, so the code is inert without
frappe_giving and frappe_giving never imports Seminary. No fixtures (can't be
conditional; would clobber). Mirrors the Customer↔Person pattern (ADR 042).
Backfill patch links existing Donors by shared Customer, then User/email
(unambiguous matches only; never creates a Person), reporting the rest.

## Consequences

Easier: one human, one identity across both apps; Seminary Person views surface
the linked Donor; either app installs alone. Harder: the link is Seminary's
responsibility, so frappe_giving UI shows `Donor.person` only post-migrate. Open:
whether a future bridge app should own this if a third consumer appears.
