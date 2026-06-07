# 032 — Disciplinary subsystem and shared separation spine

**Date:** 2026-06-01
**Status:** Accepted

## Context

The app had no disciplinary tracking. Two stub doctypes (`Disciplinary Reason`,
`Disciplinary Incident`) existed but were unwired. We needed a repository for
consistency/stats, a way to encode progressive discipline, and — at the extreme
— a disciplinary dismissal, without duplicating the program-separation cascade.

## Decision

Follow the app's **Catalog + advisory matrix + transaction** idiom (mirroring
Withdrawal Reasons/Rules + Course Withdrawal Request):

- **`Disciplinary Action`** — a controlled catalog of sanction types, each with a
  `triggers_dismissal` flag. Seeded via install hook + patch (not fixtures).
- **Advisory matrix** — a `recommended_actions` child table on `Disciplinary
  Reason` maps occurrence → recommended action(s). The incident form pre-fills
  suggestions (`disciplinary.suggest_actions`, marked `was_suggested`); the
  adjudicator confirms or overrides. **Nothing auto-enforces** except the
  dismissal trigger — due process requires human discretion.
- **Applied actions** are recorded on `Disciplinary Incident`. When an applied
  action's catalog row has `triggers_dismissal=1`,
  `disciplinary.on_incident_update` calls **`initiate_program_separation`** with
  `separation_status="Dismissed"`, `separation_category="Disciplinary"`.

We **re-modelled Full Program Withdrawal** rather than adding a Program
Separation Request doctype: a parent Course Withdrawal Request may now originate
at the program level (no pre-selected CEI), supports a timing choice (Immediate /
End of Current Term / Specific Date, deferred via `process_due_separations`), and
finalizes through the same `process_completion → set_program_status`. Dismissal
reuses this one cascade, differing only in terminal status/category.

## Consequences

Easier: one separation path, consistent stats, progressive-discipline guidance.
Harder: the trigger must guard re-entrancy/double-dismissal (it does, via
existing-request and terminal-status checks).
