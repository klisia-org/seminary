# Grading

Grading is how you decide what a student earned in a course and how you keep
track of getting there. Seminary ERP gives you two places to work, and they
fit together cleanly: a **To-Do card** that surfaces what's waiting on your
attention, and a **Gradebook** that gives you the whole picture in a grid.

## Overview

Grading in Seminary ERP is built around two ideas:

- **Assessment Criteria** define *what counts* toward the final grade for a
  course (the syllabus says "30% papers, 20% quizzes, 50% final exam," and
  the Assessment Criteria express that as rows on the Course Schedule).
- **Submissions** are *what students hand in* (a paper, a quiz attempt, an
  exam, a discussion post). Each submission gets graded against the
  Assessment Criterion it belongs to, then rolls up into the student's
  course total.

Some assessments don't have a submission at all — chapel attendance,
class participation, an in-class presentation. Those use a special type
called **Offline**, where you enter the grade directly in the Gradebook
without any handed-in artifact.

## Assessment types

When you create an Assessment Criterion (on the Course Assessment page),
you pick a **type**. That type decides how the assessment is collected
and how students submit (or don't).

### Quiz

Auto-graded multiple-choice / true-false / short-answer style questions.
Students take it in the browser; the system scores it the moment they
hit submit. You can configure passing percentage and maximum attempts on
the Quiz itself. Most quizzes need no instructor grading at all — but if
you've added open-ended questions, those land in the Quiz Submission
view for you to score.

> **Use this for:** weekly comprehension checks, vocabulary drills,
> reading-confirmation quizzes, anything where the answer is mechanically
> right or wrong.

### Assignment

A paper or file the student writes and uploads (PDF, document, image, URL,
or text). Students see a prompt in the lesson, write or attach their
answer, and submit. You then open each Assignment Submission, read it,
and enter a score plus written feedback.

> **Use this for:** essays, exegetical papers, reflection journals,
> project deliverables — anything where the student produces something
> you read carefully.

### Exam

A more elaborate, often timed, in-browser test. Exams support multiple
question types (multiple choice, open-ended, file upload), time limits,
and per-question feedback. Auto-gradable parts score themselves; the
open-ended portions are flagged "Not Graded" until you score them.

> **Use this for:** midterms, finals, formal proctored assessments where
> you want a single linear test experience for the student.

### Discussion

Threaded online dialogue. Students post their initial position on a prompt
and reply to classmates. Discussions can be **graded** (linked to an
Assessment Criterion) or **free-form** (just for engagement). Graded
discussions can require students to reply to a minimum number of
classmates' original posts; you set this on the Discussion Activity as
*"Minimum replies to other students"*. The system tracks each student's
reply count and won't mark the discussion complete until the threshold
is met.

> **Use this for:** weekly conversation around the readings, case-study
> debates, peer feedback rounds — anywhere the *interaction* is the
> learning.

### Offline

The catch-all for things you grade outside the LMS. There's no submission
doctype, no upload, no scoring page. You just open the Gradebook and type
the score for each student.

> **Use this for:** chapel attendance, class participation, in-person
> presentations, oral exams, lab work, peer-evaluation scores, anything
> that lives in your notebook and you transcribe in. Create one Offline
> assessment per category so the weights still add up cleanly.

## Where grading happens day to day

### The To-Do card (top-right of every Course page)

Every Course Detail page shows a **To-Do** card on the right. For
instructors and academic users it lists, in plain text:

- **"Assignments to Grade — N"**, **"Exams to Grade — N"**, etc. — one
  line per activity with un-graded submissions, with the count.
- Each line is a clickable shortcut straight into the grading queue
  for that activity.

This is your daily triage view. Open the course, glance at the card,
click the activity with the biggest backlog. The card only shows things
that actually need attention — empty queues collapse to *"Congrats!
No assessments to grade for now."*

> **What's NOT in the To-Do card:** Offline assessments. Since there's
> no submission to grade, they don't appear here. Use the Gradebook for
> those.

### The grading queue (one activity at a time)

Clicking an item from the To-Do card takes you to the per-activity
**Submissions** page. There you see one row per student, with their
submission status (Not Submitted / Not Graded / Graded), original-post
date or upload date, and any reply count for discussions. Click a
student's row to open their submission, read it, type a score, leave
feedback, and save.

This is the right place when you want to focus on a single assessment
and grade it cohort-wide in one sitting.

### The Gradebook (the whole grid)

The **Gradebook** (linked from every Course page) is a single table:

- **Rows:** every student in the course.
- **Columns:** every Assessment Criterion, in order, with weight
  percentage shown beneath the title.
- **Cells:** each student's grade for that assessment.

Three things to know:

1. **Header links.** Click any column title and you jump to that
   assessment's grading queue (the per-activity view above). The
   Gradebook is the natural launch pad when you're moving across
   assessments rather than across students.
2. **Edit cells directly.** You can type a grade in any cell. This is
   the **only place to enter grades for Offline assessments** — there's
   nothing to click into for those, since there's no submission. It also
   works as an override for the other types if you ever need to nudge a
   grade after the submission has been saved.
3. **Save All Changes.** Edits are tracked locally until you click the
   *Save All Changes* button at the top (or press `Ctrl+S`). The button
   shows how many cells have unsaved edits. This batches the writes so
   you can flow through the grid without saving every cell.

Extra-credit columns are tinted blue and show a "Max Extra: N" hint
under the title instead of a weight, so they're easy to spot.

## Rubrics

A rubric grades an assignment or a discussion criterion by criterion instead of
with one number. Rubrics have two parts, and different people own each part.

**The scale belongs to the school.** On the Desk, under **Rubric Scale**, the
academic office defines the levels every rubric uses, highest first. For example:

| Level | Percent of the criterion | Description |
|---|---|---|
| Excellent | 100 | Goes beyond what the assignment asks. |
| Proficient | 85 | Does what the assignment asks. *(meets expectations)* |
| Developing | 70 | Partly does what the assignment asks. |
| Beginning | 50 | Does not yet do what the assignment asks. |

Mark one level as **Meets Expectations**, and tick **Default** on the scale
instructors should start from. A school can keep more than one scale. Once a
student has been graded on a scale, its levels can no longer change. To change
them, create a new scale and make it the default.

**The criteria belong to the instructor.** Open the assignment or discussion in
the portal and use **Add a rubric** at the bottom of the page:

- Give each criterion a title and, if you like, a line about what is judged.
- **Weight %** starts out automatic: the criteria share 100% evenly, and each
  box shows the percent its criterion counts for. Type a percent to fix one
  criterion, and the blank ones share what is left. For example, with five
  criteria, fixing one at 5% gives each of the other four 23.75%. Clear a box to
  make it automatic again. You never need to make the weights add up.
- The levels come from the scale, and each one shows the scale's description.
  Use **Write wording per level** only where you want to say something specific,
  such as *"Proficient: identifies the structure but misses the chiasm."*
- **Copy from…** starts from a rubric you used on another activity.

Students see the rubric under the assignment or discussion prompt before they
submit.

**Grading.** On the grading page, click a level for each criterion. You can add
a comment under each one. Once every criterion has a level, the grade is
computed for you on the course's grading scale, and the score box is hidden.
For example, all criteria at the top level give the scale's maximum. Extra
credit and late deductions still apply as usual. Once the work is graded,
students see the level they reached on each criterion and your comments.

**Changing a rubric after grading.** A rubric that has been used to grade
cannot be edited in place. Saving it from the activity creates a new version.
Students graded earlier keep the version they were graded on.

Rubrics are not used in competency-based courses, which grade on the
competency's own levels, or in courses graded on a descriptive scale.

## A typical week

A common rhythm for a seminary instructor:

1. **Monday morning** — open the course. The To-Do card shows
   *"Assignments to Grade — 8"*. Click it, work through the eight
   submissions one by one, save each.
2. **Mid-week** — the discussion deadline passes. To-Do card now shows
   *"Discussions to Grade — 12"*. Open the queue, see the *"Replies"*
   column (X / Y format when a minimum is set) so you know at a glance
   who hit the participation requirement and who didn't. Grade the
   ones who met it; reach out to the ones who didn't.
3. **End of class session** — open the **Gradebook**, find the
   *"Class Participation"* (Offline) column, and type in scores for
   the students who spoke up well. Hit *Save All Changes* once.
4. **End of term** — open the Gradebook to see the full grid, spot any
   missing cells, fill in the last few Offline assessments, and verify
   the totals look right before publishing final grades.

## Setting up an assessment plan for a course

Before any of the above works, the course needs Assessment Criteria
defined. From a Course Schedule, click **Course Assessment** to open
the configuration page. Add one row per graded thing in the syllabus:

- Pick the **type** (Quiz / Assignment / Exam / Discussion / Offline).
- For non-Offline types, link the actual activity (the specific Quiz,
  Assignment Activity, etc.).
- Set the **weight** (percentage of the final grade) — or tick
  **Extra Credit** and enter max points, in which case the row counts
  on top of the 100% rather than against it.
- Optionally set a **due date** — used for the To-Do card's "Due Soon"
  list and for marking late submissions.

The total weight of non-extra-credit rows must equal **100** before you
can save. The page shows a running total at the top in red until you
get there.

## Tips

- **Don't grade in the Gradebook by default.** Clicking through the
  per-activity queue gives you the full submission view (the file, the
  rubric, the feedback box, prior comments). The Gradebook is for
  Offline grades, overrides, and end-of-term sweeps.
- **Use Offline liberally.** Anything that lives on a clipboard or in
  your head — attendance, oral exam scores, peer evaluation totals,
  presentation rubric scores — becomes a clean column in the Gradebook
  the moment you add an Offline Assessment Criterion.
- **One Offline row per category.** A single *"Participation"* row
  combining attendance, oral engagement, and group work is fine when
  the syllabus describes it that way. Splitting them into separate
  rows is fine too — students see the breakdown and you can weight
  each piece.
- **Discussion replies count toward "complete," not toward the grade.**
  The minimum-replies setting controls when the discussion is marked
  *complete* on the student's outline and To-Do. The grade itself is
  whatever you enter on the Discussion Submission — you can reward
  participation with the score, deduct for missing it, or use a
  separate Offline assessment if you want to track participation
  apart from the discussion's content.

## Related

- [Discussion Activities](discussions.md) — setup and reply requirements
- [Enrollment](enrollment.md) — who appears in the Gradebook rows
- [Withdrawal](withdrawal.md) — how withdrawn students are represented
- [Graduation Requirements](graduation-requirements.md) — non-course
  evidence that complements graded coursework
