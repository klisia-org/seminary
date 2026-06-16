# 054 — Internships: structured placements, requirements, and hours

**Date:** 2026-06-16
**Status:** Accepted — staged; Stage A (Desk core) the initial scope

## Context

[ADR 053](053-partner-organization-subsystem.md) stood up the Partner Organization subsystem and shipped
its Phase 1 job board + ATS (`Partner Job Opening` / `Partner Job Application`). It listed **internships**
as a roadmap feature but, in §7, deliberately drew a boundary: recruiting *postings* live in the Partner
subsystem while internship *hours* "remain a graduation-requirement concern, deliberately unmodeled
([ADR 012](012-graduation-requirements-architecture.md)). The two never link."

The seminary now wants the opposite: a **structured internship workflow** that explicitly links a posting,
a placement, tracked hours, multi-party deliverables, and graduation. This ADR therefore **revises ADR 053
§7** — internships become a first-class, hours-aware subsystem rather than a `posting_type` on the job
board. The need blends three patterns the codebase already owns:

- **Job board** (ADR 053): org-posted positions, an apply pipeline, an org contact/supervisor, the Partner
  portal, and row-scoped permissions.
- **Culminating Project** (ADR [024](024-culminating-projects-and-policy-versioning.md)/
  [025](025-culminating-project-milestones.md)): a *type* drives a *template* that snapshots per-instance
  requirements with computed due dates (`date_rules.resolve`) and multi-party submission + sign-off.
- **Graduation requirements / course enrollment** (ADR 012/[026](026-graduation-requirement-choices.md)):
  a fulfillment document reflects its status back to a `Student Graduation Requirement` (SGR), and optional
  course-backing yields credit, billing, and a transcript grade.

The target flow: an org posts an **Internship Position** tied to an **Internship Type**; an eligible
student (one whose active Program Enrollment has an open graduation requirement of that type) applies; the
org **auto-accepts or evaluates**; accepted students get one or more **placements**, each with a site
supervisor; the type's **requirement template** instantiates tracked deliverables with due dates; **hours**
are logged under one of three tracking modes; the org supervisor and the student each submit a structured
**evaluation/feedback**; and completion reflects back to graduation (and to a transcript grade when the
type is course-backed).

## Decision

### 1. A dedicated `Internship Position`, not a `posting_type` on the job board

Internships carry hours, multi-site placements, supervisors, course-backing, and a template — far more than
a job posting. We model a distinct **`Internship Position`** (mirroring `Partner Job Opening`'s
org/location/publish shape) rather than overloading `Partner Job Opening` with a `posting_type`. The
position adds an `acceptance_mode` (`Auto-accept on submission` | `Evaluate applications`), a per-week
**commitment** (`min_hours_per_week`, `flexible_dates` + optional `preferred_start`/`preferred_end`), and a
**weekly schedule** (`flexible_schedule` + an `Internship Position Schedule` child of `day_of_week` /
`start_time` / `end_time`, plus free-text `schedule_notes`).

### 2. The whole subsystem lives in the **Partner** module, reusing Seminary engines via cross-module links

All new doctypes are created under `seminary/partner/doctype/...`, keeping the internship subsystem
cohesive and org-coupled exactly as ADR 053 framed it. Academic concerns are reused by **linking out** (the
established pattern — `Partner Job Application` already links the Seminary-owned `Person`):
`Internship Type.course → Course`, `Internship Application.program_requirement → Student Graduation
Requirement`, `Internship Application.faculty_advisor → Instructor`, the shared
`seminary/seminary/date_rules.py::resolve`, and the graduation linked-doc reflection in `graduation.py`.

### 3. Supervisors link `Person`, never `Partner Contact`

`Partner Contact` is a **child table**, so a Frappe `Link` cannot target it (ADR 053 §1/§4 hit this with
`reviewer`). Every supervisor reference — `Internship Position.default_site_supervisor`,
`Internship Placement.site_supervisor`, `Internship Supervisor Evaluation.site_supervisor` — therefore
links **`Person`** (the human behind the contact), so comms/consent (ADR 043) keep working for free.

### 4. A type drives a template; instances snapshot it (the Culminating-Project idiom)

