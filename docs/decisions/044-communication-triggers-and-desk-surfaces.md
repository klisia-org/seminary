# 044 — Declarative communication triggers & desk conversation surfaces

**Date:** 2026-06-10
**Status:** Accepted

## Context

Six call sites hand-rolled `frappe.sendmail` (waitlist promotion/closure, CEI
payment threshold, late-grade nags, term-pipeline warning, recommendation
requests) — each re-implementing recipient lookup and copy, none consent-aware
or rate-limited, none on a Person's timeline. Most future notifications are the
same shape: *when document X reaches state Y, tell Z*. Frappe's Notification
doctype does this but bypasses our ledger, consent, channels, and Person spine.
Staff also had no per-person conversation view and no way to start a message
from the desk.

## Decision

**Communication Trigger** — write the plumbing once, configure the rest:
*what* (watched doctype + AND-ed condition rows `field {operator} {value}`,
covering status/workflow_state/anything), *who* (Role / User / Document Field —
a field resolving to a Person directly, via a person-bearing doctype, via User,
or a plain email), *with what* (a Communication Template, per recipient-row
channel). Sends go through `comms.send()`, so consent, routing, throttling,
and the ledger apply for free. **Save triggers are edge-triggered**: they fire
on the false→true transition (compared against `get_doc_before_save`), never
while conditions merely stay true; `once_per_document` (default on) adds an
idempotency key capping at one send per document per recipient ever. Wired via
wildcard `doc_events` with a cached watched-doctype set so unwatched saves are
a no-op. Role/User recipients get `ensure_person()` — staff acquire Persons
and timelines by receiving mail (the ADR 042 staff seam).

**The six call sites migrated** onto seeded templates (create-only-if-missing;
bodies deliberately not gettext-wrapped — per-language copy is Template
Version rows, not .po files). They stay code-driven because their conditions
are computed (thresholds, day counts), but all delivery is ledger-only:
`frappe.sendmail` no longer appears outside the Email adapter. New helper
`send_to_role()` replaces every registrar-email loop; late-grade nags send
registrars their own copy instead of a CC. The term-pipeline warning dedupes
per (count, registrar) instead of nagging daily.

**Desk surfaces:** Person gains a *Conversation* tab (timeline of its
Communication Logs: direction, channel, status pill, reference) with
*Compose → Email / SMS / In-App* buttons — template or free-form — through
`compose_communication`, which can deliver immediately (`deliver_now`,
bypassing the hourly budget: a deliberate human action, not a bulk drain).
The Communication Log list view with status indicators is the desk inbox v1;
a richer page can come with the portal inbox (ADR 043 stage two).

## Consequences

Easier: "scholarship approved → tell the student" is desk configuration, not
code; every system message lands on timelines; staff engage from the Person
form. Harder: wildcard hooks run on every save — the doctype-set cache must
stay correct (controller clears it); template edits change live system mail.
Open: Days-Before/After scheduled triggers; condition support for child-table
fields; a dedicated inbox page.
