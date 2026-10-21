# 082 — Individual due dates, late penalties and submission cut-off

**Date:** 2026-09-28
**Status:** Accepted 2026-09-28

## Context

Each Scheduled Course Assess Criteria row has one `due_date`, and it applies to every student. An
instructor can't give one student more time on a quiz, exam or assignment, whether as a favour, an
accommodation or after an excused absence (081). A graded discussion can't set one due date for
the initial post and another for the replies. The due date also has no effect: a late
submission is accepted and graded like an on-time one. The course can't deduct points for
lateness or close submissions at a set time. Canvas, Moodle, Brightspace and Blackboard all let
instructors do these things, and seminary instructors coming from them expect it.

## Decision

1. **Scope, measured against the leading LMSs.**

   | Feature (where it exists) | Decision |
   |---|---|
   | Per-student due date (Canvas "Assign to", Moodle user override, Brightspace special access, Blackboard exception) | **Yes** (§2) |
   | Per-group due date (Canvas/Moodle group override) | **No, for now.** Sections are separate Course Schedules; override each student instead |
   | Cut-off: no submissions after a set time (Canvas "until", Moodle cut-off) | **Yes** (§3) |
   | "Available from": the activity opens at a set time | **No.** Content release already controls when activities appear |
   | Automatic late penalty, % per day or hour, with a floor (Canvas late policy) | **Yes**, numeric scales only (§4) |
   | Grace period before a submission counts as late (Moodle, Blackboard) | **Yes**, in minutes, part of the late policy |
   | Instructor waives or changes the penalty on one submission (Canvas) | **Yes** (§4) |
   | Extra time and extra attempts on a timed quiz or exam for one student (Canvas moderate, Moodle override) | **Yes**, in the same override (§2) |
   | Missing work graded automatically, e.g. 0 after the cut-off (Canvas missing policy) | **No.** The instructor enters the grade |
   | Excuse one student from an assessment, removing it from their grade (Canvas, Brightspace) | **No, for now.** How the weight is redistributed needs its own decision |
   | Students request an extension in the app (Moodle plugin) | **No, for now.** None of the four has it built in, and it may invite more requests. Later it could be a draft override the instructor approves |
   | Separate due dates for a discussion's initial post and its replies (Canvas checkpoints) | **Yes**, with a deduction per missing reply (§5) |
   | Default late policy for the school or a course category (Moodle) | **No.** Courses serve several programs, and nothing yet tells an intensive section from a 12-week one. The template import carries the policy (§6) |

2. **Student Due Date Override** is a new doctype, not a child table. It holds a Course Schedule,
   a criteria row, a student, the new due date, an optional new cut-off, optional extra minutes
   and extra attempts, and a reason. Course staff (the same gate as the gradebook) and the
   registrar can create one. An override replaces the row's dates for that student only. Every
   check reads the student's effective due date and cut-off: the override if one exists,
   otherwise the row's own. When a student is marked Excused (081) on a meeting whose date
   matches an assessment's due date, the instructor is offered an override for that student. It
   is created only if the instructor confirms it.
3. **Cut-off** is an optional Datetime on the criteria row. After the student's effective cut-off,
   the server refuses to start or submit quiz, exam and assignment attempts and to post
   discussion replies that count for a grade. A timed attempt started before the cut-off ends at
   the earlier of its time limit and the cut-off. The student sees the reason and who to contact.
4. **The late policy lives on the Course Schedule's Grade Setup tab**, available only when the
   grading scale is numeric. It sets a deduction (% per day or per hour), a grace period in
   minutes and a lowest possible score. Each criteria row can opt out. The raw score is stored.
   The deduction is worked out from the submission time and the effective due date, not copied,
   so moving a due date or adding an override later still gives the right grade. The instructor
   can waive or change the deduction on one submission, with a reason. Send Grades freezes the
   result.
5. **A discussion can have two due dates.** When its Discussion Activity has `post_before` set
   and `min_replies_required` > 0, the criteria row also gets a replies due date. The row's
   `due_date` then applies to the initial post only. The late policy treats the two parts
   differently. A late initial post loses the usual % per day or hour. A reply posted after the
   replies due date does not count, and each missing reply loses a set %, entered on the late
   policy. An override may move either date. Other discussions have one due date, which applies
   to the whole activity.
6. **The template import copies the late policy.** It copies the Course Schedule's policy, each
   row's opt-out. Dates (the due date, the replies due date and the cut-off) and student
   overrides are not copied: they belong to that section's calendar and students.
7. **Where it lives in the app.** Rules for all students go where the instructor already sets
   assessments. Exceptions go where the instructor already sees the student.
   - **CourseAssessment.vue**, the section's rules:
     - A *Late policy* panel above the table, shown for numeric scales. The same fields are on
       the Desk Grade Setup tab.
     - Each row keeps its Due Date column and gets a clock button. The button opens a detail row
       (the same pattern as the competency panel) with the cut-off, the replies due date (§5),
       the opt-out and that row's student overrides, which can be added and edited there.
   - **Gradebook.vue**, one student:
     - A late submission's cell shows the deduction beside the raw score.
     - The cell's menu shows that student's dates. From it the instructor can add an override or
       waive or change the deduction.
   - **StudentAttendanceCS.vue:** after the instructor saves an Excused status, a dialog lists
     the assessments due that day and offers an override for each (§2).
   - **Student pages** (to-do list, course outline, lesson): these show the student's effective
     due date and cut-off, a warning before a late submission and the reason when one is refused.
   - **Desk:** the registrar works in the Student Due Date Override list, for example for
     accommodations the school approved.

**Rejected: new columns in the assessment table.** It already has up to eleven columns. A cut-off,
a second date and an opt-out on every row would crowd it, when most rows use none of them.

**Rejected: the late policy on each activity (Moodle).** Quizzes and exams belong to the Course,
so one activity may be used by several sections with different policies. One policy per Course
Schedule matches how syllabi state it.

## Consequences

Instructors can handle accommodations and exceptions in the app instead of grading by hand. The
due date now counts, so every place that shows or checks it must use the effective date: the
student's to-do list, the calendar, reminders and the gradebook's late flag. Letter-grade,
pass/fail and competency-based sections get overrides and cut-offs but no automatic deduction.
A Course Schedule type (intensive, standard, self-paced) could later supply default policies,
and attendance and enrollment dates could use it too; that needs its own decision.
