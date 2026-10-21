# 081 — Excused absences and leave of absence in attendance

**Date:** 2026-09-26
**Status:** Accepted 2026-09-26

## Context

037 excludes absences linked to an approved Student Leave Application, but nothing creates that
link since Frappe Education's leave-to-attendance code was dropped. A leave of absence is now a
Program Enrollment status (`program_status.place_on_leave`), written to Status History where the
registrar works. It touches no course enrollment, so a student on leave keeps accruing absences
and can reach the limit. Short excused absences are each instructor's call, often agreed before
the class, but attendance can only be marked on or after the meeting date.

## Decision

1. **Excused is an attendance status.** Course staff (the same gate as `mark_attendance`) can mark
   a student Excused. It counts as neither an absence nor a tardy.
2. **Excused can be set ahead.** It is the only status allowed on a future meeting, so the
   instructor records it when they agree to the request. When the roll is taken that day, the
   Excused row stays unless the instructor changes it. The server enforces this rule, not only
   the page.
3. **Leave is read from the Program Enrollment, not copied.** An absence on a date inside a leave
   period of the student's enrollment is not counted. A period runs from an LOA Status History
   row's effective date to the next row that ends it. The attendance page shows "On leave" for
   those students. Nothing is written when the leave changes, so extensions and early returns
   are always right.
4. **Student Leave Application is retired.** Remove Student Attendance's `leave_application`
   field, the join in `attendance._counts`, the leave filter in the Absent Student report, and
   its `person_fields` and global-search entries, then delete the doctype and its rows. No site
   uses it in production, so nothing is converted.
5. **Over the limit, the instructor decides at Send Grades.** `send_grades` and
   `send_selected_grades` (used by both gradebooks) refuse while a student being sent is over the
   limit with no decision. They return those students, and the gradebook opens a dialog showing
   each one's absences against the limit. For each student the instructor picks:
   - **Fail for absence:** sets FA through the existing `fail_for_absence`.
   - **Keep the grade:** needs a short reason.
   - **No recommendation:** the grade is sent and the decision is left to the registrar.

   The choice, who made it, when and the reason are stored on the Scheduled Course Roster row.
   The server enforces the stop, so Desk and API callers cannot skip it. A student the registrar
   already decided on does not appear. This changes 037, where only the registrar or Program
   Chair could fail for absence.
6. **The registrar keeps the last word.** The at-risk report shows waivers and pending decisions,
   and the registrar can fail for absence or undo it after grades are sent (037 addendum).

**Rejected: the registrar approves every recommendation before grades go out.** It would hold up
a section's grades until the registrar acts.

**Rejected: create a Student Leave Application from the Status History row.** It would be a
second record of one leave that no one edits, and it would go stale when the leave is extended
or ends early.

## Consequences

Excused absences have no cap for now: an instructor could excuse every meeting. Whether schools
need a cap, and who would set it, is unknown. Courses in progress during a leave are still undecided
(withdraw, Incomplete, or leave as is); that belongs in its own decision.
