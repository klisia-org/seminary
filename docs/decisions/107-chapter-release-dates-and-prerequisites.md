# 107 — Chapter release dates and prerequisites

**Date:** 2026-11-23
**Status:** Accepted 2026-11-23; implemented 2026-11-23
**Delivers:** LMS-CRS-03 (Yes)
**Related:** 014 (course templates), 041 (course packs), 065/079 (CBE content release), 082 (due-date overrides)

## Context

Chapters (Course Schedule Chapter) are seminary's modules. The only way to lock one is the CBE
release mode (065/079), which waits for a self-assessment and exists only in competency-based
sections. An instructor can't open a chapter on a date or require one chapter, or a passing quiz,
before the next. Canvas, Moodle, Brightspace and Blackboard all do both, and RFPs ask for them.

## Decision

1. **Release date on a chapter.** Course Schedule Chapter gains `release_type` (*Always open* /
   *On a date* / *Days after start*), `release_on` (Datetime) and `release_offset_days` (Int).
   *Days after start* counts from the section's `c_datestart`. In an open-ended section it counts
   from the student's enrolment (when their roster row was created). Times are in the site's
   time zone.
2. **A locked chapter is shown greyed out.** The student sees the chapter title, its lesson
   titles and the reason, for example "Opens Thu 12 Feb, 09:00" or "Finish Chapter 2 first".
   Lesson content isn't sent until the chapter opens.
3. **Prerequisites.** A new child table, *Chapter Prerequisite*, on the chapter. Each row is one
   of two kinds:
   - *Complete chapter*: every lesson in that chapter is Complete in Course Schedule Progress.
   - *Pass quiz*: the student's best submission meets the quiz's `passing_percentage`, or a
     minimum set on the row.

   Every row must be met. Rows may only point to chapters and quizzes in the same section, and a
   prerequisite loop is refused when the chapter is saved.
4. **One rule decides what is open, in every section, CBE included.** `visible_outline` moves
   out of `cbe.py` into a new `content_release.py` and checks three locks: the release date, the
   prerequisites, and the CBE self-assessment lock where the section is gated. A chapter opens
   when all three allow it. Each lock that applies is listed with its reason. Date and
   prerequisite locks always lock the whole chapter. The CBE mode that leaves content open and
   locks only activities keeps working as it does now. The server enforces every lock: the lesson
   endpoints refuse locked content, and the submission guard (`assert_activity_unlocked`) covers
   all three locks.
5. **Staff see everything.** Instructors, observers and the registrar see every chapter. A locked
   chapter carries a "Students: opens 12 Feb" badge.
6. **Per-student override.** A new doctype, *Student Chapter Release Override*, follows the 082
   pattern. Each record names a section, a chapter, a student, an optional `open_from` date
   (earlier or later than the chapter's), a `waive_prerequisites` check, a required `reason` and
   a `source`. The same people who can create due-date overrides can create these. Waiving lifts
   the CBE self-assessment lock too, and the reason stays on the record.
7. **Copying keeps the schedule.** Template import (014) and course packs (041) carry the release
   fields and prerequisites. *Days after start* copies unchanged. An *On a date* release moves by
   the gap between the old and new start dates. Prerequisite rows point to the copied chapters
   and quizzes. A row that can't be pointed at a copy is dropped and listed in the import
   message.
8. **Notice when a chapter opens.** An hourly job finds release times that passed since its last
   run (stored on Seminary Settings), so a missed run catches up and nothing is sent twice. It
   then sends "Chapter X is now open" through Communication Log to each enrolled student. A
   student who is still locked out by a prerequisite or the CBE lock gets nothing, and the notice
   goes once that lock clears. Each section has `notify_on_release`, on by default.

Rejected: prerequisites that accept any one of several conditions, and an assignment grade as a
prerequisite. Grading can take days, so the student would wait on the instructor rather than on
their own work. Hiding a locked chapter completely was also rejected, because students should see
what is coming.

## Consequences

Any section can pace its content, and CBE sections can add dates and prerequisites to their
competency lock. Hourly notices mean a chapter can open up to an hour before its notice goes
out. Lesson endpoints gain a lock check on every read. New support question: "why is Chapter 3
grey?" The reason shown on the chapter answers it.

## As built

- §8: the notice job keeps no last-run time on Seminary Settings. It looks back 7 days on each
  run and relies on Communication Log's dedupe key (`chapter-open-<roster>-<chapter>`), so a
  missed run catches up and nothing is sent twice. A release more than 7 days old sends nothing,
  which also keeps a running term quiet when this ships. The section switch is on the portal
  course form as well as Desk.
- §4: `cbe.visible_outline` is now `cbe.competency_locks`, the CBE part only. Before this, the CBE
  lock was enforced on submissions only. Now `get_course_outline` leaves out the lesson content of
  a locked chapter, `get_lesson` returns only the title and reasons, SCORM launch refuses, and
  `save_progress` won't complete a lesson in a locked chapter. It checks the lesson's own chapter,
  not the one the caller names.
- §4: the submission guard finds an activity's chapter through the lessons that hold its
  assessment row, as well as through its competency.
- §3: a quiz counts as part of the section when one of its assessment rows or lessons uses it. A
  deleted chapter takes its prerequisites, the prerequisite rows that pointed at it, and its
  overrides with it.

