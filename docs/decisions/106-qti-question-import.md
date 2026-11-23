# 106 — QTI question import

**Date:** 2026-11-23
**Status:** Accepted 2026-11-23; implemented 2026-11-23
**Delivers:** LMS-ASM-02 (Yes), LMS-ASM-01 (Yes), LMS-ASM-06 (Yes)
**Related:** 041 (course packs), 082 (extra time and attempts), 084 (Send Grades)

## Context

RFPs ask four things about quizzes: question banks, randomisation, timed attempts with per-student
accommodations, and QTI import. Seminary already has the first three. A Question belongs to a
course and can be used in any number of quizzes. A quiz shuffles its questions and can draw a
set number of them at random, with a time limit and an attempt limit. 082 lets an instructor give
one student extra minutes and attempts. QTI import is missing, so a school moving from Canvas,
Blackboard or Brightspace has to type its quizzes in again. Course packs (041) only move
questions between seminary sites.

The assignment and grade lines above were never claimed: online submission and Send Grades, which
writes final grades to the student record with nothing re-keyed, predate these records.

## Decision

1. **Import questions** on the quiz and exam forms accepts a QTI 1.2 or 2.1 package (`.zip`) or
   a single `.xml` file, as Canvas, Blackboard and Brightspace export them.
2. **Into a quiz:** multiple choice, multiple answer and true/false become *Choices*; short
   answer and fill-in-the-blank become *User Input*, taking their accepted answers. Each item becomes
   a Question on the quiz's course and a row on the quiz with the package's points.
3. **Into an exam:** essay items become Open Questions on the exam's rows.
4. **No limit on options or accepted answers.** Question's four fixed option slots and four
   accepted-answer slots become two child tables, *Choices* and *Accepted Answers*. A patch moves
   existing questions; course packs from older sites still import.
5. **Skipped, with a report.** Items that don't fit are listed with the reason and nothing is
   created for them: matching, numeric, file upload, or an essay sent to a quiz. Images in the
   package are stored as private files on the question.
6. The XML is parsed with `defusedxml`, with limits on package size and item count.

Rejected: Moodle XML. Moodle has no QTI export, but adding a second format should wait until a
school moving from Moodle asks for it. Raising the fixed slots to eight: still a cap, and every
reader loops over numbered fields.

## Consequences

A migrating school brings its question banks in one upload per quiz and sees what it has to
re-enter. Exporting to QTI is not included; course packs cover seminary to seminary. Anything
outside seminary that read `option_1`…`option_4` must read the tables instead.

## As built

- §5: package images are private files attached to the quiz or exam, not the question: students
  can read a quiz but not a Question, so an image on the question would never load for them.
- §4: the question editor saves fields and all three tables through one `save_question` call.
  The student payload lists options as `options: [{option, explanation}]`; only correct options
  carry an explanation, and it travels only when answers may be shown, as before.
- §4: the all-at-once quiz view now receives `multiple`, so multiple-answer questions show
  checkboxes there instead of radio buttons.
- §1: the uploaded package is deleted after import, and only its uploader may import it.
  Limits are in `qti.py` and can be raised in site config (`qti_max_bytes` and others).
