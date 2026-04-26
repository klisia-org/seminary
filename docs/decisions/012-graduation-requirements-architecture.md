# 012 — Graduation Requirements Architecture

**Date:** 2026-04-25
**Status:** Accepted

## Context

The existing audit (`get_program_audit` + `ProgramAudit.vue`) tracks credits
and required courses, but graduation in real seminaries also depends on
**non-course evidence**: recommendation letters, ordination steps, doctoral
theses, doctrinal statements, chapel attendance counts, internship hours,
preaching practica. Each seminary defines its own list, and that list grows
over time.

Two constraints made this a non-trivial design problem:

- **Per-school flexibility without a School doctype.** ADR 011 kept Program
  as the per-tenant unit; we did not want to introduce School now. Any new
  requirement a registrar dreams up should be expressible without code.
- **Catalog-year promises.** Seminaries traditionally honor "you graduate
  under the rules in effect when you enrolled." A registrar adding a new
  requirement in 2027 must not retroactively block a student who enrolled
  in 2025.

A handful of complex requirement types (recommendation letters with
external recommenders, theses with multi-round supervisor review) needed
their own doctypes regardless. The architecture had to accommodate both
the data-driven 90% and the bespoke 10% under one roof.

ADR 011 explicitly listed "graduation lifecycle is unmodeled" as an open
question and asked whether the new doctypes belong inside `seminary` or
in a separate `graduation` module. This ADR resolves both.

## Decision

### Three-layer model — library, policy, instance

```
Graduation Requirement Item        ← reusable library
        │ referenced by
        ▼
Program Grad Req Items   ─── child of ───  Program Graduation Requirement   ─── links ───  Program
        │ snapshotted into (at enrollment)
        ▼
Student Graduation Requirement   ─── child of ───  Program Enrollment
        │ optionally fulfilled by
        ▼
Recommendation Letter / Culminating Project / (any DocType with workflow_state)
```

- **Library** ([`Graduation Requirement Item`](../../seminary/seminary/doctype/graduation_requirement_item/graduation_requirement_item.json))
  declares *what kinds of requirements exist*. Three types only:
  `Event Attendance`, `Manual Verification`, `Linked Document`. No
  `Custom` and no `Composite` — both were placeholders without a
  contract; dropping them removes a footgun.
- **Policy** ([`Program Graduation Requirement`](../../seminary/seminary/doctype/program_graduation_requirement/program_graduation_requirement.json)
  + child [`Program Grad Req Items`](../../seminary/seminary/doctype/program_grad_req_items/program_grad_req_items.json))
  binds library items to a Program with effective-dating
  (`active_from`/`active_until`) and per-row activation rules.
- **Instance** ([`Student Graduation Requirement`](../../seminary/seminary/doctype/student_graduation_requirement/student_graduation_requirement.json),
  child table on `Program Enrollment`) is the snapshot the audit reads.

All three doctypes live in the existing `Seminary` module — no new
`graduation` module. Coupling to `Program Enrollment` is too tight to
justify the separation.

### Snapshot at enrollment, frozen forever

`Program Enrollment.before_submit` calls
[`seminary.seminary.graduation.snapshot_graduation_requirements`](../../seminary/seminary/graduation.py),
which resolves the active policy by date intersection and materializes
one SGR row per `pgr_item` (× `quantity_required` for Manual Verification
items). The chosen policy is recorded on a new
`Program Enrollment.graduation_policy` Link field for audit traceability.

A registrar may explicitly call the whitelisted `resnapshot()` to
re-materialize against the current policy, preserving waived rows by
default. **Policy publishes never auto-migrate in-flight enrollments.**
This is the catalog-year contract.

### Activation modes are evaluated, not stored

`Program Grad Req Items.activation_mode` ∈ {`Always Active`,
`After Requirement`, `On Document Status`, `Time Offset`}.
[`evaluate_activation`](../../seminary/seminary/graduation.py) computes
"is this row currently due?" at audit time using the live policy row
plus the enrollment's `expected_graduation_date` (defaulted from program
length + enrollment date, registrar-overridable). Not-yet-active
mandatory rows do **not** block `graduation_eligible`.

### Two-channel evidence for Manual Verification

Each Manual Verification library item carries two independent flags:
**Student-submitted** (with its own label) and **Staff-required** (with
its own label). The student portal exposes an upload control on the
audit page when the student channel is enabled; staff verification on
the SGR row triggers `Fulfilled` regardless of student channel state.

This was a direct user clarification: chapel attendance records are
single Events; doctrinal statements need a student signature *and* staff
verification of identity. One pair of fields couldn't model both.

### Multiplicity via distinct library items, not quantity

The natural seminary expression of "three recommendation letters" is
three distinct library items: *Pastoral Reference*, *Academic Reference*,
*Character Reference* — each with its own instructions. `default_quantity`
exists on the library and `quantity_required` on the policy, but both are
hidden unless `requirement_type == 'Manual Verification'` and the
snapshotter clamps quantity to 1 for the other two types. This keeps the
per-slot context (different instructions for each letter) where students
and registrars expect it.

### Generic linked-doc reflection via wildcard hook

Rather than registering an `on_update_after_submit` hook for every
fulfilling doctype individually, [`hooks.py`](../../hooks.py) registers
the wildcard:

```python
"*": { "on_update_after_submit": "...graduation.reflect_linked_doc_status" }
```

