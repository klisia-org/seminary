# 015 — Orthogonal Program Flags & Conditional Workflow Transitions

**Date:** 2026-05-01
**Status:** Accepted

## Context

A single `ongoing` Check field was added to `Program Level` to mark programs with no end (continuing-ed, free auditing, devotional courses). The intent was a one-stop flag: ongoing programs would skip graduation, GPA, transcript impact, *and* invoicing.

That collapsed two distinct concerns into one and broke as soon as a real-world combination surfaced: an ongoing program may still offer paid one-off courses, and a free program may still award credits and graduate students. We also needed a way to fast-path withdrawal and CEI workflows for these flagged programs without writing one workflow per combination.

Three sub-decisions emerged together:

1. How many flags, and where?
2. How to keep the gating value stable once a Program is linked to a Level?
3. How to surface the fast-paths in workflow UIs without forking workflow definitions?

## Decision

### Two orthogonal flags, not one

- **`Program Level.ongoing`** — schema-level flag, mirrored onto every Program at that level. Drives transcript / graduation / alumni concerns: skips GPA recompute, graduation snapshot/audit, alumni transition, and Academic Review on withdrawal.
- **`Program.is_free`** — per-Program user-editable flag, independent of Level. Drives money concerns: skips enrollment Sales Invoice generation (CEI on_submit, NAT/NAY/monthly trigger generators), and skips Financial Review on withdrawal.

The four combinations all have meaningful semantics (e.g., paid continuing-ed = ongoing + not free). Bundling them into one flag would force a future migration as soon as one combination diverged.

### Submittable lookup tables for behavior-gating config

`Program Level` becomes **Submittable**. Once submitted, `ongoing` is locked. Programs filter the level picker by `docstatus = 1`. To change `ongoing` after the fact, the registrar amends → new revision → re-points Programs deliberately.

This replaces the originally-planned `on_update` propagation hook from Program Level to every linked Program. The submittable lifecycle gives traceability (Submit/Cancel/Amend audit trail) for free, eliminates a class of "what happens if the propagation hook fails halfway?" edge cases, and makes "this Program's ongoing flag changed" a deliberate workflow event rather than a silent flip.

The same pattern should apply to other lookup tables whose values gate downstream behavior. Lookup tables that only carry labels/descriptions don't need it.

### Atomic-token mirror with explicit hydration fallback

Each Program carries a hidden, read-only `is_ongoing` Check field with `fetch_from: "program_level.ongoing"`. Workflow conditions and Python branches everywhere check `program.is_ongoing` (a single column lookup) instead of joining through `program_level`. Same pattern for `Program.is_free` mirrored onto downstream docs (CEI, Course Withdrawal Request) so workflow `condition` expressions can evaluate `doc.is_free` without nested lookups.

**Caveat that bit us:** Frappe's two-level `fetch_from` chain (`Doc.field → Linked.field → Linked2.field`) does not reliably resolve in a single validate pass. New CEIs for free programs were saved with `is_free=0` (the JSON default) because the chain `program_ce.program → program_data → is_free` resolved out of order. Mitigation: **explicit hydration in the controller's `validate()`** with one `frappe.db.get_value(parent, ..., as_dict=True)` lookup. `fetch_from` stays as the form-load behavior; the validate hydration is the source of truth at save time.

### Conditional workflow transitions, not hook-based auto-advance

Initial design used `db.set_value` from `on_update_after_submit` hooks to skip workflow states for ongoing/free programs (e.g., bypass Academic Review for ongoing CWRs). That broke the next-action UI: Frappe renders workflow buttons strictly from declared transitions, so a force-stamped state landed the document in a place with no visible forward path.

**Replacement:** declare the fast-paths as Frappe Workflow transitions with `condition` expressions on the gating fields. Multiple transitions from the same state with mutually exclusive conditions render as separate buttons (or none) per program flags. Course Withdrawal Request (CWR) gained:

