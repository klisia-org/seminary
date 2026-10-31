# 095 — Rubrics on assignments and discussions

**Date:** 2026-10-30
**Status:** Accepted 2026-10-30; implemented 2026-10-30
**Delivers:** LMS-ASM-03 (Yes)
**Related:** 021 (inline submission rendering), 082 (due dates and late policy)

## Context

Instructors grade Assignment and Discussion submissions with one number and a comment. Schools
expect an analytic rubric: criteria down the side, performance levels across the top. In most
systems the instructor designs the levels, writes every cell and splits the points, so rubrics are
slow to build and every course grades on a different frame. A dean wants one frame students
recognise everywhere; an instructor wants to write only what is particular to the assignment.

## Decision

1. **The school owns the frame.** `Rubric Scale` (Seminary Manager, Program Chair): a name, an
   `is_default` flag and `levels` (`Rubric Scale Level`): `label`, `description`, `percent` (the
   share of a criterion earned at that level, for example 100 / 85 / 70 / 50 / 0) and one level
   flagged `meets_expectations`. A school may keep several scales; once a scale has graded a
   submission it is read-only, and changes go into a new scale.
2. **The instructor writes the criteria.** A `Rubric` belongs to one activity (`activity_doctype`
   + `activity`, Assignment Activity or Discussion Activity) and names a `scale` (the default is
   preselected). `criteria` (`Rubric Criterion`): `criterion_code`, `title`, `description` and
   `weight` (Float, optional). Optional per-cell wording goes in `cells`
   (`Rubric Cell`: `criterion_code`, `level`, `descriptor`); an empty cell shows the scale's
   description. A flattened grid, as in 058, since Frappe has no grandchild tables.
3. **We do the math.** Weights are free numbers. Left blank, criteria weigh the same; if they don't
   sum to 100, the editor says they will be rescaled to a total of 100 and shows each criterion's
   resulting share beside its weight. Weights are stored as typed; a criterion's share is its weight
   over the total. A student's grade is Σ share × level percent of the section's maximum grade, the
   scale every assignment and discussion grade already uses, so all criteria at the top level give
   exactly that maximum. Fixed
   emphasis steps (Low / Normal / High) were rejected: they block the uneven splits some
   assignments need, and every request to allow one becomes a support ticket.
4. **One rubric per activity; reuse by copying.** *Copy from…* fills a new rubric from any the
   instructor can see. After the first graded score the rubric is locked; editing creates a new
   version for the same activity, and earlier scores keep theirs. A shared rubric linked from many
   activities was rejected: one edit would silently split them.
5. **Scores are their own records.** `Rubric Score`: `submission_doctype`, `submission`, `rubric`,
   `criterion_code`, `level`, `percent`, `comment`. Child rows on the submission were rejected: the
   grading pages save the whole submission and would overwrite rows the rubric panel wrote (the
   Activity Competency Grade precedent). Once every criterion has a level, `grade` is derived on each
   save and the score box is hidden; extra credit, fudge points and late penalties (082) still
   apply on top.
6. **Students see the rubric** on the activity before submitting, and their levels and comments once
   the grade is released.
7. **No rubrics on competency or descriptive sections.** An activity belongs to a course, not a
   section, so the rubric stays attached; the grading panel stands down there, as the numeric box
   already does. The competency framework's proficiency scale is not reused as a rubric scale: one
   judges a competency over time, the other a single piece of work.
8. **Hooks and a read API for other apps.** Seminary names no outcome:
   - `seminary.seminary.rubrics.criterion_scores(scheduled_assess_criteria)` returns
     `[{student, criterion_code, share, percent, meets_expectations_percent}]` for graded
     submissions;
   - `rubric_scored` (list of dotted paths): called with the submission after its rubric scores are
     saved;
   - `rubric_replaced` (list of dotted paths): `(activity_doctype, activity, old, new)` whenever an
     activity's rubric is saved or removed (`old == new` for an edit in place);
   - `rubric_criterion_labels` (list of dotted paths): `(activity_doctype, activity) ->
     {criterion_code: [label]}`, shown as chips beside each criterion.

## Consequences

- LMS-ASM-03 is a Yes for assignments and discussions. A rubric can be a list of titled criteria and
  nothing else.
- Every course grades on frames the dean approved, and "meets expectations" means the same thing
  across courses.
- Instructors cannot invent levels; a school that wants another frame adds a scale. They can weigh
  criteria however they like without making the numbers add up.
- Open: Offline criteria (presentations, oral exams), rubric import from Canvas/Moodle, and a
  department bank of rubrics to copy from.
