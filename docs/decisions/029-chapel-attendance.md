# 029 — Chapel attendance (count-based requirement + self check-in)

**Date:** 2026-05-31
**Status:** Accepted

## Context

ADR 028 made Events first-class: an `Event Custom Category` (type) spawns Frappe
`Event` instances and a fulfilment engine marks a **Student Graduation
Requirement** (SGR) row fulfilled when a *specific* event is attended/completed.
That model is single-occurrence and participant-listed.

Chapel does not fit it. Chapel is **recurring** (many services per term),
**public** (all students and instructors are invited, open to the public — we do
not pre-list participants), and the graduation requirement is **count-based**
("attend *N* chapels"), not "attend this one". A chaplain schedules each service
in the `Chapel` doctype and assigns the preacher/worship team via `Chapel Team`.

Forcing chapel through the `Event Attendance` engine (per-student or cohort
participants, one occurrence = one fulfilment) would distort it. So chapel gets
its **own** requirement type and doctypes, while reusing ADR 028's philosophy
(type → instance, calendar mirror, automatic fulfilment) and the existing SGR
snapshot machinery.

## Decision

A dedicated **Chapel Attendance** path, kept separate from `Event Attendance`.

- **Chapel → Event mirror.** A confirmed `Chapel` upserts a linked Frappe
  `Event` (`Chapel` controller lifecycle, `seminary/seminary/doctype/chapel/
  chapel.py`): Public, with the Chapel Team Contacts as participants. The Event
  is a **calendar mirror only** — no `event_custom_category`, no SGR
  participants — so `reflect_event_attendance` short-circuits on it.
- **Google Calendar (optional, reuse Frappe native).** A Seminary Settings
  master toggle `sync_chapels_with_google_calendar` (off by default) seeds the
  per-`Chapel` `sync_with_google_calendar` checkbox; `official_google_calendar`
  (Link → Frappe `Google Calendar`) is the shared institutional calendar. When
  both are set, the mirrored Event gets `sync_with_google_calendar=1` +
  `google_calendar`, and Frappe's native integration pushes it. No new
  "Seminary Google Calendar" doctype.
- **Self check-in.** New `Chapel Attendance` doctype (one per student per
  chapel, unique-guarded). `seminary/seminary/chapel.py` `check_in(chapel, code)`
  resolves the student (`get_current_student`), validates the chapel is
  confirmed, the check-in window (Seminary Settings `chapel_checkin_opens_
  before_mins` / `chapel_checkin_closes_after_mins`; **both 0 disables the
  window**), and an optional human-readable code (`require_chapel_checkin_code`
  → generated `Chapel.checkin_code`), then inserts the record.
- **Count-based requirement type.** `Graduation Requirement Item.requirement_
  type` gains `Chapel Attendance`; `default_quantity` (already exemplified as
  "8 chapel attendances") is the required count. `_build_sgr_row` snapshots
  `required_count` and seeds `attended_count=0` on the SGR. On Chapel Attendance
  insert/trash, `reflect_attendance` → `recompute_for_student` counts the
  student's check-ins (since enrollment date) and sets each Chapel Attendance
  SGR's `attended_count` + status (`Not Started`/`In Progress`/`Fulfilled` via
  the existing fulfilment path).
- **Portal.** `get_program_audit` returns `required_count`/`attended_count`;
  ProgramAudit.vue shows "x / N" and a **Check in** action (with code prompt
  when required) fed by `get_chapel_status`.

## Consequences

- Chapel attendance fulfils automatically from self check-in; staff waivers
  still apply (Waived rows are left untouched by the recompute).
- The requirement is fully count-driven: removing attendance recomputes the
  count and can move a row back from Fulfilled — acceptable for this type.
- `Event Attendance` and its per-student/cohort engine are untouched.
- **Setup step:** seminaries create a `Chapel Attendance` GRI with the desired
  `default_quantity`, attach it to the program's graduation policy, and (if
  desired) enable Google Calendar sync + the check-in code in Seminary Settings.

## Deferred

- Staff/usher roster marking and overrides (self check-in only for now).
- Per-term percentage requirements (attend X% of chapels held).
- Surfacing upcoming chapels as a richer portal calendar (only the open-now
  check-in list is exposed today).
