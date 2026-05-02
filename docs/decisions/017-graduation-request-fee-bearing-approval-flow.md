# 017 — Graduation Request Fee-Bearing Approval Flow

**Date:** 2026-05-02
**Status:** Accepted

## Context

Many seminaries treat graduation as an explicit, fee-bearing approval step, not a passive consequence of finishing coursework. The student requests graduation toward the end of the program, pays a (usually non-refundable) fee, and gets recorded as an approved candidate; the request itself becomes the registrar's signal to start final-grade chasing, transcript prep, and ceremony logistics.

Before this ADR the app had no first-class "graduation request" concept. Audit-page eligibility (`graduation_eligible`, computed by `get_program_audit`) showed *whether the student would be allowed to graduate today*, but there was no way to distinguish that from *the student wants to graduate this term and is willing to pay for it*. Two different decisions, conflated into one boolean.

We also wanted to give programs control over **when** the request becomes available — some institutions want students to request as soon as they're enrolled in their last courses (so the registrar gets a heads-up to prioritize final grades), others want to wait until those courses are passed. And some programs don't have a graduation-request flow at all (registrar-driven graduation only), so this needs to be cleanly opt-in per program.

The graduation requirements engine (ADR 012) is orthogonal to this: it tracks whether a student has *met* the requirements (recommendation letters, projects, mandatory courses). Graduation Request is the layer above — *given the student meets / will soon meet the requirements, the request is the formal application to graduate*.

## Decision

### Two new Program flags

```
students_can_request_graduation : Check (default 0)
graduation_request_trigger      : Select(Enrolled in final courses, Passed final courses)
```

The Check is the master switch. Programs with it off never show a CTA, never compute candidacy, never accept a Graduation Request. The trigger Select is `mandatory_depends_on` the Check; both are hidden for ongoing programs.

The two trigger modes differ only in whether in-progress courses count toward "final":

- **Enrolled in final courses** — student becomes a candidate the moment their currently-enrolled courses, if all passed, would close out the program. Use when the registrar wants early visibility of graduating students.
- **Passed final courses** — student becomes a candidate only after grades are finalized and the eligibility math is true. Use when graduation should not be claimable until everything is in.

### `Program Enrollment.grad_candidate`

A read-only `Check` field, system-managed by `seminary/seminary/graduation_candidate.py`. The evaluator runs at every PEC mutation point (`cei_lifecycle.enroll_student`, `gpa.recompute_program_enrollment_gpa`, `program_enrollment.on_update_after_submit`) and overwrites the flag. Idempotent and bidirectional — a withdrawal that drops the student below requirements flips it back to 0 with no special unset path.

The math:

```
mandatory_remaining   = program mandatory courses ∉ (completed ∪ in_progress?)
emphasis_remaining    = active-emphasis mandatory courses ∉ (completed ∪ in_progress?)
credits_remaining     = (program credits required) − pe.totalcredits − in_progress_credits?
```

`in_progress?` is included for the "Enrolled" mode and excluded for "Passed". Candidate when all three reach zero.

### Library-level blockers

Some non-course requirements (recommendation letters, theses, doctrinal statements) are hard prerequisites — a school may not allow a student to even *file* a Graduation Request until they're in. We expose this as a per-Library flag rather than program-level config, because the same item should behave identically wherever it's used:

- New `Graduation Requirement Item.blocks_graduation_request` Check (depends_on `mandatory`).
- Snapshotted into each `Student Graduation Requirement` row at PE submit, so the evaluator doesn't have to join back to Library on every recompute.
- The candidacy evaluator (`_has_pending_blocker`) keeps `grad_candidate=0` whenever any mandatory blocker is not yet `Fulfilled` or `Waived`, regardless of how the credit/course math works out.

Schools that don't want this discrimination simply leave the flag off; behavior is identical to the original two-axis (mandatory + active) gating.

### `Graduation Request` doctype, mirroring CEI

The CEI payment-gated lifecycle (ADR 016) is the right starting pattern for a fee-bearing approval flow, with two extensions for the academic-vs-financial split many schools insist on. Graduation Request reuses CEI's payment plumbing wholesale and layers two manual review states on top:

