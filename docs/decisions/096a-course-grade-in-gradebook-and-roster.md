# 096a — The course grade in the gradebook and the roster

**Date:** 2026-10-31
**Status:** Accepted 2026-10-31; implemented 2026-10-31 (b0554a7f)
**Amends:** [096](096-weighted-categories-and-dropped-scores.md)
**Related:** 072 (descriptive grading), 081 (fail for absences), p015 (grade projection)

## Context

The gradebook shows every assessment and, since 096, a subtotal per category, but not the
student's grade for the course. An instructor reads it on the Students tab (projected) or not
at all once grades are sent. The current grade that My Status shows is a weighted sum, which
is right on a points scale and wrong on a Descriptive one, where the final grade is a weighted
mean in grade points (072).

## Decision

1. **A Grade column** at the right of the gradebook, after the category subtotals: score and
   letter for each student.
2. **Before Send Grades it is the current grade**, the number My Status shows: missing work
   counts as 0, with 096's drops and excuses. It is the server's, refreshed after saving, not
   recomputed as grades are typed, so it always matches what Send Grades will compute.
3. **After Send Grades, and once a student is failed for absences (081), it is the stored
   result** (`fscore`, `fgrade`) that went to the transcript, marked as final.
4. **Descriptive scales use the mean.** `grade_projection.compute` takes the scale type: on a
   Descriptive scale the current grade is the weighted mean of the graded rows that count, in
   grade points, as Send Grades works it out. This also corrects My Status and Simulate Grades
   there.
5. **The Desk roster on Course Schedule shows it too**, in a Course Grade column beside the
   Grades link, from the same server function as the gradebook, so the two cannot disagree.
6. The projected grade stays on the Students tab. Competency sections keep their own gradebook
   and show no course grade in either place.

## Consequences

Instructors and the registrar see the grade while grading, the same figure students see. After sending,
the column is the transcript's. Typing a score leaves the column unchanged until the save.
