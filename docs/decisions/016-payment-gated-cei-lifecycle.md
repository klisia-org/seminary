# 016 — Payment-Gated Course Enrollment Lifecycle

**Date:** 2026-05-01
**Status:** Accepted

## Context

A Course Enrollment Individual (CEI) used to be a single docstatus 0→1 step. On submit, three things happened simultaneously: a Sales Invoice was generated, a `Scheduled Course Roster` row was created, and a `Program Enrollment Course` row was added. The student was on the roster the moment they clicked Submit, regardless of whether they had paid.

For tuition-charging seminaries that's the wrong default. Many institutions hold a seat until payment posts; some accept partial down-payments (e.g., 50% to enroll, balance due during the term). Free programs and full-scholarship students should pass through transparently. The previous flow had `cei_si` ("Sales Invoice Created?") as the only enrollment-side payment marker — no read of actual payment state, no gate.

We also wanted **Withdrawn** to surface as a CEI list-view state. The `withdrawn` Check field was set by the withdrawal flow but invisible in standard list filters; registrars had to open each CEI to see status.

## Decision

### Four-state CEI workflow

A new "Course Enrollment Lifecycle" Frappe workflow on CEI:

```
Draft  →  Awaiting Payment  →  Submitted  →  Withdrawn
   ↘─────────────────────────────↗
```

- **Draft** (doc_status 0)
- **Awaiting Payment** (doc_status 1) — invoiced, not yet on roster
- **Submitted** (doc_status 1) — fully enrolled
- **Withdrawn** (doc_status 1) — terminal; set by the withdrawal flow

Two new Program-level toggles drive which path Draft takes:

- `Program.require_pay_submit` (Check, default 1, hidden when `is_free`)
- `Program.percent_to_pay` (Percent, default 100)

Workflow conditions:

- `is_free or not require_pay_submit` → Draft → Submitted
- `require_pay_submit and not is_free` → Draft → Awaiting Payment
- Awaiting Payment → Submitted: manual override "Mark as Paid" (Academics User), or automatic when `paid_percent ≥ percent_to_pay`

### Side effects move from `on_submit` to "Submitted" arrival

The previous `on_submit` hook bundle is split:

- **`on_submit` (docstatus 0→1)** — only invoice generation. Sales Invoices are created the moment the student clicks Submit, because the invoice is what they need to pay.
- **Workflow-state arrival "Submitted"** — runs `copy_data_to_scheduled_course_roster` and `copy_data_to_program_enrollment_course`. These hooks now live in [`cei_lifecycle.on_workflow_update`](../../seminary/seminary/cei_lifecycle.py), idempotently (check for existing roster / PEC rows before inserting). For Awaiting Payment CEIs the student is **not** on the roster — no LMS access, no PEC accumulation — until payment crosses the threshold.

This is the durable answer to "should the student be enrolled before they pay?": for non-free, payment-gated programs, no. The workflow state is what gates the side-effect bundle, not docstatus.

### Payment Entry is the right hook target, not Sales Invoice

ERPNext's Payment Entry submission updates `Sales Invoice.outstanding_amount` via `frappe.db.set_value` — a direct DB write that **does not** fire SI's `on_update_after_submit`. So a hook on SI's update event never runs when a payment posts; the CEI's `total_paid` and `paid_percent` would stay at zero forever.

The fix is structural: hook on **Payment Entry** `on_submit` and `on_cancel`. Walk `pe.references`, filter to `reference_doctype == "Sales Invoice"`, look up `SI.custom_cei`, and react on the linked CEI. Keep the SI hook in place too as a no-cost fallback for direct SI form saves, but understand it isn't load-bearing for payment events.

This pattern generalizes: any time you want to react to "another doc's controller wrote our field", check whether the writing controller uses `db.set_value` (silent) or `doc.save()` (fires hooks). When silent, hook the writing doc.

### Refund handling: notify, don't revert

When a Sales Invoice is cancelled or a credit note posts and the linked CEI's recomputed `paid_percent` drops below `percent_to_pay`:

1. Recompute `total_paid` / `paid_percent` on the CEI so the form reflects reality.
2. **Do not** revert workflow_state. A student who is mid-term should not silently fall off the roster because of a billing reconciliation.
3. Create a ToDo on the CEI for every Academics User and email them a templated summary. The registrar decides next steps (file a CWR, follow up with the student, accept the new reality).

Reverting was tempting for purity ("the threshold is no longer met"), but un-enrolling a student in week 8 because Accounts amended an invoice is a worse outcome than a notification.

### Withdrawn marker propagation from CWR

The Course Withdrawal Request flow's `_mark_cei_withdrawn` already wrote `withdrawn=1` and `withdrawal_request=<name>` on the CEI when academic processing ran. We extended the same `db.set_value` call to also set `workflow_state="Withdrawn"`. No new hook, no new event — just a third key in the existing dict.