```
Draft → Awaiting Payment → Academic Review → Financial Review → Approved
            (free skips →                 ↗ )
                                          ↓
                                      Cancelled  (docstatus 2)
```

- **Draft → Awaiting Payment** when `not doc.is_free`, **Draft → Academic Review** when free (no payment to collect).
- **Awaiting Payment → Academic Review** auto-transitions on payment via the Payment Entry hook ([`graduation_request_lifecycle.on_payment_entry_submit`](../../seminary/seminary/graduation_request_lifecycle.py)). System-driven via `db.set_value` per `feedback_workflow_conditions` memory — the Workflow doc's "Mark as Paid" button stays available for manual override.
- **Academic Review → Financial Review** is the academic checks gate (final grades posted, all blockers cleared, no late items). Manual transition by Academics User.
- **Financial Review → Approved** is the school-wide balance check (other pending payments, scholarships reconciled). Manual transition by Accounts User.
- `on_submit` generates Sales Invoices via the same `Payers Fee Category PE` / `pgm_enroll_payers` mechanism that CEI uses, filtering on `pep_event = 'Graduation Request'` (a new entry in the Trigger Fee Events fixture).
- Idempotency via a `gr_si` Check field — re-saves never re-bill.
- A new Sales Invoice custom field `custom_graduation_request` mirrors `custom_cei` for back-reference.

A `_guard_unique_active_request` validator blocks a second active Graduation Request on the same enrollment, considering all in-flight states (`Draft`, `Awaiting Payment`, `Academic Review`, `Financial Review`, `Approved`).

#### Why two manual review steps and not just one?

Splitting Academic and Financial review reflects how real registrars and bursars work. Academics check that the student has actually finished what they're supposed to (grades, requirements, blockers). The Bursar then verifies that the student has no other outstanding balances on the enrollment — graduation fee paid is necessary but not sufficient; a student with unpaid tuition from last term should not graduate. Mirroring the Course Withdrawal workflow (ADR not yet authored, but established by `Course Withdrawal Lifecycle` in fixtures) means staff already know the pattern.

#### Snapshot HTML on the GR Desk form

Two HTML fields on the Graduation Request form (`graduation_requirements_html` and `pending_payments_html`) render at refresh-time:

