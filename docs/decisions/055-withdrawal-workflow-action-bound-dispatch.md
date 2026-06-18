# 055 — Withdrawal Workflow: Five States with Action-Bound Dispatch

**Date:** 2026-06-17
**Status:** Accepted

## Context

The Course Withdrawal workflow had eight states: `Draft → Submitted → Academic Review → Academically Approved → Financial Review → Financially Approved → Completed`, plus `Rejected`. Three of those carried side effects, fired on **state entry** via `on_update_after_submit` keyed on the resulting `workflow_state`:

- *Academically Approved* → `process_academic_approval` (withdraw the CEI, apply the withdrawal rule's grade treatment)
- *Financially Approved* → `process_financial_approval` (refund credit notes)
- *Completed* → `process_completion` (finalize a program separation)

The remaining states (`Submitted`, `Academic Review`, `Financial Review`) were pure holding queues — same role, no logic — so the flow was mostly clicks with nothing to evaluate. Two problems compounded the bloat:

1. **State-entry dispatch can't survive a collapse.** With only one resting state per department, the academic decision must be able to land in *either* Financial Review (a refund is due) *or* Completed (no refund — conclude directly). Keying the CEI withdrawal on a single state would skip it on the conclude path.
2. **A latent fast-path gap.** Frappe runs `on_submit` (not `on_update_after_submit`) for a Draft→submitted-state transition (`_action == "submit"`). The dispatcher was only on `on_update_after_submit`, so the ongoing-program Draft fast-paths never fired their processors at submit; it worked only because program-separation *parents* spawn children that do the real per-CEI work. A single-course ongoing withdrawal silently skipped the CEI withdrawal.

There were no tests on this money- and transcript-touching flow.

## Decision

**Five states:** `Draft → Academic Review → Financial Review → Completed` (+ `Rejected`). Academic Review is the Registrar queue; Financial Review belongs to the Accounts User (the cross-department `allow_edit` handoff is preserved).

**Side effects bind to the transition (action), not the resulting state.** A single `dispatch_withdrawal_effects(doc)` derives the edge from `get_doc_before_save()` and runs the right processors:

| Edge | Effects |
| --- | --- |
| Academic Review → Financial Review | academic |
| Academic Review → Completed (Conclude) | academic + completion |
| Financial Review → Completed | financial + completion |
| Draft fast-path → Financial Review | academic |
| Draft fast-path → Completed | academic + completion |
| → Rejected | none |

Program-separation **parents** carry no single CEI, so per-CEI academic/financial effects are guarded off for them; `process_completion` keeps its own child-gating.

The dispatcher is called from **both** `on_update_after_submit` (1→1 transitions) and the controller's `on_submit` (the 0→1 Draft fast-paths) — Frappe fires exactly one per transition — which also closes the latent fast-path gap.

**No-refund auto-conclude.** A computed `refund_due` Check on the Withdrawal Request (mirrors `process_financial_approval`'s gate: a withdrawal rule with refunds applies *and* the program is not free) drives mutually-exclusive workflow conditions. In Academic Review the Registrar sees **Approve Academically** (→ Financial Review) when `refund_due`, or **Approve Academically & Conclude** (→ Completed) otherwise. The ongoing fast-paths route the same way.

A migration patch remaps in-flight requests (`Submitted→Academic Review`, `Academically Approved→Financial Review`, `Financially Approved→Completed` + run completion) and recomputes `refund_due` for every non-terminal request. Mock-based tests lock the dispatch edge-table and assert the routing invariant (exactly one button per role × program-flag combination).

## Consequences

- **Easier.** "Currently pending" is a one-state filter; the no-refund path is one click; the latent single-course fast-path bug is fixed; the dispatch contract is unit-tested without a database.
- **Harder.** Side effects now depend on the (previous → current) edge via `get_doc_before_save()`, so the workflow conditions and the dispatch table must be kept in sync — the routing-invariant test guards the conditions, and the edge-table test guards the dispatcher. Reaching `Completed` is meaningful only together with its incoming edge, not on its own.
- **Open.** The Desk workflow screenshot in the staff docs was replaced with a generated `LifecycleDiagram`. The `Submitted` / `Academically Approved` / `Financially Approved` and `Send for…` / `Submit & Skip…` masters are now referenced by no workflow (`Submitted` is still used by the CEI and other workflows; the `Send for Financial Review` action by Graduation Request) — the withdrawal-exclusive ones are left in place as harmless orphans rather than deleted. Supersedes the relevant parts of [016](016-payment-gated-cei-lifecycle.md); related to [031](031-withdrawal-vs-disciplinary-reason-taxonomies.md).
