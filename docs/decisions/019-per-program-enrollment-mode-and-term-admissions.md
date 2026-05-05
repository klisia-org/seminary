# 019 — Per-program Enrollment Mode & Term-scoped Admissions

**Date:** 2026-05-04
**Status:** Accepted

## Context

The seminary app inherited Frappe Education's `Student Admission` doctype: a single per-academic-year container with one institution-wide application window, a child `Student Admission Program` table per eligible program (carrying min/max age, application fee, and applicant naming series), a public `/admissions` web view, a portal menu entry, and the "New Applicant" CTA on each published admissions page. The custom `Student Applicant` was wired to it for naming, age validation, and per-program config.

That model stopped fitting once the app served real seminaries:

- **Higher-ed has no min/max age.** The age validation was dead weight.
- **Application fees are now `Fee Category`-driven.** Putting `application_fee` on a child table duplicated state already modeled by Trigger Fee Events + Program Fees.
- **Enrollment cadence is per-program.** Some programs (e.g. continuing education, devotional courses) accept applicants year-round; others (degree programs) gate on term-scoped windows. A single institution-wide window forced both shapes through the same flow.
- **No general "admissions" landing page wanted.** Each program's own public page is the natural home for "are we accepting applications, and when?" — `/admissions` was a redundant funnel.

## Decision

### Per-program `enrollment_mode` flag, orthogonal to `is_free` and `is_ongoing`

`Program.enrollment_mode` (Select: `Timed` | `Continuous`, default `Timed`, required). This is a third orthogonal Program flag (cf. ADR 015):

- `is_ongoing` — graduation/transcript concerns
- `is_free` — money concerns
- `enrollment_mode` — admissions cadence

Continuous programs bypass Term Admission entirely; the public CTA tags applicants to the current Academic Term. Timed programs honor Term Admission windows.

### `Term Admission` is per-Academic-Term and Submittable

One `Term Admission` per `Academic Term` (unique key). Replaces `Student Admission` as the admissions-window container. Holds:

- `academic_term` (unique Link, drives the doc name via `format:{academic_term}`)
- `admission_start_date`, `admission_end_date`
- `published` (gates whether the public CTAs render)
- `program_details` (child `Term Admission Program`, one row per admissible program)
- `introduction` (optional public-facing copy)

`is_submittable: 1`, per the Submittable-lookup pattern (ADR 015): the doc's `docstatus = 1` is what gates "real" enrollment-window behavior, including the public Apply CTAs. Drafts are scratch space.

The child `Term Admission Program` is intentionally minimal — a single `program` Link. No min/max age (gone), no per-window application_fee (now via Fee Categories), no per-window naming series (now per-Program).

### Program child table pre-populates on insert; manual refresh for additions

`before_insert` populates `program_details` with every Program where `enrollment_mode = "Timed"`. The registrar removes rows for programs not enrolling that term. A "Refresh from Programs" button on the Term Admission form (whitelisted method) appends any newly-created Timed Program not already listed — covering the case where Programs are added between Term Admissions.

This trades a small amount of magic for a much shorter happy-path (registrar opens the form and sees the 90% answer pre-filled).

### Application fees flow through the Trigger Fee Events / Fee Category pipeline

A new seeded Trigger Fee Event `"Application"` joins the existing six (NAY/NAT/Monthly/Program Enrollment/Course Enrollment/Graduation Request). Admins wire it through `Program.pgm_pgmfees` like any other fee event. The seminary's chart of accounts and price-list machinery doesn't need to know "application" is special.

`Student Applicant.on_submit` calls a new `generate_application_invoices(applicant)` in `seminary.seminary.api`. Unlike the NAY/NAT/Monthly generators (which join through `pgm_enroll_payers` — a Program Enrollment doesn't exist for an applicant yet), this generator walks `Program.pgm_pgmfees` directly, resolves the Customer for the applicant (creating one if needed), and uses the Customer Group's `default_price_list` for pricing. Idempotent via `seminary_trigger = APP:<applicant>:<pf_row>`.

Two new fields on `Student Applicant` support this: `customer` (Link, auto-set on first invoice generation) and `customer_group` (Link, defaults to `Individual`). The applicant's customer record carries forward when they're admitted and become a Student.

### Per-program `applicant_naming_series` replaces per-(admission, program) value

The naming series for `Student Applicant` records (e.g. `MDIV-APP-.####.`) moves from `Student Admission Program.applicant_naming_series` to `Program.applicant_naming_series`. The previous level of indirection (per admission cycle) bought no flexibility — naming conventions are per-program, not per-window.

### Public Program web page renders enrollment status, not `/admissions`

`Program.get_context` resolves the program's open windows (Term Admission rows with `docstatus=1`, `published=1`, `admission_end_date >= today`, where the Term's `program_details` references this Program) and the continuous-CTA term (current Academic Term, falling back to next upcoming).

