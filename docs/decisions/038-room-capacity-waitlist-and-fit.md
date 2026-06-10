# 038 — First-class rooms: capacity, waitlist, feature matching & conflict detection

**Date:** 2026-06-09
**Status:** Accepted

## Context

Rooms were passive. A `Course Schedule` (CS) linked to a `Room`, but nothing
enforced capacity, detected double-booking, matched a course's needs to a
room's features, or recorded demand the rooms turned away. Two latent problems
made capacity work impossible to build on:

- **The `enrollments` counter drifted.** It was incremented in one place
  (`copy_data_to_scheduled_course_roster`) and never decremented on withdrawal
  or cancellation, so it crept upward and could not be trusted for seat math.
- **The pipeline was invisible.** `enrollments` and the roster only reflected
  *seated* (Submitted) students. Draft, Awaiting Payment, and would-be
  waitlisted students were not counted anywhere, so demand-vs-supply could not
  be reported.

The seminary had already scaffolded the vocabulary — `Room Feature`,
`Room Existing Feature`, `Course Type`, `Course Type Requirements`, and a
`Course.course_type` link — but none of it was wired to behaviour.

## Decision

Make rooms first-class across capacity, waitlisting, fit, and conflict, with
every check **opt-in by data presence** so a small seminary that fills none of
it sees today's behaviour unchanged.

### Capacity is decoupled from the room

A new `Course Schedule.max_enrollment` is the single source of truth for the
seat cap. It auto-fills from `Room.seating_capacity` when a room is set, but is
overridable and may be cleared (uncapped). This handles virtual sections (no
room), seminars capped below room size, and room changes — none of which a
"read the room's capacity directly" approach could. `seating_capacity` was
converted Data→Int for the arithmetic.

### Seat-holder state semantics

Counts are recomputed from CEI workflow state by one helper
(`waitlist.recount`), never incremented in place:

- `enrollments` = rostered → `Submitted`
- `seats_used` = seat-holders (capacity) → `Submitted` + `Awaiting Payment`
- `registrations` = demand → `Draft` + `Awaiting Payment` + `Submitted` + `Waitlisted`
- `waitlist_count` → `Waitlisted`

`Awaiting Payment` **holds a seat** — a committed-but-unpaid student must not be
oversold against. A section is full when `max_enrollment` is set and
`seats_used >= max_enrollment`.

### Waitlist as CEI states, not a parallel doctype

Two states join the Course Enrollment Lifecycle workflow: `Waitlisted` and the
terminal `Unseated`. A computed `seat_available` flag on the CEI (set in
`validate`, mirroring the existing `is_free` / `require_pay_submit` flags) gates
the Draft transitions: an open seat routes to Submitted/Awaiting Payment as
before; a full section routes to `Waitlisted` (no invoice raised). This reuses
the workflow's existing condition-branching rather than inventing a second
lifecycle. Waitlisted students never get a roster row, so they are naturally
excluded from capacity.

### One promotion choke point

`waitlist.recount_and_promote(cs)` refreshes the caches and, while the section
is **Open for Enrollment** and has an open seat, promotes the head of the queue
(FIFO by creation) — to Awaiting Payment for paid courses (invoice raised at
promotion) or Submitted otherwise — notifying the student **and** the
registrar. It is invoked from every seat-changing event: withdrawal,
cancellation, a capacity/room increase, and a fresh Submitted enrollment.
System-driven promotion uses `db.set_value` and fires the side effects manually
(per ADR 013), since it bypasses `on_update_after_submit`.

### Unseated is the scarcity record

When a section leaves Open for Enrollment, remaining Waitlisted CEIs move to
`Unseated`. A withdrawal reason was rejected — those students were never seated,
so withdrawal vocabulary would muddy withdrawal reports. The Unmet Demand report
counts `Unseated` CEIs per section: the room-scarcity signal.

### Warn on fit, block on conflict

On CS save, when a room is set: missing Course-Type-required features (unioning
the `All` modality rows with the section's modality) raise a **dismissible
warning**; a room smaller than current `seats_used` and a **double-booking**
(same room, overlapping meeting date+time over the `cs_meetinfo` child table)
**block** the save. The room Link picker is ordered best-fit-first via a custom
search (`api.room_search`) with a muted description line (capacity · feature fit
· free/busy) — ordering only, never hiding, since fit is advisory.

Accessibility was folded into the feature vocabulary (a seeded
`Wheelchair Accessible` Room Feature) so it can be *required*; the standalone
`Room.accessible` check could never express a requirement.

## Consequences

- Capacity math is now correct and self-healing (recompute, not increment).
- `seat_available` is computed at validate time, so under concurrency two
  students could momentarily both see the last seat. The promotion engine is the
  authority and re-checks; acceptable at seminary scale.
- Registrar gained permissions on Room, Room Feature, Course Type and on the
  Course Schedule room/capacity fields (permlevel 1).
- New reports: Room Utilization, Waitlisted Sections, Unmet Demand. A room
  change log child table records every reassignment with a reason.
- Manual reordering of the waitlist is out of scope; order is FIFO by arrival.
