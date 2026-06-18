# 056 — Course-gated and emphasis-scoped graduation requirements

**Date:** 2026-06-17
**Status:** Accepted (amended same day — see Amendment)

## Amendment (2026-06-17): single Link, not Table MultiSelect

The original draft (below) proposed storing the course gate and emphasis scope as **`Table
MultiSelect`** fields on the PGRI child row, citing the existing `prerequisite_requirement` as a
shipping precedent. **That precedent was a latent bug.** Frappe forbids *any* table field on a child
doctype: `frappe.model.base_document.TABLE_DOCTYPES_FOR_CHILD_TABLES` is an empty map, and every child
row is forced to use it ([base_document.py](../../../frappe/frappe/model/base_document.py)), so a
`Table MultiSelect` on a child (a "grandchild" table) silently fails to load, append, or save through
the parent. `prerequisite_requirement` never round-tripped through the form.

**Resolution:** all three fields are **single `Link`** fields on PGRI, not multi-selects:
`prerequisite_course → Course`, `applies_to_emphasis → Program Track`, and
`prerequisite_requirement → Graduation Requirement Item` (the broken existing field, fixed here).
To gate on several courses/prerequisites, **chain** requirements; to scope one requirement to several
emphases, **add the row once per emphasis** (snapshot dedups by library item so a student in two of
them gets a single row). The three orphaned child doctypes are removed by patch
`remove_grad_req_multiselect_doctypes`. Read the section bodies below with "single Link" substituted
for "Table MultiSelect" throughout.

## Context

Configuring real programs against the requirement engine surfaced two shapes it cannot express
(see [research note](research/graduation-requirement-configuration-audit.md)):

1. **Course-gating** — a requirement should not activate until the student has *passed* a specific
   course (e.g. *Writing a Thesis* gates the thesis itself).
2. **Emphasis-scoping** — a requirement should apply only to students who declared a given emphasis
   (e.g. a counseling internship for the Counseling emphasis).

The audit overturned the assumptions behind both. Course-gating does **not** need a forbidden
grandchild grid: PGRI (`Program Grad Req Items`, `istable:1`) already carries a `Table MultiSelect`
(`prerequisite_requirement` → `Grad Req Item Prerequisite`), so a flat list of links on a child row
is an established, shipping pattern. And tracks/emphases already exist in full (ADR 002) — they
simply never reach the requirement engine, which differentiates students only by *course* and
*credit*, never by *course identity* or *sub-program*. Both gaps are missing **applicability axes**,
not missing requirement types. This ADR adds both axes; it does not touch the five requirement types
or the three-layer model (ADR 012).

## Decision

### 1. New `Course Passed` activation mode (Gap A)

Add a sixth value to PGRI `activation_mode`: **`Course Passed`**, with a new field
`prerequisite_courses` — a **`Table MultiSelect` → new child doctype `Grad Req Course Prerequisite`**
(single Link field `course → Course`), mirroring `Grad Req Item Prerequisite` one-for-one. `depends_on`
`activation_mode == 'Course Passed'`, shown in the Prerequisites section.