This is a system-driven workflow transition (no user button, no role gate) so it follows ADR 013's `db.set_value` pattern rather than a Frappe transition. Distinguishes cleanly from the user-facing transitions in ADR 015: those need buttons; this one needs only a marker.

### Full-scholarship edge case

A non-free program where every payer is a 100%-discount scholarship will generate $0 Sales Invoices. The threshold check `paid / invoiced * 100 ≥ percent_to_pay` divides by zero. Treat `invoiced == 0` *with at least one submitted SI* as `paid_percent = 100` — vacuously satisfied. No SIs at all (configuration error or audit-only enrollment) stays at 0%, so the CEI sits in Awaiting Payment until a registrar investigates.

## Consequences

**Easier:**

- Payment really gates enrollment for non-free programs. The roster reflects who actually has a seat.
- Registrars see CEI workflow state as a colored pill in the standard list view: Awaiting Payment, Submitted, Withdrawn. Triage queries (`workflow_state = "Awaiting Payment"`) replace ad-hoc joins.
- Free programs and full-scholarship students pass through transparently. No `cei_si` confusion, no Awaiting Payment limbo for $0 invoices.
- Manual "Mark as Paid" override handles the messy real world (cash at the door, off-platform wire, special exceptions) without code changes.

**Friction (accepted):**

- Side-effect placement now spans two events: invoice gen at docstatus 0→1, roster/PEC at workflow-state-arrival "Submitted". A future contributor adding a fourth side effect must decide which event it belongs to. The split is documented; the file `cei_lifecycle.py` is the canonical reference.
- The Payment Entry hook fans out per-reference. A PE that pays five invoices recomputes five CEIs (deduplicated). Acceptable at seminary scale.
- The "notify, don't revert" decision means a CEI's `paid_percent` can be below `percent_to_pay` while workflow_state is still "Submitted". The form shows this honestly; the report does not (the report is forward-looking, not backward). Some registrars may be confused by the apparent contradiction. The ToDo + email is the discoverability layer.
- We mirrored four flags (`is_free`, `require_pay_submit`, `percent_to_pay`, `is_ongoing`) onto CEI for workflow conditions to evaluate against. The Frappe two-level `fetch_from` quirk (see ADR 015) bit us here too — explicit hydration in CEI's `validate()` is the source of truth, with `fetch_from` as the form-load convenience.

**Open / residual:**

- **Auto-revert on refund** is an explicit non-goal today. If a future seminary policy demands strict reversal, the hook in `cei_lifecycle.maybe_notify_registrar_on_invoice_cancel` is the single place to add it — but the rollback story for the roster + PEC is non-trivial (do you delete the roster row? mark the student withdrawn? what about grades already entered?). Defer until a real customer asks.
- **Concurrent payments** — two Payment Entries for the same CEI submitted simultaneously could both pass the threshold check and both call `_advance_cei_to_submitted`. The second `db.set_value` is idempotent on the workflow_state; `enroll_student` is idempotent on roster/PEC creation. Race-tolerant by construction; not by lock.
- **Audit-only enrollments** generate $0 invoices when audited at full scholarship and trigger the empty-`invoiced` branch. Currently advances correctly. If audit-only ever needs to gate on a different threshold, we'd add a separate `audit_percent_to_pay` — no change today.
- **Programmatic CEI creation** (imports, batch enrollments) calls `submit()` directly, which may not transition the workflow_state through `apply_workflow`. The validate hook hydrates the mirrors, but workflow_state can stay at "Draft" with docstatus=1 — an inconsistent state. The backfill patch normalizes existing rows; new programmatic creators should set `workflow_state` explicitly.

## References

- [`cei_lifecycle.py`](../../seminary/seminary/cei_lifecycle.py) — `on_workflow_update`, `enroll_student`, `_recompute_cei_payment_status`, `_advance_cei_to_submitted`, `on_payment_entry_submit`, `_notify_registrar_payment_dropped`
- [`course_enrollment_individual.py`](../../seminary/seminary/doctype/course_enrollment_individual/course_enrollment_individual.py) — split `on_submit`, `_hydrate_program_flags`
- [`course_enrollment_individual.json`](../../seminary/seminary/doctype/course_enrollment_individual/course_enrollment_individual.json) — workflow_state field, mirrored flags, payment tracking section
- [`hooks.py`](../../seminary/seminary/hooks.py) — Payment Entry events, CEI on_update_after_submit, SI fan-out
- [`fixtures/workflow.json`](../../seminary/seminary/fixtures/workflow.json) — "Course Enrollment Lifecycle" workflow definition
- [`patches/backfill_cei_workflow_state.py`](../../seminary/seminary/patches/backfill_cei_workflow_state.py) — one-shot Draft/Submitted/Withdrawn classification of legacy CEIs
- ADR 013 — system-driven `db.set_value` workflow pattern (used here for Withdrawn marker propagation)
- ADR 015 — orthogonal flags + conditional workflow transitions (this ADR's CEL workflow follows the same pattern for Draft → Submitted vs Draft → Awaiting Payment)
