# 047 — First-class scholarships

**Date:** 2026-06-12
**Status:** Accepted

## Context

Scholarships were a thin, percentage-only mechanism. A `Scholarships` template
held a discount % per fee category; linking it on `Payers Fee Category PE` ran
`add_scholarship()`, which carved the % out of the student's payer row and inserted
a `pgm_enroll_payers` row for the configured scholarship customer. At invoice time
the three billing paths detected that customer (`customer == scholarship_cust`) and
emitted a 100%-discounted invoice booked to the scholarship cost center — the
"forgiveness".

Gaps: (1) **No flat-value awards** — a fixed dollar amount can't be a stable % of a
credit-based fee that varies by term, yet smaller seminaries budget in dollars.
(2) **No granting criteria, no application/request flow, no retention criteria**
(e.g. min credits/term, also needed for international students). (3) **No
budget/availability signal**, so students applied against empty funds.

## Decision

**Discounts are computed at invoice time, not baked into payer rows.** The student
keeps their full payer percentage; `billing.resolve_scholarship(program_enrollment,
fee_category, student_gross, academic_term)` returns the amount to forgive for the
student's line only. Percent terms forgive a proportion; **Flat** terms forgive a
fixed amount **capped per academic term** — the cap is enforced by summing prior
forgiveness invoices tagged `SCH:<award>:<fee>:<term>:<scope>`, so a flat award
billed across several course invoices in a term is never over-applied. The student
invoice records the award as an absolute `additional_discount_amount`; a separate
100%-discounted invoice to the scholarship customer at the scholarship cost center
preserves the forgiveness booking. All three paths (`get_inv_data_pe`,
`get_inv_data_ce`, `create_extension_invoices`) share the resolver and only ever
apply it to the **student's** payer line.

**Two doctypes.** `Scholarships` stays the reusable *template* — now carrying a
`scholarship_type`, per-fee terms of mode **Percent | Flat**, granting criteria
(`min_gpa`, `min_credits_total`), retention criteria (`retain_min_credits_per_term`,
`retain_min_gpa`), a `cost_center` (defaulted from Seminary Settings, overridable),
`budget_slots`, and portal gates. The new **Scholarship Award** is the per-enrollment
grant, with a workflow (`Draft → Submitted → Under Review → Active`, plus
`Rejected/Suspended/Ended`), effective dates, a snapshot of the template's terms at
grant time, and a `retention_status`. **One active/pending award per Program
Enrollment** is enforced in `validate()`.

**Budget reuses ERPNext.** The dollar ceiling lives in an ERPNext **Budget** against
the template's cost center; `scholarship.get_scholarship_availability` compares it to
the **gross** of scholarship-customer invoices on that cost center (the
`scholarship_sales_invoices` method) because the forgiveness is 100%-discounted and
nets ~0 in the GL. `budget_slots` adds a headcount cap. `is_open` gates the portal.

**Portal applications are double-gated.** A scholarship is offered only when the
global `Seminary Settings.allow_portal_scholarship` **and** the template's
`show_on_portal` are both on, the template `is_open`, and the student holds no award
on that enrollment. `Fees.vue` shows the held award + retention, or available
templates with requirements + Apply; `scholarship.apply_for_scholarship` creates the
award request.

**Retention flags, never revokes.** A daily `review_scholarship_retention` checks
each active award's min credits/term and min GPA — plus active employment for
Work-Study awards when `hrms_enable` is on (HRMS is a soft dependency: the award's
`Employee` link only matters when enabled) — setting `retention_status = At Risk` and
notifying registrars. Money and workflow state are never changed automatically.

**Migration.** A pre-sync patch (`stash_scholarship_links`) captures the legacy
`Payers Fee Category PE.scholarship` links before the column is dropped; a post-sync
patch (`migrate_scholarships_to_awards`) creates the awards and reverses the old
payer-row carve-out (restoring the student's share, deleting scholarship-customer
rows). Submitted invoices are untouched. The legacy field, `add_scholarship`,
`get_scholarships`, and the payer-row mechanism are removed.

## Consequences

Easier: flat **and** percent awards from one model; per-scholarship budgeting via
cost-center Budgets; a real application + retention lifecycle; an explicit discount
line auditors expect. Harder/risk: scholarship math now lives at invoice time (not
in payer rows), so reports and the withdrawal refund path were updated (the refund
now scales the absolute scholarship discount with the credited quantity). The
flat-per-term cap relies on the `SCH:` invoice tag, so cancelling a scholarship
invoice correctly frees that term's budget. Assumes one active award per enrollment
(no stacking).

## Accounting model and pending cases

Scholarships are recorded as a **tuition discount (forgone revenue)**: the
forgiveness is a 100%-discounted Sales Invoice to the scholarship customer booked to
the scholarship cost center, netting ~$0 in the GL. For **institutional aid** (merit
/ need waivers the seminary itself grants — the dominant case) this is the recognized
**scholarship allowance / contra-revenue** treatment under U.S. nonprofit/higher-ed
guidance (NACUBO; FASB ASC 958-605). Because it is an *allowance and not an expense*,
scholarships intentionally do **not** appear on the P&L as an expense and ERPNext's
native **Budget Variance Report** (built for expense GL actuals) cannot see them —
hence the purpose-built **Scholarship Budget vs Given** report, which compares the
ERPNext Budget ceiling on each `scholarship.cost_center` to the gross of the
scholarship-customer invoices there (same figures as `get_scholarship_availability`).

Two cases are **deliberately deferred** — the current discount model under-reports
them, and they likely warrant per-type accounting treatment when they arise:

1. **Donor- / endowment- / restricted-gift-funded scholarships.** When an external
   donor or a restricted fund pays for the award, GAAP generally wants the amounts
   **grossed up**: recognize the gift/grant revenue *and* a scholarship **expense**
   (or a release from restricted net assets), so both the money in and the money out
   are visible. The discount model shows neither, which donors and auditors typically
   will not accept for restricted funds.

2. **Work-Study.** Money tied to work performed at the seminary is generally
   **compensation** (a wage/expense, ideally through payroll/HRMS), not a tuition
   allowance. Treating a Work-Study award as a discount understates both wage expense
   and gross tuition.

When implemented, these would be modeled **per scholarship type**: only the affected
types (e.g. `scholarship_type` in {Work-Study} or a "funding source = donor/endowment"
flag) would post a real expense/journal entry to the cost center — at which point
those types would also surface in ERPNext's native Budget Variance Report, while
institutional-aid types keep the contra-revenue treatment. The `scholarship_type`
field and per-template `cost_center` already give us the seam to branch on.
