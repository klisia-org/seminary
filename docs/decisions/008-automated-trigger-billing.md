# 008 — Automated Trigger Billing

**Date:** 2026-04-21
**Status:** Accepted

## Context

Before this ADR, the "Roll Academic Term" server action conflated three unrelated operations inside a single function: academic-term flag management (`iscurrent_acterm`, `open`), student advancement in time-based programs (`roll_pe` → `petb_enroll`), and Sales Invoice generation for the `New Academic Term` / `New Academic Year` trigger events. It only ran when a human clicked a button, producing no audit of missed cycles, and none of the three invoice generators (`get_inv_data_nat` / `get_inv_data_nayear` / `get_inv_data_monthly`) checked for existing invoices before inserting — re-running duplicated. The `Monthly` trigger had a generator but no caller, so the fixture value was dead. The daily scheduler (`tasks.daily`) ran a stub `set_iscurrent_acterm` that only flipped flags and advanced student terms; billing never ran automatically.

Student advancement and billing have different risk profiles: advancement is a once-per-term decision a registrar should make after verifying grades are finalized, whereas billing is a mechanical operation that should fire on calendar dates and must be safely repeatable.

## Decision

### Split

- `seminary.seminary.api.roll_students(academic_term=None)` — student-advancement only. Calls `roll_pe`. Wired to the Academic Term "Advance Students" server action and the Registrar Hub primary button. No billing side-effects.
- `seminary.seminary.api.generate_nat_invoices(academic_term)` / `generate_nay_invoices(academic_year)` / `generate_monthly_invoices(as_of)` — billing only, driven by the daily scheduler.

### Automation

`tasks.daily()` is now a single idempotent scan that runs under a global `Seminary Settings.billing_automation_enabled` kill switch:

1. `_update_term_flags(today)` — flips `iscurrent_acterm` / `open` based on dates; does NOT advance students.
2. `_run_nat_for_due_terms(today)` — selects `Academic Term` where `term_start_date <= today AND invoiced_nat_on IS NULL`; calls `generate_nat_invoices` per term.
3. `_run_nay_for_due_years(today)` — same pattern on `Academic Year` / `invoiced_nay_on`.
4. On the calendar 1st, `generate_monthly_invoices(today)` iterates active Program Enrollments whose Fee Categories have `fc_event = "Monthly"`.

The `start_date <= today` predicate inherently self-heals after missed cron runs: the next successful `daily()` picks up any pending period. No separate fallback job is needed.

### Idempotency — belt-and-suspenders

Two layers, because a single layer is insufficient:

1. **Fast-path flag** on the parent record (`Academic Term.invoiced_nat_on`, `Academic Year.invoiced_nay_on`, `Program Enrollment.last_monthly_invoiced_on`). Once set, the generator skips immediately.
2. **Per-row safety net** via a Sales Invoice Custom Field `seminary_trigger` tagged `NAT:<term>:<pep>` / `NAY:<year>:<pep>` / `MONTHLY:<YYYY-MM>:<pep>`, where `<pep>` is the unique `pgm_enroll_payers` row. Before each `insert()`, the generator checks `frappe.db.exists("Sales Invoice", {"seminary_trigger": tag, "docstatus": ["<", 2]})`. This catches drift (flag cleared for recovery, partial prior run that died mid-loop, etc.) without re-billing.

### `effective_from` on Fee Category

Monthly-only Date field. A Program Enrollment is billed for a given Monthly Fee Category only when `PE.enrollment_date > FC.effective_from` — grandfathering students who enrolled before a new monthly fee existed. Empty → no restriction.

### Recovery

"Regenerate Current-Term Invoices" on the Registrar Hub clears `invoiced_nat_on` on the current term and calls `generate_nat_invoices`. The safety-net query prevents duplicates; only missing invoices are created. Manual recovery for Monthly / NAY is by clearing the flag on the relevant parent record and waiting for the next daily run.

### Fee Category submittable

All billing SQL now filters `fc.docstatus = 1` so draft / cancelled Fee Categories never drive invoice generation.

## Alternatives considered

- **Separate `hourly` / `weekly` / `monthly` scheduler events** — rejected. Daily + date check covers all three triggers, self-heals on missed runs, and keeps one cron surface.
- **Flag-only idempotency** (no `seminary_trigger` tag) — rejected. Flag can drift if invoices are deleted manually, if a run crashes mid-loop, or during recovery.
- **Query-only idempotency** — rejected. Re-checking every row on every run is O(N) work forever; the flag provides an O(1) fast path for the common case.
- **Lifecycle guards blocking all writes** (like ADR 007 for Trigger Fee Events) — rejected. The doctype fixtures themselves aren't at risk; the problem was the generators, not the definitions.
- **Back-compat patch to backfill flags on past terms** — not needed: system is not live.

## Consequences

**Easier:**
- A missed cron run no longer means skipped billing: the next daily run catches up.
- Re-running recovery doesn't duplicate invoices.
- The Monthly trigger is now live.
- Student advancement is clearly separated from billing; a registrar can verify grades before clicking "Advance Students" without the button side-effecting invoices.

**Open questions / residual risks:**
- Grade-finalization is still a manual gate; there is no doctype flag preventing `roll_students` from running against a term whose grades aren't finalized. Deferred to a future ADR.
- `rate: 0` + `price_list_rate: X` in the generated SI items relies on `run_method("set_missing_values")` to fetch the rate from the Item Price. If that hook is bypassed (e.g. by a future ERPNext refactor) invoices would post at zero. A follow-up refactor should compute rates explicitly.
- The three near-duplicate generators share a helper (`_create_trigger_invoice`) for SI construction, but the per-event SQL is still triplicated. Consolidating into one parametrized helper is a later cleanup once automation is proven green.
- `ip.item_code = fc.item` ignores `Item Price.valid_from` / `valid_upto`. A stale or future-dated price could land in an invoice. Follow-up.
- Any Fee Category accidentally set to `fc_event = "Monthly"` will start billing on the next 1st. After deploy, audit Fee Categories once to confirm intent.
