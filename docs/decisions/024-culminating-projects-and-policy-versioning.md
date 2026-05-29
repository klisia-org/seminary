# 024 — Culminating Projects as Academic+Financial Records, and Graduation-Policy Versioning

**Date:** 2026-05-29
**Status:** Accepted

## Context

Two gaps surfaced in the graduation machinery from ADR 012.

**1. Graduation policies could not be versioned.** `Program Graduation
Requirement` (PGR) is submittable so a policy is traceable and snapshot-bound
to enrollments (ADR 012). The original design retired a policy by *cancelling*
it (`on_cancel` cleared `active` and stamped `active_until`). But cancellation
never worked: `Program Enrollment.graduation_policy` is a submitted Link to PGR,
and Frappe's `check_no_back_links_exist` runs *before* `on_cancel`. With PE →
CEI → Sales Invoice cascading off that link, Frappe demanded the registrar
delete every enrollment, course enrollment and invoice first. The retirement
code was unreachable.

**2. Culminating projects were inert.** The `Culminating Project` doctype
tracked a thesis through advisor review and auto-fulfilled a graduation
requirement, but had no connection to credits, a grade, GPA, the transcript, or
billing. Real seminaries need a thesis (or summative paper, doctrinal
statement, …) to (i) charge a fee, (ii) carry credits, (iii) earn a grade that
counts in GPA and prints on the transcript. Different options carry different
course codes, and registrars frequently grant a thesis *extension* — another
term with an extra fee, but no new course code, grade, or transcript line.

## Decision

### Versioning by workflow, never by cancellation

PGR gains a workflow, **Program Graduation Requirement Versioning**:
`Draft → Active → Superseded`, all on one document that stays at `docstatus 1`
for its whole life. The `Change Version` transition (`Active → Superseded`):

1. retires the policy in place — `active = 0`, `active_until = today` — without
   ever cancelling it, so back-links from submitted enrollments stay valid; and
2. spawns a **Draft** clone (`supersedes` set on the new doc, `superseded_by`
   set on the old) for the registrar to edit and submit.

`active` is now **system-derived** from the workflow state (Active ⇒ 1, else 0),
not hand-toggled — drafts and superseded versions are inactive, so they never
collide in `_validate_no_active_overlap` or get handed out by `resolve_policy`.
`resolve_policy` now filters `docstatus = 1` (not `!= 2`) so a Draft successor
is never resolvable.

**Trade-off — brief no-active window.** Between superseding the old policy and
submitting the new one, the program has no active policy and `resolve_policy`
returns `None` for enrollments created in that gap. Accepted: the registrar
completes the new version promptly, and re-snapshotting (`graduation.resnapshot`)
can repair any enrollment caught in the window.

Snapshot semantics from ADR 012 are unchanged: enrollments keep resolving their
`graduation_policy` by name regardless of the policy's lifecycle state.

### Thesis = a real Course → Course Schedule → CEI (reuse, don't rebuild)

Rather than bolt credit/grade/fee fields onto `Culminating Project`, a project
is backed by a normal course enrollment:

- A new lookup, **Culminating Project Type** (Thesis, Summative Paper,
  Doctrinal Statement, …), maps each option to a **backing Course**. The Course
  (and its Course Schedule) is the single source of the credits, grading scale,
  and fees — there is deliberately **no** grading-scale or fee-category override
  on the type. `Culminating Project.project_type` changed from a hardcoded
  Select to a Link to this lookup; the shipped fixtures are named to match the
  old Select values so existing rows resolve with no data migration.
- `Culminating Project.course_enrollment` links the **Course Enrollment
  Individual (CEI)** created by the `Enroll in Project Course` action. From
  there everything is reused: CEI `on_submit` bills the fee; credits come from
  `Program Course`; the grade lands on the `Program Enrollment Course` row and
  flows to GPA (`gpa.py`) and the transcript. The PEC row is the grade's source
  of truth; the project's `final_grade` is display-only.

### Extensions = billing + tracking only

A new submittable **Culminating Project Extension** records a registrar-granted
extra term (`academic_term`). The fee is **fully configuration-driven**: there
is no fee-category or quantity field on the extension — on submit it bills
whatever Fee Category carries the `Culminating Project Extension` trigger, split
through the enrollment's `Payers Fee Category PE` rows keyed to that event. It
**creates no Program Enrollment Course row** — extensions never touch credits,
grade, GPA, or transcript. The doctype's list view is the registrar's roster of
who is extending.

### Shared billing helper

`seminary/seminary/billing.py` owns the Sales-Invoice construction step
(`build_and_create_invoice`). `CEI.get_inv_data_ce` was refactored to call it
(keeping its own payer-resolution SQL and credit/audit qty logic), and the
extension uses `create_extension_invoices`, which resolves payers via the same
`Payers Fee Category PE` split keyed to a new **Culminating Project Extension**
Trigger Fee Event (a flat charge of the configured fee per payer share). Incidental fix: each invoice now computes its cost center
per-payer, so a scholarship payer no longer leaks the scholarship cost center
onto later non-scholarship invoices in the same run.

## Consequences

- Registrars version policies via the `Change Version` button; cancellation is
  no longer part of the lifecycle (`on_cancel` removed). A backfill patch sets
  `workflow_state` on existing PGRs (active ⇒ Active, inactive/cancelled ⇒
  Superseded, draft ⇒ Draft).
- Theses earn fees/credits/grades/transcript lines through the exact same paths
  as ordinary courses — no parallel academic machinery to keep in sync.
- Extension billing depends on the seminary configuring payer rows for the
  `Culminating Project Extension` event; absent that, submission throws with a
  clear message rather than silently billing nothing.
- A dedicated student/advisor Vue page is deferred (see plan); the desk forms
  and `ProgramAudit.vue` cover the interim.

## Status of follow-ups

- Vue workbench for students (track/submit) and advisors (review/grade).
- Optional: link extension Sales Invoices back via a custom field (today they
  are tracked by name on the extension and by `custom_student` on the invoice).
