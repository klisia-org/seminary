# Course catalog

A **Course** is a subject you teach. Each time it is offered you schedule it as a Course
Schedule. This page covers the parts of a course that make up the catalog: its code, its
prerequisites and the older courses it replaces.

Only a **Registrar**, **Seminary Manager** or **Program Chair** can change these fields.
Instructors can read them and still edit a course's description and assessment. Every change
is kept in the course's history, with who made it and when.

## Course code

You type the **Course ID**: the number only, without the prefix (for example `501`). The
**Course Code** is set from it and can't be edited. It is the course's **Academic Unit** code,
a hyphen and the Course ID: `ST-501`. A course with no unit has the Course ID as its code.

- Change a unit's **Code** and the codes of all its courses change with it. The new codes also
  show on the course's schedules and competencies.
- Move a course to another unit and its code changes the same way. The course keeps its
  history, because it is still the same record.
- Codes are unique. A unit code that would give two courses the same code is refused.

Courses from before this rule that had a code not starting with their unit's code keep that
code. The form asks for a Course ID the next time someone saves the course.

### A course two departments share

Don't create a course twice, once per department. Create an **Academic Interdepartment** whose
member units are the two departments, and home the single course there (see
[Academic Units](academic-units.md)). The course takes the Interdepartment's code. Students and
the program page see "Offered jointly by Theology and Pastoral Ministries".

If you already have two records, keep one and move it to the Interdepartment. Retire the other
one (tick **Disabled**). Then add it under **Replaced Courses** on the course you kept.

## Prerequisites

On the course's **Prerequisites** table, each row names a course and whether it is
**Mandatory** or **Recommended**. Students can't register for a course until its mandatory
prerequisites are met. Recommended ones only show as advice.

A prerequisite is met when the student has a grade in it that isn't a fail, or when it counts
as done another way:

- the student was exempted from it by a placement (leveling),
- an approved waiver or substitution covers it,
- the student passed a course it replaces (see below).

### "Any one of" groups

To ask for one course out of several, such as *Greek I or Hebrew I*, give those mandatory
rows the same number in **Any-One-Of Group**. Passing any one of them is enough. Leave the
number blank for a course that is required on its own. A group needs at least two courses,
so a mistyped number is caught when you save. Recommended rows don't take a group.

Messages and the program page show a group as "Greek I or Hebrew I".

## Replaced courses

When a course replaces an older one, for example after renumbering or after merging two
records, list the older course under **Replaced Courses**. A student who passed the older
course counts as having passed the new one for prerequisites, the program audit and
graduation. It works one way only: passing the new course doesn't count for the old one.

A student can't register for a course that replaces one they have already passed. A registrar
can override this, as for prerequisites, by ticking **Don't check pre-requisites** on the
enrollment.

## On the program page

The public program page lists the program's courses: code, name, credits, the start of the
description, its prerequisites and, for a shared course, who offers it jointly. Retired
courses and courses disabled in the program are left out. Check your prerequisite tables
before publishing, because they are now public.