- Draft → Submitted (Submit) — `not doc.is_ongoing` for academic users; `not (doc.is_ongoing and doc.is_free)` for students
- Draft → Academically Approved (Submit & Skip Academic Review) — `doc.is_ongoing and not doc.is_free`, Academics User
- Draft → Completed (Submit & Complete) — `doc.is_ongoing and doc.is_free`, both roles

System-driven `db.set_value` advancement (per ADR 013) remains valid for transitions that have no user-facing entry point — e.g., a cron nightly batch advancement, or `withdrawal._mark_cei_withdrawn` flipping CEI's workflow_state to "Withdrawn" as a list-view marker. The rule: if a button needs to render anywhere, declare a transition. Otherwise `db.set_value` is fine.

## Consequences

**Easier:**

- Adding a new "this Program is X" flag is now a small, well-trodden path: define the flag, mirror it where workflow conditions need it, hydrate explicitly in validate.
- Workflow fast-paths are visible in the workflow definition. Future contributors reading `workflow.json` see exactly which roles see which buttons under which conditions. No hidden hook-driven state advancement.
- Toggling `ongoing` on a Program Level is now a deliberate, audit-trailed action (Submit → Amend → re-link), not a silent flip with downstream surprises.
- Validation hydration covers the case Frappe's `fetch_from` chain misses, so flags are consistent server-side regardless of how the doc was created (form, import, programmatic).

**Friction (accepted):**

- Adding a new state to a CWR/CEI workflow now means updating both the JSON and the `Workflow Action Master` / `Workflow State` fixtures. We learned this the hard way when "Awaiting Payment", "Withdrawn", and the new actions had to be created manually before fixture export caught up.
- Each gating flag costs at least one mirrored field per consumer doctype (e.g., `is_free` on Program, on CEI, on CWR). The duplication is the price of letting workflow `condition` expressions evaluate against `doc.*` without runtime lookups.
- Two-level `fetch_from` chains remain a footgun. We documented it as a Frappe quirk and codified the explicit-hydration workaround, but new contributors will rediscover it. The chain is alluring because the JSON is shorter; the workaround is in code, not schema.

**Open / residual:**

- The `Program.is_ongoing` mirror has no automatic refresh when an admin amends a Program Level (Frappe doesn't propagate the new `ongoing` value to already-linked Programs). The submittable lifecycle makes this a rare, deliberate event — but a registrar who amends a Level and expects every linked Program to update will be surprised. We accept this; the alternative was the propagation hook we explicitly rejected.
- A future generic flag-driven workflow framework could collapse the per-flag mirror+hydrate boilerplate into a single helper. Out of scope for this iteration; revisit when the third copy appears.

## References

- [`program.json`](../../seminary/seminary/doctype/program/program.json) — `is_free`, `is_ongoing` (mirrored), `require_pay_submit`, `percent_to_pay`
- [`program_level.json`](../../seminary/seminary/doctype/program_level/program_level.json) — `is_submittable: 1`, `ongoing` flag
- [`program.py`](../../seminary/seminary/doctype/program/program.py) — `validate()` forces gating fields off when `is_free` is set
- [`fixtures/workflow.json`](../../seminary/seminary/fixtures/workflow.json) — Course Withdrawal conditional transitions, Course Enrollment Lifecycle workflow
- [`withdrawal.py`](../../seminary/seminary/withdrawal.py) — `process_academic_approval` defensive `is_ongoing` no-op; `_mark_cei_withdrawn` sets workflow_state on CEI
- [`patches/submit_program_levels.py`](../../seminary/seminary/patches/submit_program_levels.py) — backfills existing Levels to `docstatus=1`
- [`patches/clear_pay_gate_on_free_programs.py`](../../seminary/seminary/patches/clear_pay_gate_on_free_programs.py) — backfills `is_free` programs' gating fields
- ADR 013 — established the system-driven `db.set_value` workflow pattern this ADR scopes ("only when no UI entry point")
