# 051 — Per-meeting room, virtual meetings, time enforcement & per-meeting attendance

**Date:** 2026-06-13
**Status:** Accepted

## Context

ADR 050 recorded four room/scheduling limitations as deferred. They shared one root: scheduling was
modeled at the **course-section** level (`Course Schedule.room`, `.web_meeting`,
`.from_time/.to_time`) while real classes vary per **meeting** — the `Course Schedule Meeting Dates`
(`cs_meetinfo`) child rows. This ADR pushes room, online-meeting, and attendance down to the meeting
row, with fallback to the section value.

## Decision

### Shared foundation — meeting-level fields

`Course Schedule Meeting Dates` gains `cs_room` (Link → Room), `cs_online` (Check), and
`cs_web_meeting` (Data). `Student Attendance` gains `meeting` (Link → Course Schedule Meeting Dates).
The fallback rule lives in one place — `CourseSchedule._effective_room(row)` = `row.cs_room or
self.room`, and `None` when the meeting is online — reused by every validation, the calendar, and the
course-details API.

### #1 Per-meeting room override

A meeting may set its own `cs_room`; blank inherits the section room. Room **double-booking**
(`_validate_room_double_booking`) now compares **effective rooms**: it collects this section's
`(date, effective_room)` pairs and matches them against other sections' meetings on
`COALESCE(cs_room, section room)`, excluding online meetings, using the ADR-038 `times_overlap`
predicate. The room-picker "busy" hint (`api._rooms_busy_for_cs`) uses the same effective room. The
grid room picker reuses `api.room_search` (`set_query("cs_room", "cs_meetinfo", …)`).

**Capacity is asymmetric by design:** the *section* room keeps its hard undersize block, but
per-meeting override rooms are **informational only** (`msgprint`, never `throw`) — an override room
smaller than enrollment warns the registrar and never blocks a save or unseats anyone. Missing-feature
warnings now cover every effective room.

### #2 Per-meeting virtual meeting

`cs_online` marks a meeting online (no room; skipped by room conflict); `cs_web_meeting` is its join
link (falls back to the section `web_meeting`). The iCal export (`calendar.py`) sets each event's
location to the effective room — or "Online" / the link — and adds the join link to the description.
The portal calendar (`get_course_details` → `CourseCalendar.vue`) shows each meeting's room and a
"Join Online" link.

### #3 Times enforced when a room is in play

A section with a room but no `from_time`/`to_time`, or any meeting with an effective room but no
window, is now blocked at validate — omitting times silently opted a section out of **both** room and
student (ADR 050) conflict detection. Per-meeting `from > to` is also rejected.

### #4 Per-meeting attendance

`Student Attendance` is keyed to the **specific meeting**, not the date — a section that meets twice
in a day is two classes, and the old `(student, course_schedule, date)` key collapsed both into one
record (a real bug; both meetings already showed to instructors). `make_attendance_records` /
`mark_attendance` / `course_check_in` thread the meeting row name; existence checks match on `meeting`
(falling back to the date for un-backfilled legacy rows), and the `attendance` flag is set on the
specific meeting row. The instructor page, the course-card self check-in, and the QR-landing fallback
all key on the meeting and show the time so same-day meetings are distinct. Patch
`backfill_student_attendance_meeting` links existing rows (earliest meeting on multi-meeting dates).

This **aligns** — does not change — the absence policy: `attendance._counts` already counts attendance
rows while `_cs_meta.total` counts scheduled meetings (`cs_meetinfo` rows), which were mismatched under
date-keying; per-meeting rows make them consistent.

## Consequences

- Room, online link, and attendance are per-meeting, falling back to section values, so a small
  seminary that fills none of the new fields sees unchanged behaviour.
- The same `times_overlap` mechanism now backs section rooms, per-meeting rooms, and student conflicts
  (ADRs 038/050/051).
- The backfill patch must run (it does on `migrate`) before per-meeting marking, or a re-mark of a
  legacy date-keyed row would create a duplicate.

## Deliberately out of scope

- Room/section reports (Room Utilization, Waitlisted Sections, Unmet Demand) still read the
  section-level `room`; per-meeting report breakdowns are a later refinement.
- The section-level "Change Room" dialog + `Course Schedule Room Change` audit log stay
  section-scoped; per-meeting overrides are edited inline on the grid (a note in the dialog explains
  this) and are not recorded in that log.
- `ensure_meeting_checkin_code` still generates the code against the open/first meeting on a date;
  per-meeting codes for same-day meetings can follow if needed.