The handler short-circuits cheaply (one cached set lookup) unless
`doc.doctype` appears as a `link_doctype` on some library item. This
means **a new linked-document requirement type — say, an Internship
Report — can be created entirely via Desk without editing `hooks.py` or
deploying code**. The cache is invalidated by the library item's own
`on_update`/`on_trash` hook.

### Two complex linked-doc types built up-front

Two requirement types are too rich for the generic Linked Document path
and got their own complete doctypes:

- **[Recommendation Letter](../../seminary/seminary/doctype/recommendation_letter/recommendation_letter.json)**:
  multi-channel delivery (Portal Form / Email Reply / Manual Upload),
  per-letter token (90-day TTL) for guest-portal access, dedicated
  workflow (Draft → Requested → Awaiting Response → Submitted → Under
  Review → Approved | Rejected | Resend Required). The recommender
  portal lives at `/recommender-form/<rl>?token=...` and is implemented
  via two `allow_guest=True` endpoints in
  [`recommender.py`](../../seminary/recommender.py); the SPA router
  honors `meta.guest` to skip the login redirect for that route.
- **[Culminating Project](../../seminary/seminary/doctype/culminating_project/culminating_project.json)**:
  rounds-based child table
  ([`Culminating Project Submission`](../../seminary/seminary/doctype/culminating_project_submission/culminating_project_submission.json))
  with reviewer decisions and a 9-state workflow ending in
  `Completed | Rejected`.

Both controllers reflect their workflow state onto the bound SGR row's
`status`/`fulfilled_on` via the same pattern, and both can be initiated
by the student from the audit page through whitelisted `start_*`
endpoints (with student-ownership checks).

## Alternatives considered

**Compute live, no snapshot.** Tempting for "one source of truth", but
loses catalog-year semantics, has nowhere to put waivers/notes, and
forces every audit page load to re-walk activation rules and linked-doc
queries. Rejected.

**Quantity as the primary multiplicity model** ("3 Recommendation Letters"
as one library item with `quantity_required = 3`). Rejected as primary —
it loses per-slot context (which letter is the pastor's vs. the
academic's). Kept as a Manual-Verification-only escape hatch for
genuine multi-attendance cases.

**A `Graduation Requirement Template` layer** (library → reusable
template → per-program binder). Useful when a seminary has 8 programs
sharing identical graduation rules. Deferred — can be added later as a
fourth layer without breaking the existing three. ADR amendment, not a
rewrite.

**One doctype per requirement type.** Rejected: doctype explosion, and
defeats the entire "registrars author requirements without code" goal.

**A separate `graduation` module.** Considered (ADR 011 raised the
question). Rejected because every doctype here is tightly coupled to
`Program Enrollment` and `Program`; a module boundary would purchase
nothing but extra import paths.

## Consequences

**Easier:**

- Registrars author the bulk of graduation requirements via Desk. New
  Linked Document targets attach via the wildcard hook with zero `hooks.py`
  edits.
- Catalog-year is enforced by construction. A 2027 policy change
  cannot retroactively fail a 2025 student.
- Waivers are first-class on the SGR row, with `waived_by`/`waived_on`
  audit trail.
- The two complex doctypes (Recommendation Letter, Culminating Project)
  are end-to-end usable, including the external pastor-portal flow.
- `get_program_audit` returns one consolidated `graduation_requirements`
  list; the Vue audit page can render it without per-doctype branching.

**Friction (accepted):**

- The wildcard `doc_events["*"].on_update_after_submit` runs on every
  saved/updated document in the system. Cost is one cached set lookup
  per save; if it ever shows up in profiling, switch to an explicit
  per-doctype registration list.
- `quantity_required > 1` is silently ignored outside Manual Verification.
  A registrar who sets it on Event Attendance gets no warning, just
  one snapshot row. Acceptable; could be enforced in
  `Program Graduation Requirement.validate()` later.
- Each genuinely new complex linked-doc target (e.g., a future
  *Internship Report* with hours tracking) still needs its own doctype
  and workflow — the generic path only handles the common case.

**Open / residual risks:**

- **`Time Offset` with unit "Academic Term" is approximated** as 120
  days per term for due-date computation. A precise walk over
  `Academic Term` records is straightforward to add when registrars
  notice the drift.
- **Prerequisite resolution is virtual.** The `prerequisite_requirement`
  field on `Program Grad Req Items` is `is_virtual: 1` and self-references
  the same child doctype; activation evaluation reads from a transient
  child table. If we ever need to query "what blocks what" across
  enrollments, a stored representation is the next move.
- **No auto re-snapshot mechanism.** When a registrar publishes a new
  policy, in-flight enrollments stay on their old snapshot until a
  human triggers `resnapshot`. Surface a registrar-side dashboard
  showing "N enrollments on a stale policy" if this becomes a coordination
  problem.
- **Email-reply ingestion path** for Recommendation Letter is specified
  but not built. The first delivery method to land is the portal form;
  the email-reply path requires investigating Frappe's `Email Account
  append_to=Recommendation Letter` configuration before deciding whether
  a custom `Communication.after_insert` hook is needed.
- **Student-portal evidence upload** writes to `Home/Attachments` private
  folder via the standard Frappe FileUploader. If files start carrying
  PII at scale, revisit storage isolation per-student.