`evaluate_activation()` ([graduation.py:227](../../seminary/seminary/graduation.py#L227)) gains a
branch: the row is active iff **every** listed course has a passing record for this enrollment.
Authoritative signal is **`Program Enrollment Course.status == "Pass"`** — the exact set
`_course_status_sets()` already computes for candidacy
([graduation_candidate.py:161](../../seminary/seminary/graduation_candidate.py#L161)). Like every
activation mode, this is **evaluated at audit time, never snapshotted**, so it must read identically
in the Desk audit and the frontend portal audit. The course list is read live from the (frozen,
never-cancelled) `pgr_item` via `_load_pgr_item()`, exactly as `After Requirement` reads its
prerequisites — so no new SGR field is required.

**A single passing attempt satisfies the gate, permanently — regardless of later or earlier
attempts, and even for repeatable courses.** This is intentional (a pass is a pass) and **must be
documented to end users** in the graduation-requirements module doc.

### 2. Emphasis scope on requirement rows (Gap B, option B3)

Add `applies_to_emphasis` to PGRI — a **`Table MultiSelect` → new child doctype
`Grad Req Emphasis Scope`** (single Link field `program_track → Program Track`, picker filtered
`is_emphasis = 1`). **Empty = applies to all students** (today's behaviour, unchanged). A non-empty
list scopes the row: it materializes only for students who have **declared at least one of the listed
emphases** (`Program Enrollment Emphasis.status in (Active, Completed)`), **excluding `advisory_only`
tracks** — an advisory-only emphasis never makes a scoped requirement applicable.

Snapshot ([graduation.py:74](../../seminary/seminary/graduation.py#L74)) gains the scope filter, and
`_build_sgr_row()` stamps a cheap `emphasis_scoped` Check on the SGR for efficient report filtering
(authoritative scope still lives on the `pgr_item`).

### 3. Partial re-snapshot on emphasis change

Because `emphasis_declaration` may be `Anytime` / `Auto-grant`, emphasis-scoped rows often must
appear *after* enrollment. On any change to the `emphases` child set (desk edit, portal declaration,
or auto-grant), a **partial re-snapshot** runs that touches **only emphasis-scoped PGRI rows**
(`applies_to_emphasis` non-empty): newly-applicable rows are appended; program-flat rows and all
existing progress are left frozen (the catalog-year contract holds for the base requirement set).
This is a new narrow path — *not* the full `resnapshot()` ([graduation.py:185](../../seminary/seminary/graduation.py#L185))
— triggered from the emphasis-change point in `program_enrollment.py` (compare `emphases` to
`_doc_before_save`). It must fire for every route that mutates emphases.

### 4. Dropped-emphasis orphans → a script report, never auto-delete

Dropping an emphasis can leave a scoped SGR row that is already In Progress, Submitted, or Fulfilled
(the student may have *done* the counseling internship, then switched). Deleting it silently would
destroy real progress, so scoped rows are **never auto-removed** on drop. Instead a new query report
**`Orphan Graduation Requirements`** surfaces SGR rows whose scoping emphasis is no longer Active /
Completed, **mirroring `Students At Attendance Risk`**
([report](../../seminary/seminary/report/students_at_attendance_risk/)): a `.py` returning
columns + rows, and a `.js` with `checkboxColumn` + role-gated inner buttons (Registrar / Program
Chair / Seminary Manager / System Manager) that batch-act via whitelisted API methods behind a
`frappe.confirm` — at minimum **Cancel** (remove the orphan row) and **Waive**, leaving **Keep** as
the no-op default. Registrar judgement, not automation, resolves each orphan.

### 5. Freeze emphases once a Graduation Request exists

Rather than reason about a late mandatory emphasis-scoped requirement appearing after a request is
filed, we forbid the move that creates the ambiguity: **emphasis changes are blocked once a
non-cancelled `Graduation Request` exists** for the enrollment (`Graduation Request.program_enrollment`,
`docstatus != 2`). `validate_emphases()`
([program_enrollment.py:241](../../seminary/seminary/doctype/program_enrollment/program_enrollment.py#L241))
throws with a clear message: *delete the graduation request first, then change the emphasis*. This
keeps the requirement set stable from the moment of request and preserves the candidacy/blocking
invariants unchanged.

## Consequences

- **Easier:** "pass X before Y" and "counseling emphasis ⇒ counseling internship" become pure
  configuration; both reuse the in-repo `Table MultiSelect`-on-child pattern, so no Frappe structural
  workarounds. Empty scope keeps every existing policy behaving exactly as before — no migration of
  current data.
- **Harder / new surface:** a second snapshot path (partial, emphasis-only) now coexists with
  `snapshot`/`resnapshot` and must stay consistent with them. The orphan report adds an ongoing
  registrar workflow. Course-gating reads PEC pass-state at every audit render (already cheap; same
  query candidacy uses).
- **End-user docs must change:** the "one pass satisfies forever, even for repeatable courses" rule
  and the "delete the graduation request before changing emphasis" rule both need to be written into
  the graduation-requirements module doc.

## Open questions

- Should `Course Passed` and `After Requirement` be combinable on one row (course *and* prior
  requirement), or remain mutually exclusive as the single-select `activation_mode` implies? Starting
  exclusive; revisit if a real program needs both.
- Orphan report actions beyond Cancel / Waive (e.g. "re-attach to a re-declared emphasis")? Deferred
  until a real case appears.
