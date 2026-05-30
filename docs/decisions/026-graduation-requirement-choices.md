# 026 — Graduation Requirement Choices: Project-Type allow-list + "Choose Option" umbrella

**Date:** 2026-05-29
**Status:** Accepted

## Context

Two real graduation-requirement patterns weren't modelled (ADR 012 snapshots one
Student Graduation Requirement [SGR] row per policy item, and a Culminating
Project was started with a free-text `project_type`):

1. **A requirement fulfillable by one of several Culminating Project Types** —
   e.g. an MDiv "Culminating Project" allows *Thesis or Summative Paper*.
2. **An umbrella over several different GRIs** ("Choose Option") — the student
   picks which whole requirement to satisfy.

Crucially the choice is decided **before and independently of** the Culminating
Project document (via a course, interview, etc.), so it must live on the SGR.

## Decision

**Two configuration mechanisms on `Graduation Requirement Item` (GRI):**
- `culm_proj_types` (child → `Grad Req Item Culm Proj Type`): the allowed
  Culminating Project Types, **required** when `requirement_type='Linked Document'`
  and `link_doctype='Culminating Project'` (`mandatory_depends_on`).
- `requirement_type='Choose Option'` + `grad_req_option` (child → sub-GRIs): an
  umbrella. `student_choice` decides whether the student picks (portal) or the
  registrar assigns.

**The choice lives on the SGR**, in two explicit Link fields (chosen
representation): `chosen_project_type` (→ Culminating Project Type) and
`chosen_option` (→ GRI), plus `student_choice`, `choice_pending`, and
`linked_doc_status` (snapshot of the fulfilling status).

**Spawn a dedicated row (not morph).** Snapshot creates one SGR row. A "Choose
Option" umbrella starts `choice_pending`; choosing a sub-GRI **spawns a new SGR
row** carrying that option's full behavior (`requirement_type`, `link_doctype`,
`linked_doc_status`, and any nested project-type choice) and links it both ways
(`umbrella.spawned_sgr` ↔ `spawned.parent_choice`). The umbrella stays a
selector and **mirrors the spawned row's status**, so it stops blocking once the
chosen requirement is fulfilled. Changing the choice **replaces** the spawned
row (the desk prompts before deleting it). A CP option with one allowed type
auto-selects on the spawned row; with several it stays `choice_pending` there.

Spawn (rather than the originally-planned morph) because different options have
genuinely different behaviors — internship (Manual Verification) vs elder's
letter (Recommendation Letter) vs thesis (Culminating Project) — which a
dedicated row expresses cleanly, keeps changeable, and tracks via the link. The
existing engine (`start_culminating_project`, evidence, `reflect_linked_doc_status`)
operates on the spawned row unchanged.

**One resolution path.** `graduation.apply_sgr_choices(pe)` runs from
`ProgramEnrollment.before_update_after_submit`, so desk grid edits and the
whitelisted portal actions (`choose_requirement_option`, `choose_project_type`,
permission-gated by `student_choice`) funnel through the same morph.
`start_culminating_project` now reads/validates `chosen_project_type` instead of
taking a free param. `reflect_linked_doc_status` prefers the SGR's
`linked_doc_status` (set on morph from a `{Culminating Project: Completed,
Recommendation Letter: Approved}` convention map) over the policy row's value, so
umbrella-chosen linked docs fulfil correctly.

## Consequences

- **Frappe gotcha (load-bearing):** on an `update_after_submit` save, *changing*
  child-table fields that aren't themselves `allow_on_submit` is silently
  dropped (the whole row update is discarded, no error). The choice/status
  fields the engine writes post-submit are `allow_on_submit` on SGR. (*Inserting*
  a new child row — the spawn — writes all its fields fine; the gotcha only bites
  edits to existing rows. Parent fields, by contrast, *throw* —
  `UpdateAfterSubmitError`, ADR 025.) `apply_sgr_choices` runs in
  `before_update_after_submit` because `validate()` doesn't run after submit.
- The umbrella mirrors its spawned row's status, so an unchosen mandatory
  umbrella is "Not Started" (blocks) and a fulfilled one is "Fulfilled" (clears)
  via the existing `all_mandatory_satisfied` — no special branch. The spawned
  row blocks on its own status until fulfilled.
- `spawned_sgr` is backlinked in `ProgramEnrollment.on_update_after_submit`
  (child names are only assigned once the parent has saved); `parent_choice`
  (set at spawn time) is the authoritative link used by the engine and the desk
  change-prompt.
- `get_program_audit` exposes `student_choice` / `choice_pending` /
  `chosen_*` and a pending-only `options` array (value+label) so the portal can
  render the Choose modal without extra round-trips.
- The choice is fully decoupled from the Culminating Project doc: the type/option
  can be set by a registrar (after a course/interview) long before the project
  exists.
- **Desk (belt + suspenders):** the Program Enrollment client script
  (`program_enrollment.js`) scopes the `chosen_option` / `chosen_project_type`
  grid dropdowns per row via `set_query` → link-query methods
  (`get_choose_option_items`, `get_allowed_culm_types`), and `apply_sgr_choices`
  re-validates the chosen value against the allow-list on every save — so a
  direct grid edit to an out-of-list value is rejected, not just hidden.

## Follow-ups
- **Frontend (specified, deferred):** in `ProgramAudit.vue`, when
  `student_choice && choice_pending`, a **"Choose"** action opens a modal —
  `Choose Option` → list `options` (sub-GRIs) → `choose_requirement_option`;
  Culminating Project → list `options` (allowed types) → `choose_project_type`.
  After the choice the existing Start Project / evidence actions appear. Build
  with the deferred milestone workbench (ADR 025).
