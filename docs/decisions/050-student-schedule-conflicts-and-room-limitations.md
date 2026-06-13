# 050 — Student schedule conflicts (warn-not-block) & known room/scheduling limitations

**Date:** 2026-06-13
**Status:** Accepted

## Context

ADR 038 made rooms first-class and, among other things, stopped a `Room` from
being double-booked: `_validate_room_double_booking()` blocks two sections that
share a room when their `Course Schedule Meeting Dates` (`cs_meetinfo`) rows
collide on date + overlapping time, via `times_overlap()` in `utils.py`.

Nothing equivalent existed for **students**. A student could enroll in two
sections that meet at the same time on the same dates — most relevant for
Presential/Hybrid sections, since Virtual sections carry no fixed meeting time.
This is not always a mistake: a student on a waitlist for a preferred section
often enrolls in a less-desired section meeting at the same time, just to hold a
seat until the waitlist clears (and then drops one). Blocking the second
enrollment would break that legitimate workflow.

Walking the room/scheduling code while designing this also surfaced four
**undocumented design limitations**. They are recorded here so future decisions
account for them; none is fixed in this round (cost outweighs current benefit).

## Decision

### Student schedule conflicts are detected and surfaced, never blocked

Detection reuses the ADR-038 mechanism pivoted from room → student: a single
helper `utils.student_schedule_conflicts(student, course_schedule, exclude_cei)`
joins `cs_meetinfo` on a shared `cs_meetdate` with the same strict time overlap
(back-to-back meetings don't clash; missing times — Virtual — never clash).
Because the join is date-based, sections in different terms cannot collide, so
no separate term filter is needed.

A conflicting enrollment is **anything that occupies the student's calendar**:
the student's other Course Enrollment Individual (CEI) rows that aren't
audit / withdrawn / cancelled and aren't in a `Withdrawn` / `Unseated` state.
That deliberately includes **Draft, Awaiting Payment, Submitted, and
Waitlisted** — a waitlisted hold still counts, because the whole point is to
warn the student they are stacking two sections at the same time.

The conflict is surfaced in three places, all non-blocking:

1. **Student portal picker** (`Enrollment.vue`, fed by
   `get_available_courses_categorized`): each section carries a
   `schedule_conflict` list; the card shows a "Schedule overlap" badge, and
   clicking *Enroll* opens an **"Enroll Anyway / Cancel"** dialog whose message
   notes the registrar may later cancel one of the two enrollments.
2. **Desk CEI form** (`course_enrollment_individual.js`): an async `validate`
   gate calls `check_schedule_conflicts` and, on a hit, shows a
   **"Proceed Anyway / Cancel"** dialog; Cancel sets `frappe.validated = false`
   to abort the save. A lightweight server-side `_warn_schedule_conflict()` in
   `validate()` remains as a non-interactive `msgprint` safety net for
   API/registrar-script paths that bypass the form. **Never `frappe.throw`.**
3. **Registrar worksheet** — a new Script Report **"Student Schedule
   Conflicts"** (Registrar / Program Chair / Seminary Manager / System Manager).
   One row per enrolled side of a clash so the registrar can check the specific
   enrollment to drop; an **Alert** flag is raised whenever either side of the
   pair is already `Submitted` (rostered), the case worth prioritising. Inline
   *Resolve Selected* dispatches to `resolve_schedule_conflict`, which picks the
   safe path by state: a Draft is deleted, an unpaid `Awaiting Payment` seat is
   released (`cancel_unpaid_enrollment`, freeing the seat + promoting the
   waitlist), and a Submitted / Waitlisted / paid enrollment is routed to a
   prefilled **Withdrawal Request** (it carries financial/grade weight, so it
   keeps the audit trail rather than being silently dropped).

### Known room/scheduling limitations (accepted, deferred)

> **Update (2026-06-13):** all four limitations below were subsequently
> implemented — see **[ADR 051](051-per-meeting-room-virtual-and-attendance.md)**
> (per-meeting room override, per-meeting virtual meetings, time enforcement when
> a room is set, and per-meeting attendance).

Documented now, deliberately **not** built this round:

1. **No per-meeting-date room override.** `Course Schedule` has a single `room`
   link; `cs_meetinfo` has no room field. So a Hybrid course that meets in
   different rooms across the term, or two instructors alternating the "good"
   room by weekday, cannot be modelled. *Deferred:* needs a room column on
   `cs_meetinfo` plus reworking room double-booking and capacity to read
   per-meeting rooms.
2. **No virtual meeting on the calendar per meeting date.** `web_meeting` is a
   single course-level URL; `cs_meetinfo` has no per-meeting link/flag, so a
   Hybrid section cannot mark "this Thursday is online" or carry per-meeting
   links. *Deferred.*
3. **`from_time`/`to_time` not enforced when a Room is set.** They are only
   conditionally mandatory by modality, so a roomed Presential/Hybrid section
   can be saved with no times — which silently opts it out of both room and
   student conflict detection (both require times). *Deferred but cheap;* a
   targeted follow-up could require times whenever `room` is set.
4. **Multiple meetings per day are manual and attendance is date-keyed.**
   `cs_meetinfo` allows several rows on one date, but `Student Attendance` is
   unique per (student, course, date), so it cannot distinguish which of two
   same-day meetings a student attended; self check-in resolves to the
   currently-open window only. *Deferred.*

## Consequences

- Detection is one shared helper, used by the form, the portal API, and the
  report — a single overlap definition, consistent with room double-booking.
- Enrollment behaviour is unchanged for students with no clash; double-booking
  stays possible by design, now visible to the student at enroll time and to the
  registrar as an actionable worklist.
- The four limitations are explicit, so later scheduling work can reopen any of
  them deliberately rather than rediscovering them. Limitation 3 in particular
  is a known gap that weakens both conflict checks when times are omitted.
