# 036 — Course attendance self check-in (per-meeting code) + printable sheet

**Date:** 2026-06-08
**Status:** Accepted

## Context

The Student Attendance page ([StudentAttendanceCS.vue](../../frontend/src/pages/StudentAttendanceCS.vue),
route `/attendance/:courseName`) lets an instructor tick a roster Present/Absent
per meeting date and save via `mark_attendance` (api.py). Two gaps surfaced for
in-person seminaries:

1. **Low-tech fallback.** Smaller seminaries want to print a blank roster, mark
   it by hand during class, and key it in later.
2. **Manual taking is slow.** ADR 029 already proved a student self check-in
   pattern for **Chapel**: a static, human-readable code per service, valid only
   inside a configurable time window, that students type from the portal. The
   same mechanism fits regular class meetings.

## Decision

Reuse the Chapel self check-in pattern for course meetings, and add a
browser-printed blank sheet. No new attendance schema beyond a per-meeting code.

- **Per-meeting code.** `Course Schedule Meeting Dates` (the `cs_meetinfo` child
  of Course Schedule) gains a read-only `checkin_code`. It is **static per
  meeting** and generated **on demand** by the instructor from the attendance
  page ("Show check-in code") via `course_checkin.ensure_meeting_checkin_code` —
  not pre-generated on save. This needs no backfill patch and creates codes only
  for meetings actually run with check-in.

- **Shared generator.** The code alphabet + `generate_checkin_code()` moved from
  the Chapel controller to `seminary/seminary/utils.py`; Chapel imports it.
  Human-readable (drops ambiguous I/O/0/1), `secrets`-random, 5 chars.

- **Self check-in.** `seminary/seminary/course_checkin.py` mirrors `chapel.py`:
  `get_open_course_checkins()` (portal feed of the student's currently-open
  meetings + already-checked-in flags) and `course_check_in(course_schedule,
  meeting_date, code)`. The latter validates active enrollment
  (`Scheduled Course Roster`, `active=1, audit_bool=0`), the time window (unless
  disabled), and the code (case-insensitive, if required), then writes a
  `Student Attendance` via the existing `make_attendance_records` helper — so
  self check-in and instructor marking share one idempotent code path.

- **Tardy.** Attendance gains a third status, **Tardy**, alongside Present/
  Absent. `status` was already a free-form `Data` field, so no schema change.
  Self check-in auto-marks Tardy when a student checks in later than
  `course_checkin_tardy_after_mins` after meeting start (0 disables). Instructors
  set it manually via a 3-way segmented control on the attendance page;
  `mark_attendance` gained a `students_tardy` bucket (default empty —
  back-compatible).

- **Two modes via `enforce_time_window`.** `Seminary Settings` gains an explicit
  master toggle `enforce_time_window` (default on) — clearer than the chapel
  "set both window bounds to 0" trick, and it drives *behaviour*, not just window
  size:
  - **Enforced (time-based):** the meeting happening now (inside the window) is
    auto-selected; a code may be required; a late check-in is Tardy.
  - **Catch-up (not enforced):** the student picks any past meeting they have no
    attendance for. No clock dependency, no code, never auto-Tardy.

  The remaining settings — `require_course_checkin_code`,
  `course_checkin_opens_before_mins` (15), `course_checkin_closes_after_mins`
  (30), `course_checkin_tardy_after_mins` (10) — apply only in enforced mode
  (`depends_on` hides them otherwise).

  **Timezone caveat:** Frappe stores Time fields without timezone conversion and
  `now_datetime()` is in the *site* time zone (System Settings). Enforced mode is
  only correct when the site time zone matches the seminary; otherwise a live
  class reads as "closed". Catch-up mode exists precisely so a seminary that
  can't rely on that still gets automation.

- **Student surface.** Primary path is a **"Mark my attendance"** button on the
  student's course card ([CourseCardOverlay.vue](../../frontend/src/components/CourseCardOverlay.vue)),
  shown only to enrolled students of a course that has meeting dates (gated by
  `get_course_checkin_context`). Enforced+no-code check-ins submit in one click;
  enforced+code and catch-up open a small dialog. A mobile page
  `CourseCheckin.vue` (`/attendance-checkin`) remains as the **QR-landing
  fallback**: the instructor's "Show check-in code" dialog renders a **QR** (via
  the `qrcode` dep) deep-linking with `?course=&date=&code=` prefilled — scanning
  the projected QR is itself the proof of presence.

- **Printable blank sheet.** A "Print blank sheet" button uses browser
  `window.print()` against a `Teleport`-to-body print root shown only under
  `@media print` (we hide everything but the sheet). No backend Print Format —
  the roster+meeting is not a single doctype document, and the page already holds
  all the data.

## Consequences

- Self check-ins only ever set Present/Tardy; the instructor still reviews and
  finalizes absences via `mark_attendance`. The meeting's "Attendance taken"
  flag stays instructor-driven.
- Auditors (`audit_bool=1`) are excluded from self check-in, matching the
  instructor roster on the attendance page.
- Codes are stable once generated. There is no rotation (see the static-vs-
  rotating decision — static mirrors chapel and is simplest to operate).
- `Student Attendance` is keyed per (student, course, **date**), so multiple
  meeting rows on the same date collapse to one attendance record. Where a date
  carries more than one row, enforced check-in (window, code generation,
  Present/Tardy) resolves to the row whose window is **open now**
  (`_open_meeting`), not the first row matching the date — otherwise the
  student-facing "open" meeting and the server's validation can disagree.

See ADR 029 (chapel attendance) for the parent pattern.
