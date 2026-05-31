# 028 — Events as first-class (Event Custom Category + attendance fulfilment)

**Date:** 2026-05-30
**Status:** Accepted

## Context

`Graduation Requirement Item` (GRI, the reusable requirements library) linked
directly to a Frappe **Event instance** (`GRI.event`). That is a category error:
a GRI is a *type* applicable across programs and years; an Event is a single
dated occurrence. It was only done to lean on Frappe's native Event. Worse,
**Event Attendance fulfilment was a no-op stub** — nothing read `GRI.event`,
there was no `Event` hook, and the snapshot didn't carry it, so an Event
Attendance requirement sat at `Not Started` until a registrar manually called
`mark_sgr_verified`.

Defenses had the same gap: `Culminating Project Milestone.creates_event` /
`event` existed but the wiring was deferred (ADR 025/027).

## Decision

Model the **type → instance** split and wire a fulfilment engine.

- **New `Event Custom Category`** doctype (the reusable type): `category_name`,
  `description`, `visibility` (Public/Private → `Event.event_type`),
  `per_student`, `instructions`. The GRI now links `event_custom_category`
  (replacing `event`); `event_per_student` is **removed** — per-student is a
  property of the *type*, so it lives on the category.
- **`Event` custom field** `event_custom_category` (fixtures) tags created
  events for discovery/reporting.
- **Service + engine** in `seminary/seminary/events.py`:
  - `create_event_from_category(category, starts_on, …, participants)` builds an
    Event from a category (title, visibility, instructions, participants).
  - `reflect_event_attendance` (hooked on `Event` `on_update`) fulfils the
    **Student Graduation Requirement** rows an attendance Event references
    (participants reference the SGR child row). **Cohort** (`per_student=0`):
    fulfil all on `status == "Completed"`. **Per-student** (`per_student=1`):
    fulfil each participant marked `attending == "Yes"`. Reuses
    `graduation._mark_sgr_fulfilled`; mirrors `reflect_linked_doc_status` with a
    cheap short-circuit. `_build_sgr_row` snapshots `event_custom_category` onto
    the SGR.
- **Three entry points** funnel through that service:
  1. **Per-student** — desk Program Enrollment button *Schedule Required Event*
     → `get_per_student_event_requirements` + `create_requirement_event` (one
     student's SGR as participant).
  2. **Cohort** — `Event Custom Category` list per-row button (shown when
     `per_student=0`) → modal → `get_cohort_candidates` (active PEs with an open
     Event-Attendance SGR of this category; filters: program, graduation
     candidates, days-to-max-graduation) → `create_cohort_event` (all selected
     SGRs as participants).
  3. **CP defense** — `event_custom_category` added to the type-milestone
     template (snapshot to the instance, alongside the retained `creates_event`
     flag). Portal workbench **Schedule Defense** button (advisor only) →
     `create_milestone_event`: participants = student + readers + committee
     (external members referenced by their committee child row), de-duped. Sets
     the milestone's `event`. **Calendar-only** — it carries no SGR participants,
     so the reflector never fulfils anything from a defense; `defended_on` stays
     driven by the Defense milestone sign-off.

## Consequences

- Event Attendance requirements now fulfil **automatically** from attendance —
  the manual `mark_sgr_verified` path remains as an override.
- The deferred `creates_event` wiring (ADR 025/027) is resolved. `creates_event`
  is kept as the "this milestone gets an event" flag; the category supplies
  defaults.
- `GRI.event` / `event_per_student` columns are dropped (schema sync). The link
  was inert, so no data migration; pre-existing SGR snapshots simply lack a
  category until re-snapshotted.
- **Setup step:** seminaries must create their `Event Custom Category` rows
  (e.g. Convocation = cohort, Thesis Defense = per-student) — not seeded, to
  avoid imposing process assumptions.

## Deferred

- Self-service appointment booking (rtCamp `frappe-appointment` fork; forced
  Google Calendar). One-on-ones (exit interviews, etc.) remain staff-created
  per-student events for now.
- Surfacing upcoming required events on the student portal.
