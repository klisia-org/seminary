# 114 — Course catalog: prerequisites, equivalencies and course codes

**Date:** 2026-11-25
**Status:** Accepted 2026-11-25
**Delivers:** SIS-CUR-01 (Yes)
**Related:** 005 (partner course equivalence), 023 (course lifecycle), 058 (leveling), 059 (academic
units, one home per course), 061 (public programs), 098 (substitutions and waivers)

## Context

Registration enforces mandatory prerequisites, but only against a passed row for the exact course,
so a substituted or waived requirement (098) still blocks. "Greek I or Hebrew I" can't be expressed.
A renumbered course loses its link to the old code. Any Instructor can edit any course's
prerequisites, and nothing records the change. 059 says the code prefix comes from the academic
unit, but `coursecode` is typed by hand, so moving a course to an Academic Interdepartment leaves
its old prefix. The public program page lists no courses.

## Decision

1. **Prerequisites use what counts as done.** `unmet_prerequisites` checks against
   `exceptions.satisfied_courses(pe, counted=...)`, with `counted` set to today's rule (graded and
   not Fail). Substituted, waived, 058-exempted and replaced (§3) courses then satisfy prerequisites.
   The SQL exclusion in `get_available_courses_categorized` calls the same function, so
   registration, the course picker and the required-enrollment sweep give one answer.
2. **"Any one of" groups.** `Course_prerequisite` gains `prereq_group` (Int, optional). Mandatory
   rows with the same number are met when any one is satisfied. A row without one must be met on
   its own. Saving fails when a group has a single course, which catches a mistyped number, and when
   a Recommended row has a group. Messages are built from course names ("Greek I or Hebrew I").
3. **Replaced courses.** `Course` gains a child table `Replaced Course` (`course`, Link Course).
   Passing a replaced course counts as passing the course that replaces it. It works one way only:
   the old course does not count the new one. `satisfied_courses` adds replacements, so
   prerequisites, the program audit and the graduation check all read them. A student can't
   register for a course that replaces one they have passed. Prerequisite overrides still apply.
   Partner equivalences (005) need no change.

   Co-owned courses stay one record homed in an Academic Interdepartment (059 §6). To consolidate
   two departmental records, keep one, move it to the Interdepartment (its history stays with it),
   retire the other (023) and list it under the kept course's Replaced Courses.
4. **The course code follows the unit.** `Course` gains `course_id` (Data, required, described as
   "Number only, without the prefix: the prefix comes from the Academic Unit"). `coursecode`
   becomes read-only and is set on save to `<unit_code>-<course_id>` (`ST-501`), or to `course_id`
   alone when the course has no unit. It stays unique and URL-safe. Changing a unit's `unit_code`,
   or a course's unit, re-derives the code, and the stored copies on Course Schedule and Course
   Competency are updated with it. A patch fills `course_id` by removing
   the unit prefix from today's code. Courses whose code doesn't start with their unit's prefix keep
   their code and get no `course_id`, and the form asks for one at the next save. Course pack
   import sets `course_id`, not `coursecode`.
5. **Who edits the catalog.** Course code, unit, credits, prerequisites and replaced courses move to
   permlevel 1, writable by Registrar, Seminary Manager and Program Chair. Instructors keep the
   description and assessment fields. `track_changes` is turned on for `Course`, so every catalog
   change shows who made it and when.
6. **Courses on the public program page.** The program page lists the program's active courses:
   code, name, credits, the first lines of the description, and a "Prerequisites:" line (groups
   shown as "A or B"). A course homed in an Academic Interdepartment says "Offered jointly by X and
   Y", built from its `member_units`, here and in the student course picker. Retired courses and
   disabled program courses are left out.

## Consequences

- A substitution or waiver unblocks registration as well as graduation.
- A co-owned course is one record with one roster, so students never choose between two codes for
  the same course.
- Moving a course to another unit changes its code everywhere it is read live. Existing Course
  Competency names keep the old code, because document names don't change. The Version history
  keeps the old code.
- Instructors who edited prerequisites now ask the registrar or Program Chair. Instructors also
  lose create and delete on Course: a new course needs a Course ID they can't set. Registrar
  gains full Course access, which it never had.
- A messy prerequisite table becomes visible in public. The release notes say to check the tables
  first.
- Corequisites are left out.

**Rejected:**
- Cross-listing as two linked records. 059 §6 chose one home per course.
- A text label for `prereq_group`. Nothing displays it, and it gives typos more room.
- Expressing "or" prerequisites as a 098 substitution. That is one student's exception, not the
  catalog's rule.
- A separate public `/courses` page. Applicants look at the program page.
