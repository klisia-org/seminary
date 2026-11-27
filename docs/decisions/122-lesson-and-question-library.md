# 122 — Lesson and question library

**Date:** 2026-11-27
**Status:** Accepted 2026-11-27; implemented 2026-11-27
**Delivers:** LMS-CRS-06 (Yes; with shared Course Folders)
**Related:** 014 (course templates), 041 (course packs), 107 (chapter release)

## Context

Course Folders can already be shared with other courses and instructors, and lessons embed them
by reference. Everything else belongs to a single place: a Course Lesson belongs to one
section, and a Question or Quiz to one catalogue Course. Reusing a unit in another course means
copying it with a template import or a course pack, and the copies then drift apart. Schools have
material that many courses use: an academic-integrity unit, a research-writing module, a
Spiritual Formation core taught by five instructors. Someone fixes it in one place, and the
other copies stay wrong.

## Decision

1. **Library Lesson**, a new doctype that belongs to the school rather than to a term. It holds
   the content fields of a Course Lesson (`title`, `body`, `youtube`, `captions`, `transcript`,
   `instructor_notes`), `tags`, `maintainers` (a table of Instructors) and `courses`, an
   optional table of catalogue Courses. When `courses` is empty, any instructor may place the
   lesson. When it lists courses, only sections of those courses may place it. Maintainers and
   the Seminary Manager edit it. Other instructors can only place it.
2. **Placing by reference.** Course Lesson gains `library_lesson` (Link). When it is set, the
   lesson shows the library content and its own content fields are hidden. Quizzes, assignments,
   discussions, the LTI link and the assessment criteria stay on the Course Lesson, because
   grading belongs to the section. Release dates and prerequisites (107) stay on the chapter.
3. **Edits reach every section at once**, including running ones. When a maintainer saves a
   change, the instructors of every open section that places the lesson get one notice per day
   through Communication Log, saying what changed (from Frappe's Version log).
4. **Detach.** An instructor may *Detach* a placed lesson. That copies the current library
   content into the Course Lesson and clears the link, so the lesson becomes local and stops
   receiving updates.
5. **Closed sections freeze.** When a section reaches *Closed*, each of its placed lessons is
   detached automatically. The archived course then keeps what students actually saw, for
   grade disputes and accreditation evidence.
6. **Shared questions and quizzes.** Question and Quiz gain `shared_with` (a table of Courses,
   the same as Course Folder Share). The quiz and question pickers for course X offer the items
   whose `course` is X or whose `shared_with` lists X. A quiz already holds its questions by
   reference, so editing a shared question updates every quiz that uses it. Past submissions
   aren't affected, because Quiz Result keeps the question text as it was answered.
7. **Library page** in the instructor portal. Instructors search library lessons and shared
   questions by title, tag or course, preview them, see where each one is placed, and use
   *Add to chapter*. The lesson form gains *From library* next to *New lesson*.
8. **Copying.** On the same site, a template import (014) keeps `library_lesson` links. A
   course pack (041) puts the library content inline, because the library doesn't travel to
   another school. Shared questions go into a pack as ordinary questions of the pack's course.
9. **Required lessons.** The Seminary Manager can require a library lesson with a new doctype,
   *Library Lesson Requirement*. Its fields are `library_lesson`, `programs` (a table),
   `academic_terms` (a table, where empty means every term from now on), `position` (*Start of
   the first chapter* / *End of the last chapter*), `reason` and `active`. Every section in
   those terms whose course is in one of those programs (through Program Course) receives one
   placed Course Lesson with `required_by` set. A section whose course is in several programs
   receives it once. Placement happens when the requirement is saved, for sections that aren't
   yet *Closed*, and again when a section is created or a template is imported. Instructors
   can't detach, move out of the section or delete a required lesson, and the lesson shows a
   "Required by the school" badge. When the requirement is deactivated, its lessons are removed
   from sections that are still open, unless a student has already completed them. A lesson
   with a completion stays and stops being required. Instructors of the affected sections get
   one notice when the requirement is placed.
10. **Library use report**, a script report for the Seminary Manager, Registrar and Program
   Chair. It has one row per placement, with library lesson, term, program, section, instructors,
   *Required* or *Chosen*, state (*Placed* / *Detached* / *Frozen at close*), the date placed,
   and student completion (completed / enrolled, from Course Schedule Progress). Filters cover
   lesson, term, program and required-only. A summary lists the sections that should hold a
   required lesson but don't. That happens when a section's chapters were deleted, or when the
   requirement was added after the section closed.

Rejected: sharing a Course Lesson directly. It belongs to one section's chapter, and that
section ends. Also rejected: local edits on top of a placed lesson, because nobody could say
which version wins when the library changes. Also rejected: pinning each section to a version
of the lesson. Instructors would then have to accept every update, and updates reaching every
course is the reason to have a library. Also rejected: a school-wide notice or acknowledgement
instead of a required lesson. It can't hold a quiz, wouldn't count in course progress, and
would live outside the course where students do their work.

## Consequences

A core unit is edited once and every running section shows the change, while closed sections
keep what was taught. Content can change in the middle of a term, so maintainers carry that
responsibility and the daily notice tells the affected instructors. Lesson reads gain one join.
Open question: whether placing a lesson should require the maintainer's approval in schools
where departments guard their material. For now `courses` restricts where a lesson can go, and
nobody approves each placement. A required lesson follows the chapter it sits in. If that
chapter has a release date or prerequisites (107), students wait for them, and the lesson counts
toward *Complete chapter* prerequisites. Instructors should hear about this when the requirement
is placed.

## As built

- §2: the placed lesson's own content holds only activity blocks (quiz, assignment, exam,
  discussion, oral). They are shown after the library's blocks, and a save with any other block
  is refused. A library lesson refuses activity blocks, and also the competency reflection
  blocks (self-assessment, development plan), which read their own section's lesson. Neither
  editor offers them. The placed lesson's title is copied from
  the library and kept in step, so the outline and reports need no join.
- §2: a library lesson's files are read by whoever may read the lesson: instructors, and the
  students of the sections that place it.
- §5: closing freezes required lessons too. They keep `required_by`, so the report still shows
  them.
- §6: the question picker also offers questions that name no course, which is most of them,
  as it did before.
- §7: the portal page is *Lesson Library* (/lesson-library). The Desk Teaching sidebar has a
  *Lesson library* section with the requirements and the report. Library lessons themselves are
  edited in the portal.
- §8: a template import into a course the lesson isn't available to copies its content instead.
- §9: placement also runs when a chapter joins a section's outline, so a section built by hand
  gets the lesson with its first chapter. Template imports and course packs place once at the
  end. If the section already placed the same library lesson, that lesson becomes the required
  one instead of a second copy. Each instructor gets one notice per section.

