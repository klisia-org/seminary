# 031 — Withdrawal vs disciplinary reason taxonomies

**Date:** 2026-06-01
**Status:** Accepted

## Context

Two reason vocabularies now exist: `Withdrawal Reasons` (the student-facing exit
taxonomy used by Course Withdrawal Request) and `Disciplinary Reason` (the
misconduct taxonomy for incidents). They risk being conflated, and the exit
taxonomy lacked a way to signal *why* a student left (transfer? to where?).

## Decision

Keep the two taxonomies **separate**; they relate only through the status spine.

- `Withdrawal Reasons` gains a required `category` (Voluntary / Transfer /
  Medical/LOA / Administrative) — deliberately **no** Disciplinary or Academic
  value. The category drives the terminal status on a full program separation:
  `Transfer → Transferred`, everything else `→ Withdrawn`
  (`withdrawal._resolve_separation_target`).
- **Transfer destination is captured on the transaction**, not the catalog: the
  Course Withdrawal Request gains `transfer_to_institution`, `transfer_to_program`,
  `transfer_to_country`, `destination_contact`, and `transcript_sent_on`. These
  are snapshotted into the status-history `notes`.
- Disciplinary exits never use `Withdrawal Reasons`. A dismissal carries its
  `Disciplinary Reason` and lands a history row with `category = "Disciplinary"`;
  the Course Withdrawal Request it spawns uses a dedicated, auto-seeded
  "Disciplinary Dismissal" withdrawal reason only to satisfy the required field.

## Consequences

Easier: reportable exit categories, structured transfer tracking, clean
separation of voluntary vs disciplinary exits. Harder: two catalogs to maintain.
Open: transfer destination institution is free text — a linked institution
registry could come later.
