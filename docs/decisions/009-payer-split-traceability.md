# 009 — Payer Split Traceability

**Date:** 2026-04-22
**Status:** Accepted

## Context

Payers Fee Category PE (PFC) holds the per-Program-Enrollment payer split: who pays what share of each Fee Category, captured in the `pgm_enroll_payers` child table (one row per fee_category × payer with `pay_percent`, `pep_event`, `payterm_payer`). The four billing paths — [generate_nat_invoices](../../seminary/seminary/api.py), `generate_nay_invoices`, `generate_monthly_invoices`, and the PFC's [get_inv_data_pe](../../seminary/seminary/doctype/payers_fee_category_pe/payers_fee_category_pe.py) — read these rows live to build Sales Invoices.

Before this ADR, every registrar edit mutated `pgm_enroll_payers` in place with no audit trail. A common scenario surfaced the gap: a payer (e.g. a sponsoring church) calls mid-term and asks to stop paying after a given month. The registrar opens the PFC, edits `pay_percent`, saves — and the original intent disappears. The only reconstructable history is via past Sales Invoices, which tells you what *was* billed but not when or why the split changed.

We need: (a) a record of *every* payer-split change with user/timestamp/diff, and (b) a place for the registrar to capture the *narrative* behind each change ("Pastor Joe — Oak St Church — call on 2026-05-15"). What we don't need today (see Deferred) is genuinely time-windowed billing where May and June bill under different splits without manual coordination.

## Decision

**Audit-only**, not submittable, not effective-dated. Two pieces of machinery:

### 1. `track_changes` on PFC

Set `"track_changes": 1` on the PFC doctype. Frappe's Version doctype serializes the parent including child rows on every save, so `pgm_enroll_payers` adds, removes, and field edits show up in the document's Version History sidebar with full diff. Matches the convention used by 45+ other doctypes in this app. No flag is needed on the child table itself — child track_changes is redundant when the parent has it.

### 2. Required `change_reason` field with auto-clear

A `Small Text` field on PFC. Optional at the JSON level (so the automatic `get_payers` / `get_payers_fees` creation path still works), but enforced by the controller on update:

- `validate()` — on non-new docs, diff the current `pgm_enroll_payers` against `self.get_doc_before_save()` via tuple signature `(fee_category, payer, pay_percent, pep_event)`. If any row added/removed/changed and `change_reason` is blank, throw.
- `on_update()` — clear `change_reason` via `frappe.db.set_value(update_modified=False)` after the save commits. Forces a fresh reason for the next edit and prevents stale narratives from carrying forward.

The cleared write uses `update_modified=False` so it doesn't bump the timestamp or retrigger hooks. The reason is captured in the *previous* save's Version entry before clearing, so history is preserved.

### 3. `add_comment` for scholarship cascades

`add_scholarship` mutates `pgm_enroll_payers` via `frappe.db.set_value` and `frappe.delete_doc`, bypassing the parent's save lifecycle. That means it bypasses `validate()` (intentional — scholarships are self-describing system events that don't need a registrar narrative) and *also* bypasses `track_changes` (`db.set_value` doesn't write Version entries for child rows). To keep the document timeline complete, `add_scholarship` calls `self.add_comment("Info", ...)` at the top of each branch ("Scholarship X applied." / "Scholarship removed."). Comments appear in the Activity log alongside Version entries.

## Alternatives considered

### Submittable PFC — rejected

Was the obvious first instinct (it's how ERPNext models almost everything that needs an audit trail). Three reasons we ruled it out:

1. **It doesn't solve the actual problem.** Submittable gives you named cancelled/amended versions, not time-windowed billing semantics. On June 1 the Monthly generator still reads the *current* PFC's child rows. Pastor Joe's case still requires manual orchestration around billing dates.
2. **It breaks `add_scholarship`.** The method does `frappe.db.set_value` on `pgm_enroll_payers` rows after the PFC is created. Once a PFC is submitted, child rows are locked — set_value would fail. The JS `after_save` hook in `payers_fee_category_pe.js` also calls `.save()` again, which fails on a submitted document.
3. **It collides with the singleton-per-PE invariant.** `get_payers` (the `Program Enrollment.on_submit` hook), `get_inv_data_pe`, and the three billing generators all assume one mutable PFC per Program Enrollment. Amending breaks `frappe.db.exists` checks and creates orphaned rows.

The submittable path would have been a multi-week refactor of four call sites *and* still wouldn't have solved the time-varying billing question.

### Full effective-dated `pgm_enroll_payers` rows — deferred

Add `effective_from` / `effective_to` to each `pgm_enroll_payers` row. Pastor Joe's call becomes: close the church's existing row with `effective_to = 2026-05-31`, insert a new row with `pay_percent = 0` and `effective_from = 2026-06-01`. Generators filter rows valid on the billing date. Clean, declarative, and the audit trail falls out naturally.

The cost is significant: changes to all three billing generators in [api.py](../../seminary/seminary/api.py), the PFC's `get_inv_data_pe`, the four scholarship reports (`active_scholarships`, `all_active_scholarships`, `count_of_all_active_scholarships`, `active_scholarships_(all_types)`), the portal's `financials.py`, and rewriting `add_scholarship` to version rows instead of mutating in place. Worth doing the day a real case demands it. Until then, the workaround for Pastor Joe is for the registrar to time the edit between billing cycles (after May 1 Monthly billing, before June 1) — and the audit trail (track_changes + change_reason) lets us prove when the change happened and why.

## Consequences

**Easier:**
- Every registrar edit is recoverable: who, when, what changed, plus the registrar's narrative for that specific edit.
- Scholarship cascades show up in the document timeline despite mutating via direct SQL.
- No structural change to the billing generators or the singleton-PFC invariant.
- Matches the existing repo convention (`track_changes` is everywhere).

**Friction (accepted):**
- Registrars must type a reason on every payer-share edit. Reasonable — payer splits drive money flowing to/from external parties (churches, scholarship funds), so a one-line note is cheap insurance.
- The `change_reason` field is intentionally short-lived per save (auto-cleared). A registrar reloading the form *after* their edit sees a blank field; the reason lives in Version History only. This is intentional but worth flagging in user-facing docs.

**Open / residual risks:**
- **Time-varying billing remains unsolved.** If a registrar edits the split *between* Monthly's `last_monthly_invoiced_on` flag being set and the next 1st-of-month run, the next billing uses the new split. If they edit after a 1st but want June to bill under the old split, manual correction (cancel + recreate) is needed. The audit trail tells you what happened; it doesn't compensate for it. Revisit if real cases accumulate.
- **`db.set_value` paths still bypass `validate`.** Beyond `add_scholarship`, any future code that mutates `pgm_enroll_payers` via direct SQL also bypasses the change-reason requirement. The convention is: anything that's a *system-driven cascade* (scholarships, hypothetically future automatic adjustments) goes through `db.set_value` + `add_comment`; anything *user-driven* goes through the form. New automated mutations should follow the same pattern.