**`Internship Type`** (non-submittable, seeded via the install hook, never fixtures — fixtures clobber desk
edits) carries `total_hours_required`, `allow_multi_site` + `max_sites`, an `hours_tracking` mode, the
optional `course`, the `evaluation_model`, the `graduation_requirement_item` map, and the faculty pool
(§7). **`Internship Requirement Template`** rows (one standalone doctype, filtered by `internship_type`)
declare each deliverable: a `scope` (`Application` once-per-application, or `Placement` per-site), a due
rule (`due_anchor` / `due_offset_value` / `due_offset_unit`, resolved by `date_rules.resolve` with no
resolver change — only new anchor keys `Application Date` / `Placement Start` / `Placement End` /
`Previous Requirement`), and **three party sets** (student / seminary / partner), each declaring whether
that party submits, with what `submission_type`, under what label and instructions, and whether that party
signs it complete.

On Application → `Active`, a `snapshot_requirements()` (mirroring
`culminating_project.snapshot_milestones`) instantiates the `scope=Application` templates onto the
application; on Placement creation it instantiates the `scope=Placement` templates per site. The runtime
**`Internship Requirement`** instance is modeled on `Student Graduation Requirement`'s multi-evidence +
verify pattern (a `status` Select, per-party submission value + label snapshot, and per-party
`*_signoff` / `*_signed_by` / `*_signed_on`) rather than `docstatus`, so post-snapshot edits and
supervisor confirmations keep working.

A template may carry an optional **`submit_template`** attachment — a blank form (e.g. a site-evaluation
PDF) that a party downloads, fills, and re-uploads as their submission; it is snapshotted read-only onto
the instance. A *structured, fillable-form* doctype (a digital form builder rather than a static file) is
**deferred** to a later phase.

### 5. Evaluation and credit are conditional on the type's `course`

`evaluation_model` is a three-option Select — `Inherited from course` | `Pass/Fail` | `Graded` — defaulting
to `Inherited from course`, which `validate` requires a `course` (and the other two forbid one), so staff
*see why* grading is fixed instead of a field silently hiding. When `course` is set, the type is
**course-backed**: Application → `Active` creates a `Course Enrollment Individual` (the Culminating Project
idiom), the Program Enrollment Course row is the grade source of truth, and `final_outcome` is ignored.
When `course` is blank, the faculty advisor records the `final_outcome` (Pass/Fail or a grade) on the
application directly.

### 6. Eligibility is gated by an open graduation requirement; completion reflects back

`Internship Type.graduation_requirement_item` maps a type to a `Graduation Requirement Item`. A student may
apply only when their active Program Enrollment carries an open (`Not Started`/`In Progress`) SGR for that
type; `Internship Application.validate` rejects otherwise. The internship's status reflects back onto that
SGR row in-controller (it is a status-Select doc, not a submittable one, so the generic
`reflect_linked_doc_status` hook does not apply) — `Completed` ⇒ `Fulfilled`, and rejection/withdrawal
release the row back to `Not Started` so the student can apply elsewhere.

**Curated `Allowed Graduation Document` picker.** Configuring a "Linked Document" graduation requirement
previously meant typing a raw `link_doctype` (a `Link` to *every* DocType in the system) and hand-entering
the fulfilling status — confusing and error-prone for staff. We add an **`Allowed Graduation Document`**
lookup (`document_type`, friendly `label`, `fulfilling_status`, `is_active`, read-only `built_in`),
**seeded** with the built-ins (Culminating Project → Completed, Recommendation Letter → Approved,
Internship Application → Completed) and **extensible by advanced users**. `Graduation Requirement Item`
gains an `allowed_document` picker that derives the now-read-only `link_doctype`; `graduation.py`'s
`fulfilling_status()` reads the lookup (falling back to the built-in dict), so the fulfilling status flows
automatically instead of being typed per policy row. A backfill patch points existing linked-document
items at the lookup. This sharpens an ADR 012 rough edge surfaced by the internship work.

### 7. Round-robin faculty assignment, opt-in per type

`Internship Type.auto_assign_faculty` (Check) plus an **`Internship Type Advisor Slot`** child
(`instructor`, `max_students`, read-only `current_students`) form an advisor pool. On Application →
`Accepted`, when `faculty_advisor` is blank and the type opts in, the controller picks the slot with the
most remaining capacity, sets `faculty_advisor`, and increments `current_students` (decremented on
`Withdrawn`/release). A manually entered advisor always wins.

### 8. One hours doctype, three modes; a Desk-proxy for back-office entry