- **Graduation Requirements** — pulled from `get_program_audit`, with desk-style links to each linked document (Recommendation Letter, Culminating Project, etc.) and a *Blocks Request* column so reviewers see at a glance which items gated the request.
- **Pending Payments** — pulled from a new `get_pe_unpaid_invoices` endpoint that aggregates unpaid Sales Invoices across all PE→SI linkage paths (`custom_cei`, `custom_graduation_request`, and trigger invoices via `seminary_trigger`'s last segment which encodes the `pgm_enroll_payers` row name). Grouped by payer with a Total row.

The same Pending Payments table is also rendered student-side on the Program Audit page (without the registrar-facing desk links), so the student sees what's outstanding before they file. The student CTA does NOT block on pending payments — the **Financial Review** step is the gate. Surfacing it earlier just sets expectations.

### Cancellation: PE inactivation cascades

When a registrar deactivates a Program Enrollment (`pgmenrol_active` 1→0), `cascade_cancel_graduation_requests` cancels every active GR on that PE. The fee is **non-refundable** by default — the cascade sets `flags.cascade_from_pe_withdrawal = 1` on each GR, which the controller's `on_cancel` reads to skip Sales Invoice cancellation.

Manual cancellation (registrar clicks Cancel on the GR form, no PE withdrawal) cancels unpaid SIs but leaves partial-paid SIs alone — the registrar handles refund decisions explicitly.

### Frontend CTA

`ProgramAudit.vue` renders a Graduation Request card under the eligibility banner. The eligibility banner itself has three states (Eligible / Conditionally Eligible / Not Yet Eligible) so the student can distinguish "I've passed everything" from "I'm enrolled in my last courses but they aren't graded yet".

CTA visibility:

| State | UI |
|---|---|
| `students_can_request_graduation = 0` | hidden |
| Check on, no GR, candidate=0 | hidden |
| Check on, no GR, candidate=1, eligible | "Request Graduation" button + confirm dialog |
| Check on, no GR, candidate=1, conditionally eligible | "Request Graduation" + caveat text ("you must pass the courses you are currently in") |
| GR Awaiting Payment | "Awaiting Payment" + paid_percent + invoice link |
| GR Academic Review or Financial Review | "Under Review" banner with the current state |
| GR Approved | "Approved" banner |

Submission goes through the `create_graduation_request` whitelisted endpoint. Permission: caller is the linked Student (portal flow) OR holds an Academics role (registrar acting on behalf).

The audit page also renders a **Pending Payments** table grouped by payer for the same enrollment — visibility-only on the student side. Most schools require all balances cleared before graduation; this table tells the student where they stand without forcing them to dig through Fees.vue (which only shows invoices addressed to *them*, not other payers like sponsoring churches or scholarship donors).

## Why not a generic "Other Linked Document" fee trigger?

An earlier proposal extended Fee Category with a generic `link_doctype` + `link_doc_status` mechanism (mirroring Graduation Requirement Item) so any doc could become a fee trigger. We rejected it: ADR 012's wildcard hook + dynamic_link pattern is config-driven and already proves the abstraction works for *receiving* status, but invoking *invoicing* on arbitrary docs introduces a much heavier set of concerns (pricing context, payer split, customer group resolution) that the existing per-PE `Payers Fee Category PE` table already solves cleanly. Mirroring the CEI pattern keeps Graduation Request in well-trodden territory and lets the same `pep_event` indirection scale to whatever the next fee-bearing concern is.

## Why two trigger modes (and not just one)?

Different schools genuinely operate differently. A school with strict "no walk if you might fail your last class" policy wants "Passed final courses". A school that wants early registrar prep — print the diploma, line up the ceremony — wants "Enrolled in final courses" so it can see the cohort weeks earlier. Both modes use the same eligibility math; only `in_progress` toggles in or out. One field, two semantics, near-zero implementation cost.

## Why cancel-cascades, not just registrar-handles-it?

A withdrawn enrollment shouldn't leave an active Graduation Request on the registrar's queue — the request is conceptually dead the moment the enrollment is. Auto-cancelling on PE inactivation also gives a clean event for the workflow_state field to land on "Cancelled" (vs. an indeterminate "Awaiting Payment forever"). The non-refundable default reflects what most schools actually do; a per-program refund policy field is a future ADR if a partner needs it.

## Consequences

- New doctype: `Graduation Request` (submittable, workflow-driven, with HTML snapshot fields for graduation requirements + pending payments).
- New module: `seminary/seminary/graduation_candidate.py` (evaluator, idempotent).
- New module: `seminary/seminary/graduation_request_lifecycle.py` (payment / cascade hooks).
- New PE field: `grad_candidate` (read-only, system-managed).
- Two new Program fields: `students_can_request_graduation`, `graduation_request_trigger`.
- New Library field: `blocks_graduation_request` (Check), mirrored to SGR for evaluator efficiency.
- New Sales Invoice custom field: `custom_graduation_request`.
- New endpoint: `get_pe_unpaid_invoices` (used by both the Program Audit page and the Graduation Request desk form).
- New Trigger Fee Events fixture entry: `Graduation Request`.
- New Workflow: `Graduation Request Lifecycle` (six states: Draft, Awaiting Payment, Academic Review, Financial Review, Approved, Cancelled).
- Patches: `add_custom_graduation_request_field`.
- ADR 012 unchanged — Graduation Request is a sibling concept; SGR rows continue to track requirement *satisfaction* independently. The new `blocks_graduation_request` flag is a refinement on Library, not a structural change.
- ADR 016 unchanged — its payment-gated CEI pattern is being reused, not modified.

## Notes

- The candidacy evaluator runs synchronously on every PEC mutation. Cost is one PE load + a handful of `frappe.get_all` calls — measured negligible at single-row scale. Bulk grade imports get a `recompute_for_program(program)` bench helper instead of paying the per-row cost.
- The "Enrolled in final courses" trigger does not project emphasis credit caps (`emphasis.trackcredits` is grade-driven and lags). For an emphasis to count as "all-in-progress" the mandatory courses must be enrolled; the credit-cap subtlety only matters for elective-heavy emphases and can be revisited if it surfaces.
- `Graduation Request` does not stamp the PE as "graduated". That's still a separate registrar action (eventually a workflow on PE itself, not in scope here).
