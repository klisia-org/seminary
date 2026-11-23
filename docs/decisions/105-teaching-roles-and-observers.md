# 105 — Teaching roles and course observers

**Date:** 2026-11-23
**Status:** Accepted 2026-11-23; implemented 2026-11-23
**Delivers:** LMS-ADM-01 (Yes)
**Related:** p007 §2.8 (instructor tiers), 042 (Person), 066 (mentors), 097 (discussions)

## Context

Instructor Category already sets how far an instructor can see: an instructor of record can read
across the school, and anyone else only the sections they are listed on. It does not set what they
can do there. Every instructor listed on a section can edit the outline, grade, take attendance and
post to the class, so a "Grader" ("grades only") can rewrite the course. There is also no way to
let someone read a course without teaching it: a peer reviewing someone's teaching, an advisor,
an accreditation visitor, a ministry supervisor. A reviewer checking instructor, TA and observer
finds the first and neither of the others.

## Decision

1. **Categories grant actions.** Instructor Category gains four checkboxes: *Edits course content*,
   *Grades*, *Records attendance*, *Posts to the class* (announcements and instructor replies).
   Reach stays as it is; these say what may be done within it.
2. **Defaults, on new and existing sites.** Instructor of Record and Co-Instructor get all four.
   Graduate Teaching Assistant gets *Grades*, *Records attendance* and *Posts to the class*.
   Grader gets *Grades* only. Any other category, and a new one, starts with all four. On an
   existing site this applies on update, so a Grader or assistant there loses what they could do
   before; the school ticks it back if it wants.
3. **Per section.** The category on the section's instructor row decides; an empty row category
   falls back to the instructor's default category, and an empty default allows all four (the
   p007 "no restriction recorded" rule). One gate, `require_section_capability(section, action)`,
   replaces the role-only checks in `require_grader`, `require_outline_editor` and the attendance
   and posting endpoints. School roles pass, as now.
4. **Observers.** Course Schedule gains a `Course Schedule Observers` table: Person, optional
   *Until* date, reason. The user comes from the Person; no Instructor record, so observers never
   appear in faculty counts, payroll or accreditation reports. An observer gets the portal's
   read-only view of the published course: outline, lessons, assessments and announcements.
5. **Observers do not see students.** No roster, grades, submissions or discussion posts. Seeing
   student work needs a school-official reason that a supervisor or visitor may not have; a school
   that wants it lists the person as an instructor in a category with no actions ticked.
6. **Access ends by itself.** Past *Until*, or when the section is cancelled, the row stops
   granting anything.

Rejected: an *Observer* Frappe role. A role is site-wide, and observing is about one section.

## Consequences

Instructor, TA and observer each mean something different and enforced, and schools set it per
category rather than per person. Writes through the existing section gates and the row-level
permission hook now ask for the action; reads do not change. Open: whether a TA's *Grades* should cover
only an assigned group of students (left out; whole section for now), and whether observers are
told when they are added.

## As built

- §3: the row-level permission hook maps each section-keyed doctype to its action, so Desk and
  `frappe.client` writes are covered too. A class announcement is Frappe's `email` on the section.
- §3: only the course page hides what a category leaves out (outline editing, announcements).
  Grading and attendance pages still show their buttons, and the server refuses with a message
  naming the missing action.
- Not covered: rubrics and activity documents (Assignment, Discussion, Oral Activity) are not
  keyed to a section, so their editing still follows the Instructor role alone.
- The whitelisted functions this touched gained argument type hints (Frappe's semgrep rules).
