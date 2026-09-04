# 042 — Person identity spine

**Date:** 2026-06-10
**Status:** Accepted — **superseded in part by [ADR 068](068-person-first-identity-and-shared-attribute-registry.md) (2026-09-04)**

The core decision below stands: Person is a spine beside the role doctypes, not a replacement, with one
mutation point and an opaque id. Three clauses do not, and 068 replaces them:

- **The mirror mechanism.** "Role contact fields flip read-only once the link exists
  (`read_only_depends_on: doc.person`, which leaves them typeable on the creation form where
  `fetch_from` would not)" — Person-first removes that reason, because nothing is typed on a role
  creation form when the Person already exists. Those fields are `fetch_from person.*` mirrors now, and
  the ones that are not read-heavy were deleted rather than mirrored.
- **"Student/Applicant/Instructor/Alumni keep their naming series ... untouched."** Three of the four
  were keyed on mutable personal data — `format:{instructor_name}`, `field:email`,
  `format:{academic_term}-{first_name}-{###}` — which is exactly what this ADR says identity must not
  be. They are opaque now (`INST-`, `ALUM-`, `APP-`); Student was already `format:{YY}-{#####}`.
- **"Two onboarding heads."** There is one rule — Person first — and one named exception, Student
  Applicant, because a guest has no User. The asymmetry was the point that got lost.

Also superseded: "hydrated server-side in `validate`". `_validate_links()` runs *before* `validate()`,
so a `person` resolved there missed the fetch until the second save; `person` is now reqd and set
before insert.

## Context

Four person-shaped doctypes (Student Applicant, Student, Instructor, Alumni
Profile) each carry their own name/email/phone fields with no cross-type
identity: the same human as Student + Instructor is two unrelated records,
emails are unique only per-doctype, and stakeholders without an operational
doctype (donors, guardians, church contacts) only exist as Customers. A
first-class communication system (ADR 043) needs **one** routing target that
owns reachability, consent, and language — Frappe's Contact is email-centric
and Frappe CRM is sales-funnel oriented, so neither fits.

## Decision

A **Person** doctype as an identity-and-reachability spine — **not** a
replacement for the role doctypes. Student/Applicant/Instructor/Alumni keep
their naming series, workflows, permissions, and Customer/Supplier links
untouched; each gains a `person` Link maintained by **one mutation point**,
`ensure_person()` in `seminary/seminary/person.py`. Person is the **system of
record** for identity and contact data — the app is pre-production, so there is
no mirror/sync transition: role contact fields flip read-only once the link
exists (`read_only_depends_on: doc.person`, which leaves them typeable on the
creation form where `fetch_from` would not); edits happen on Person. The
columns stay physically on the role tables so every existing query keeps
working, hydrated server-side in `validate` and pushed by Person's `on_update`
propagation (`db.set_value`, hook-free) whenever the spine changes.

**Creation order is the only seam — two onboarding heads.** Public intake: the
webform still captures contact fields on Student Applicant (a guest cannot
write Person directly); `after_insert` promotes them through `ensure_person()`,
seeding the primary email/phone Channel Address rows — no User exists yet.
While the applicant is the only role attached (no User yet), applicant-form
edits **re-promote** — staff fix intake typos where they see them. Admission
then attaches Student, User, and Customer to that **same** Person
(`person.user` / `person.customer` filled as each appears) and the applicant's
contact fields flip to read-only mirrors like every other role. Staff intake runs
the other way: the User exists first; `ensure_person()` lifts identity from
User when the Instructor (or other staff role) record is created, and links it.

**Identity is opaque; email is data.** Person autonames `PERS-.#####` and is
never renamed — every foreign key points at that id. An email is just a Person
Channel Address row: normalized email is only the *match heuristic*
`ensure_person()` uses to find an existing Person, never the key. This
deliberately breaks with Frappe's User-keyed-by-email awkwardness — when an
email changes, one child row changes; the `user` link is the single field a
User rename touches, and Frappe's rename machinery maintains it. Multiple
addresses per channel are allowed (an official and a promotional email…), each
optionally scoped to a message category; routing (ADR 043) prefers the
category-scoped address and falls back to the primary.

Person owns what roles only mirrored: canonical name, image, **language**
(communication language, distinct from `User.language`), country/region (drives
provider routing, ADR 043), optional `user`/`customer` links, and two child
tables — **Person Channel Address** (channel, value, verified, status:
Active/Bounced/Invalid) and **Person Consent** (channel × category, status
Opted In/Out/Unset, source, timestamp). Donors/guardians become Persons
directly, with relationship rows instead of forced Customers.

Backfill patch creates Persons from existing roles, matching on lowercased
email; collisions **hard-fail the patch for manual resolution** (pre-production
dataset, so this is cheap), never auto-merge.

## Consequences

Easier: one consent/language/contact record per human; a unified interaction
timeline (ADR 043 logs hang off Person); Student-who-teaches is one identity.
Harder: contact edits live on Person only — the Student Applicant intake fields
are capture-then-promote, **not** a second home for the data, and any new
onboarding path must call `ensure_person()` at its head. Open: merge tooling
for duplicates; folding Instructor's `messaging_apps` child into Person Channel
Address.