Two web-tab Check fields on Program control rendering, orthogonal to each other and to `enrollment_mode`:

- `display_enrollment_window` — show the open-windows block on the public page (no-op for Continuous).
- `display_cta` — show the Apply CTA. For Timed programs, one CTA per open window (URL passes `program`, `academic_term`, `term_admission`). For Continuous, one CTA passing `program` and the resolved current/upcoming `academic_term`.

`/admissions`, the website_generator on Student Admission, the portal menu entry, and the global-search index entry all go away. Old links to `/admissions` 404 — there is no redirect.

### Migration via `retire_student_admission` patch

A post-model-sync patch nulls the legacy `student_admission` column on existing Student Applicant records (the field is removed from the doctype JSON, but Frappe leaves the column behind), then deletes all Student Admission and Student Admission Program records so the tables drop cleanly when the doctype directories are removed.

## Consequences

**Easier:**

- A Program's enrollment story is fully described by its own row: cadence (Continuous vs Timed), public-display flags, naming series, fee categories. No coordination with an institution-wide admissions cycle.
- Adding/changing application fees is the same shape as every other Trigger Fee Event — admins already know the Program Fees + Fee Category + Item Price flow.
- The public Program page is the single source of truth for "are you accepting applicants?" — no risk of `/admissions` and the Program page disagreeing.
- Term Admission's pre-populated child table makes "open admissions for next term" a small, mostly-automatic action.

**Friction (accepted):**

- Two new Customer-related fields on Student Applicant (`customer`, `customer_group`) and a customer-creation helper. Application fees can't bill without a Customer; deferring this to a separate "admit applicant" workflow would mean no on-submit billing. We accept the small auto-creation cost; the registrar can amend the Customer later.
- Each Term Admission still requires a per-program review (rows to delete or add). The pre-population covers the 90% case but not the "this program is suspended this term" case — that's the explicit row deletion.
- The `Doctrinal Statement.use_in_student_admission` Check field is now orphaned (no consumer code referenced it even before this ADR; it survives as a relic). Cleanup is a follow-up.

**Open / residual:**

- The Continuous CTA falls back to "next upcoming Academic Term" if no term is flagged `iscurrent_acterm=1`. If the calendar is misconfigured (no current and no upcoming term), the CTA is suppressed and a `frappe.log_error` fires for the registrar. We don't surface this to the public visitor; they just see the program page without a CTA.
- Re-application semantics are unchanged: a Student Applicant can submit multiple times for the same Program, and the `APP:` tag dedup prevents duplicate Sales Invoices for the same `(applicant, fee row)` pair. Different fee rows or different programs would generate distinct invoices.

## References

- [`program.json`](../../seminary/seminary/doctype/program/program.json) — `enrollment_mode`, `applicant_naming_series`, `display_enrollment_window`, `display_cta`
- [`program.py`](../../seminary/seminary/doctype/program/program.py) — `get_context`, `_resolve_open_windows`, `_resolve_continuous_term`
- [`templates/program.html`](../../seminary/seminary/doctype/program/templates/program.html) — public page rendering
- [`term_admission/`](../../seminary/seminary/doctype/term_admission/) — new Submittable doctype with pre-populating `before_insert` and `refresh_programs` whitelisted helper
- [`term_admission_program/`](../../seminary/seminary/doctype/term_admission_program/) — single-field child
- [`student_applicant.py`](../../seminary/seminary/doctype/student_applicant/student_applicant.py) — `on_submit` → `generate_application_invoices`; naming from Program; age validation removed
- [`api.py`](../../seminary/seminary/api.py) — `generate_application_invoices`, `_ensure_applicant_customer`
- [`fixtures/trigger_fee_events.json`](../../seminary/fixtures/trigger_fee_events.json) — `Application` event
- [`hooks.py`](../../seminary/hooks.py) — `website_generators`, `/admissions` route, portal menu entry, and global-search index for Student Admission removed; `Term Admission` substituted in global search
- [`patches/retire_student_admission.py`](../../seminary/seminary/patches/retire_student_admission.py) — null legacy FK + delete records
- ADR 015 (Orthogonal Program Flags) — same orthogonality pattern; `enrollment_mode` is the third flag in the family
- ADR 008 (Automated Trigger Billing) — the Trigger Fee Events pipeline application fees plug into
