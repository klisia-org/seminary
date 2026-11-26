# 116 — Formation attendance requirements: cohort meetings and chapel by roll or percentage

**Date:** 2026-11-25
**Status:** Accepted 2026-11-25; implemented 2026-11-25
**Delivers:** SIS-FOR-03 (Yes)
**Amends:** 029 (chapel attendance), 101 §7 (cohort meeting attendance), 034 (role taxonomy)
**Related:** 028 (events), 066 (cohort types), 081 (excused absences and leave)

## Context

Chapel (029) and events such as retreats (028) can count toward graduation. Mentoring groups can't. 101 §7
records cohort meeting attendance but keeps it as the cohort's own record, so no requirement can read it.
Chapel can only count self check-ins toward a fixed number: no one can take a roll, and a school that
requires "75% of chapels each term" can't express it.

## Decision

1. **New requirement type `Cohort Meeting Attendance`.** The Graduation Requirement Item gains
   `cohort_types` (Table MultiSelect of Cohort Type, required for this type): which cohorts' meetings
   count, for example Mentoring Group. A meeting counts for a student when it is Scheduled, has started,
   falls on or after the enrollment date, and the leader marked the student's Person. Unmarked rows don't
   count. 101 §7 is amended: the record is still the cohort's, but formation requirements read it.
2. **One measure for both types.** The `Chapel Attendance` and `Cohort Meeting Attendance` GRIs gain
   `attendance_measure` (Count, as in 029, or Percentage), `percentage_period` (Whole program or Each
   term) and `minimum_held`. `default_quantity` is the count or the percentage (1–100). Excused never
   counts as attended. A percentage's base leaves out Excused and occasions on a leave day (081 §3). The
   base is derived every time, never stored. The measure, target, minimum and counted cohort types are
   snapshotted on the SGR (012).
3. **Status of a percentage row.** For Whole program, the row is Fulfilled while the rate is at or above
   the target and at least `minimum_held` (at least 1) occasions are in the base; otherwise In Progress.
   For Each term, each completed Academic Term that overlaps the enrollment and has at least
   `minimum_held` occasions in its base is judged. The row is Fulfilled when every judged term met the
   target. A term below the target leaves it In Progress, and only a waiver clears it. Rows can move back
   from Fulfilled (as in 029). Waived rows are never recomputed. The SGR shows `attendance_rate` (for
   Each term, the latest judged term) and `term_rates`, and the portal audit shows "82% (target 75%)".
4. **Recompute.** A recompute runs when:
   - a Chapel Attendance is saved or deleted (after the delete, so the removed record no longer counts;
     029's `on_trash` counted it);
   - a Chapel is confirmed, moved or deleted (queued; recomputes every chapel percentage row);
   - a Cohort Meeting is saved (for the members whose marks changed, or all marked members if the meeting
     was cancelled or moved);
   - an enrollment goes on leave or returns.

   A daily job also recomputes every percentage row, so an occasion held but missed lowers the rate.
5. **Chapel roll and the Chaplain role.** Chapel Attendance gains `status` (Present or Excused) and
   `method` (Self check-in or Roster). A new **Chaplain** role has full access to Chapel and Chapel
   Attendance and can read Room. The Chapel Team picks contacts through a gated search, so Contact's own
   rules are untouched. *Take Roll* on a confirmed chapel (Chaplain, Seminary Manager or Program Chair)
   lists the students with a chapel requirement. It can mark Excused ahead of time, mark Present once the
   chapel has started, or clear a mark to remove the record. A student who was excused and then checks
   in becomes Present. Existing check-ins are patched to Present / Self check-in.

## Consequences

- Mentoring groups, chapel and retreats all count toward graduation without being courses.
- A cohort leader's roll now affects graduation, so marking Absent matters. Mentors already see the
  record (101 §7).
- A chapel percentage's base is every confirmed chapel since enrollment, including ones a student
  couldn't attend. Excused or a leave of absence is the remedy.
- Missing the target in one term can't be made up later. That is the school's choice, and the remedy is
  a waiver.