**`Internship Hours Log`** is a non-submittable per-day row (the `Student Attendance`/`Chapel Attendance`
pattern): `internship_placement`, `log_date`, `hours`, `description`, `supervisor_verified` +
`verified_by`/`verified_on`. The type's `hours_tracking` mode governs **when hours count toward the total**:
`Portal — daily log` counts immediately; `… with supervisor confirmation` counts only when
`supervisor_verified`; `Submittable log` counts once the designated **hours-log requirement** is signed
complete. That designated requirement is marked by `Internship Requirement Template.is_hour_log`, and a
**config QA** in `Internship Type.validate` requires exactly such a template to exist when (and only when)
`hours_tracking = Submittable log`. Hours roll up to `Internship Placement.hours_logged` and
`Internship Application.total_hours_logged`.

Because Stage A ships Desk-only (no portals yet), back-office entry would otherwise force the registrar to
play every party. A `internship_staff_proxy` flag on **`Seminary Settings`** lets staff fill and sign any
party's submission directly in Desk; the sign-off still records *who* (the acting staff user), it just
skips the portal round-trip. This also covers legitimate back-office cases after portals exist.

### 9. Org-supervisor and student evaluations are structured, multi-party documents

**`Internship Supervisor Evaluation`** (submittable, like `Culminating Project Milestone Signoff`) carries
`overall_readiness` / `theological_integration` / `relational_skills` / `initiative` on a shared
`Exceeds | Meets | Developing | Below | Not Observed` scale, plus `comments` and `endorses_ministry`.
**`Student Internship Feedback`** carries an `overall_rating` (Rating), `supervision_quality` /
`spiritual_formation_value` / `workload_appropriateness` Selects, `would_recommend`, and the
`highlights` / `concerns` / `suggestions_for_seminary` editors. Both link the placement.

### Phasing

- **Stage A (this ADR's initial scope) — Desk core.** All config + runtime doctypes and their controllers
  (snapshot, due dates, hours rollup, SGR reflection, optional course-backing, eligibility validation,
  one-application-per-position, faculty round-robin, the `internship_staff_proxy` Desk path); the
  `Seminary Settings` fields; and an install-hook seeder for a starter type + templates (e.g. Worship vs
  Chaplaincy). Fully operable in Desk, no frontend.
- **Stage B — Permissions + Partner portal.** Row-scoping hooks in `seminary/partner/permissions.py`
  (registered like `opening_query`/`application_query`), plus Partner portal pages + an
  `internship_portal.py` API: post/edit positions (unpublished pending staff approval), run the
  acceptance pipeline (auto-accept vs evaluate), assign a `site_supervisor` per placement, verify hours,
  and submit the supervisor evaluation.
- **Stage C — Student portal.** Eligible-only browse, prayerful apply, and a "My Internships" surface
  (placements, requirement checklist, mode-aware hours logging, student feedback) via an
  `internship_api.py`, mirroring `Jobs`/`JobOpening`/`JobApplication`.
- **Stage D — Polish.** Hours/placement roster reports, communication triggers
  ([ADR 044](044-communication-triggers-and-desk-surfaces.md)), multi-site approval refinements, and a
  Desk workbench akin to [ADR 027](027-culminating-project-workbench.md).

## Consequences

Easier: the subsystem reuses four proven engines (job-board posting/permission shape, Culminating-Project
template-snapshot + `date_rules`, graduation linked-doc reflection, optional course-backing) rather than
inventing any of them; it ships Desk-first and operably (the staff-proxy flag removes the portal
prerequisite); and evaluation/credit follow one conditional (`course` set or not) instead of a matrix.
Harder: this revises ADR 053 §7's "postings and hours never link" stance — the two now link through
`Internship Application`, which is the intended change. A type that is both course-backed *and*
graduation-gating reflects in two places (the Program Enrollment Course grade and the SGR status); the
controllers must keep those consistent. The single `Internship Hours Log` doctype carries three behavioural
modes via `hours_tracking` rather than three doctypes — a deliberate simplification whose "Submittable log"
mode is realized through the `is_hour_log` requirement sign-off, not a per-row `docstatus`.

## Open questions

- **Multi-site hours allocation.** When `allow_multi_site` splits `total_hours_required` across placements,
  is `hours_allocated` per placement registrar-set, supervisor-proposed, or evenly auto-split? Stage A
  leaves it a manual field; revisit with the portal in Stage B.
- **Evaluation as a graduation gate.** Whether `endorses_ministry = 0` or a below-threshold supervisor
  evaluation should *block* completion (vs. being advisory) is deferred until faculty weigh in — Stage A
  treats both evaluations as required-to-submit but not pass/fail-determinative.
