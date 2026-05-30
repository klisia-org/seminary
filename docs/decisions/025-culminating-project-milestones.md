# 025 — Culminating Project Milestones: Slim Lifecycle + Configurable Dated Milestone Model

**Date:** 2026-05-29
**Status:** Accepted

## Context

ADR 024 put culminating projects on a single, linear Frappe Workflow (Draft →
Proposal Submitted → … → Defended → Completed). Enriching `Culminating Project
Type` with capability flags exposed that a native workflow cannot model what
real projects need:

- **Per-type stages** — a Doctrinal Statement, a Masters Thesis and a PhD
  Dissertation have different steps; one global fixture workflow can't vary.
- **Dated milestones across multiple terms/years** — prospectus, chapters, full
  draft, defense, final submission, each with a due date.
- **Repeating milestones** — multiple dissertation chapters.
- **Multiple sign-offs per milestone** — advisor + second/third reader for a defense.

A Frappe Workflow is good at *document lifecycle + permissions + the single
"Completed → graduation requirement Fulfilled" signal*, but bad at variable,
dated, multi-party checkpoints.

## Decision

### Separate lifecycle from progress

**Lifecycle** is a slimmed, type-agnostic Frappe Workflow:
`Draft → Active → Under Review → Completed` (+ `Rejected`, `Withdrawn`). It gates
permissions and carries the graduation signal (`linked_doc_status = "Completed"`).
`_reflect_state_to_sgr` shrank to five entries. The old rich states
(Proposal/Drafting/Revisions/Defended) became **milestones**, not states. The
slim states are barely entangled — nothing in Vue or reports hard-codes them.

**Progress** is a data-driven, per-type, dated milestone model, reusing the
proven graduation template→snapshot pattern (ADR 012):

```
Culminating Project Type
  └ milestones[]  (TEMPLATE: Culminating Project Type Milestone)
        name, sequence, kind, mandatory, repeatable+default_count,
        requires_submission, creates_event, signoff_* flags, anchor+offset
              │ snapshot_milestones() when the project is Activated
              ▼
Culminating Project
  └ milestones[]  (INSTANCE: Culminating Project Milestone)
        due_date (computed), status, completed_on, instance#, event
        ▲ sign-offs in Culminating Project Milestone Signoff (one row per role)
```

- A **Defense is just a milestone** (`kind = Defense`) with its required
  sign-offs; the per-type capability flags from ADR 024 (`req_second_reader` /
  `req_third_reader` / `defense`) were removed. The project keeps its
  advisor/second/third reader Link fields (they name the people).
- **Sign-offs are data-driven**: each milestone declares required roles via
  `signoff_advisor/second_reader/third_reader/committee` checks; a milestone
  flips to **Approved** once every required role has an Approved sign-off. Each
  sign-off carries a reviewer `attachment` and `comment`.
- **Completion gate**: `milestones_complete` (computed) is the `condition` on
  the `Complete` transition — the button only appears when every mandatory
  milestone is Approved/Waived (per the workflow-conditions convention).
- **Overdue**: the daily scheduler flips open, past-due milestones to `Overdue`.
- `creates_event` flags a milestone (e.g. Defense) for which the frontend will
  later create a calendar `Event` (wiring deferred).

### Unified `DateRuleResolver`, scoped to milestones

`seminary/seminary/date_rules.py` is a new plain utility (not a Frappe Module):
`resolve(anchor, offset_value, offset_unit, context, *, weekday, weekday_strict,
holiday_adjust, clamp_to)`. Anchors come from a caller-supplied `context` dict;
term offsets do a **real term walk** (fixing graduation.py's `*120 days`
approximation), which matters for multi-year PhD timelines. It is now the single
resolver behind **all four** dated rules — milestones,
`cs_lifecycle.resolve_window_dates`, `withdrawal.calculate_dynamic_date`, and
graduation's Time-Offset due dates — replacing the three ad-hoc implementations.

Migration was behaviour-preserving where it mattered: CS windows and withdrawal
deadlines produce byte-identical dates (the withdrawal weekday rule's
"advance even when already on the target weekday" is preserved via
`weekday_strict=True`; holidays come from the company's default holiday list).
Graduation's day offsets are unchanged; its term offsets switch from the
`*120-day` approximation to a real walk from the term covering the anchor —
and deliberately yield **no date** (rather than a misleading one) when no
Academic Term covers the anchor (e.g. an offset anchored years out with no
terms defined that far). `term_for_date` is covering-term-only for this reason.

## Consequences

- Two important Frappe gotchas, both now handled: `validate()` does **not** run
  on `update_after_submit`, so milestone-derived fields recompute in
  `before_update_after_submit`; and post-submit field writes need
  `allow_on_submit` — set on `workflow_state`, `milestones`, `milestones_complete`,
  `proposal_approved_on`, `defended_on`.
- Backfill patch maps existing projects onto the slim states and seeds
  `milestones_complete=1` for milestone-less legacy projects.
- Seminaries express any culminating-project shape as data (1 milestone for a
  Doctrinal Statement; a dozen dated, multi-term milestones for a PhD) without code.
- Sign-off roles use fixed per-role checks tied to the project's reader slots
  rather than a free MultiSelect — simpler, and validated against the slots.
- `Culminating Project Type` is **not** a fixture: it carries seminary-configured
  milestone rows, and a fixture re-import on every migrate would wipe them. The
  starter types are seeded create-only-if-missing via `install.seed_culminating_project_types`
  (after_install for fresh sites, a one-time patch for existing ones), never
  overwriting an existing type or its milestones.

## Follow-ups
- Student/advisor Vue workbench (milestone timeline, submission upload, sign-off)
  and the Defense `Event` creation wiring.
