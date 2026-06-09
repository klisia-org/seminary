# 037 — Attendance policy: absence limits, standing & alerts

**Date:** 2026-06-08
**Status:** Accepted

## Context

ADR 036 made attendance capturable (Present/Tardy/Absent + self check-in) but
inert — nothing told a student or instructor how many classes had been missed,
and there was no policy. Seminaries commonly fail students who miss more than a
percentage of meetings, and count N tardies as one absence. We want attendance
to drive a visible, governed **standing**, surfaced to students/instructors/
registrar, **without changing grades automatically**.

## Decision

A three-layer policy computed into a per-student standing on the roster, with
flag-and-notify enforcement only.

- **Global (Seminary Settings):** `tardies_per_absence` (default 3, `0` disables
  conversion) and `absence_warning_buffer` (default 1 — the danger band width).
- **Program:** `default_max_absence_percent` — the policy %.
- **Course Schedule:** `attendance_policy` (`Auto (from program)` | `Custom` |
  `Disabled`) + `max_absences_custom`. **Registrar/Program-Chair governed**:
  enforced in `course_schedule.py._guard_attendance_policy` (mirroring
  `cancel_course`/`import_template`) and shown read-only to instructors via
  `course_schedule.js` (no clean permlevel path — Instructors already hold
  permlevel-1 write).

- **The limit is per-student, not per-course.** A Course Schedule has **no
  Program link** (a course can serve several programs; the program lives on each
  student's roster row, `program_std_scr`). So under **Auto** each student's
  limit = `round(their program's default_max_absence_percent% × scheduled
  meetings)`. **Custom** applies one number to everyone; **Disabled** and
  **Virtual + Auto** mean no limit (`0`). The resolved limit is stored on the
  roster as `absence_limit`.

- **Standing (on Scheduled Course Roster, all read-only):** `absence_count`,
  `tardy_count`, `effective_absences` (= absences + `tardies //
  tardies_per_absence`), `absence_limit`, and `attendance_alert_level`
  (0 ok / 1 within buffer / 2 over). Absences linked to an **approved**
  (submitted, `docstatus=1`) Student Leave Application are excluded; auditors
  (`audit_bool=1`) and inactive rosters are never flagged.

- **Recompute** in `seminary/seminary/attendance.py`:
  `recompute_for_attendance` (Student Attendance `after_insert`/`on_update`/
  `on_trash` doc_events), `recompute_for_course_schedule` (Course Schedule
  `on_update` — the Auto limit moves when meeting dates are added *after* the
  initial save), and `recompute_all` (daily backstop in `tasks.py`). Writes use
  `frappe.db.set_value(..., update_modified=False)` so they don't recurse
  through the roster `on_update` grading-advance hook or churn timestamps.

- **Notifications (once per rising crossing):** when `attendance_alert_level`
  rises, a Notification Log fires to instructor(s) + Registrar/Program Chair +
  student — at the danger band and again at over-limit. Lowering the level
  resets silently (no re-spam).

- **Surfaces:** student panel + amber/red banner on `CourseStatus.vue` (fed by
  `get_student_course_status`, augmented with an `attendance` block); per-student
  "X / Y" absences column with at-risk colour on `StudentAttendanceCS.vue` (fed
  by `attendance.get_course_attendance_standings`); and a **Students At
  Attendance Risk** Query Report for the registrar. No Gradebook column.

## Consequences

- Enforcement never auto-changes grades; a human acts on the flag. The "fail for
  absences" action is a deliberate, registrar-driven step (see addendum).
- Because the limit is per-student, two students in the same course can have
  different limits (different programs) — the per-student "X/Y" display reflects
  this; a uniform seminary-wide % simply yields the same Y for everyone.
- See ADR 036 (attendance capture / self check-in) for the upstream data.

## Addendum — Failure for Absences (FA), 2026-06-08

A registrar-driven action to fail a student for unexcused absences despite
otherwise-passing scores (the manual half of "flag + notify").

- **Grade code convention** lives on **Grading Scale** (`fa_code`, default `FA`,
  + `fa_gpa`), beside the existing WP/WF withdraw notations. Existing scales were
  backfilled to `FA`.
- **Sticky flag** `failed_for_absence` on Scheduled Course Roster. `fgrade_this_std`
  ([api.py]) honors it: forces `fgrade = fa_code`, `fgradepass = Fail` regardless
  of score, so it **survives re-grading / Send Grades** (which then emits Fail
  with 0 credits, mirroring the existing pass/fail credit logic).
- **Actions** (registrar / Program Chair only, controller-gated like
  `cancel_course`): `api.fail_for_absence` / `api.undo_fail_for_absence`. The
  transcript (Program Enrollment Course `status=Fail`, `pec_finalgradecode=FA`,
  `count_in_gpa` per `fa_gpa`) is rewritten **only when grades are already
  finalized** (`active=0`), decrementing the enrollment's `totalcredits` if the
  course had counted as passed; undo reverses it. Pre-grading, only the flag +
  roster grade are set and Send Grades does the rest.
- **Surfaces**: a "Fail for Absence" / "Undo" button on the Scheduled Course
  Roster desk form (next to "Grade Student"), and a checkbox-row action on the
  **Students At Attendance Risk** report. The report also offers (when
  `portal_disciplinary` is on and an `Attendance`-category Disciplinary Reason
  exists) a "Report Disciplinary Incident" action that opens a new incident
  prefilled with the student's PE + reason. The instructor attendance page
  ([StudentAttendanceCS.vue]) shows a per-student "Report Disciplinary Incident"
  button (reusing ReportDisciplinaryIncidentModal, prescoped to the student) when
  `portal_disciplinary=1`, an instructor-portal `Attendance` reason exists, and
  the student is at risk / over limit.
