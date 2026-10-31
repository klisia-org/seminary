# 096 — Weighted categories, dropped scores and excused assessments

**Date:** 2026-10-31
**Status:** Accepted 2026-10-31
**Delivers:** LMS-ASM-04 (Yes)
**Related:** 081 (excused absences), 082 (due dates and late policy), 095 (rubrics)

## Context

Each Scheduled Course Assess Criteria row carries its own `weight_scac`, a percent of the final
grade, and the rows must total 100. A syllabus says "Quizzes 20%, Papers 40%, Final 40%, lowest
quiz dropped". Today the instructor divides 20% by the number of quizzes by hand, re-divides when
a quiz is added, and cannot drop one at all. 082 deferred excusing a student from one assessment
because the freed weight had nowhere defined to go. Canvas (assignment groups), Moodle (grade
categories), Brightspace and Blackboard all handle this, and instructors check it in demos.

## Decision

1. **Categories are optional, per section.** `Scheduled Course Assess Category`, a new child
   table on Course Schedule's Grade Setup tab: `category_code`, `title`, `weight` (Percent) and
   `drop_lowest` (Int, default 0). A section with no categories keeps today's behaviour exactly.
   Once a section has one, every row that isn't extra credit must name a `category_code`, and
   category weights must total 100 instead of row weights. Extra credit rows stay outside
   categories, as today. Points and Descriptive scales only; competency sections have no weights
   (065 §11a), so the table is hidden there.
2. **Inside a category, row weights follow the 095 rule.** A typed `weight_scac` is that row's
   fixed percent *of its category*; blank rows share what is left evenly. Five quizzes with no
   weights each count 20% of the category, and adding a sixth needs no arithmetic. The table
   shows each row's resulting percent of the final grade. One weighting rule across rubrics and
   gradebook was chosen over Canvas's "weight by points": our rows are percents, not points.
3. **Drop the lowest N per category.** A student's lowest `drop_lowest` rows in a category, ranked
   by percent of the row's maximum after the late deduction (082), leave that student's grade. A
   row flagged `never_drop` (Check) is never dropped, as in Canvas. Ties drop the earlier due
   date. `drop_lowest` must leave at least one droppable row. Drop highest (Moodle) is not
   offered for now: it is rare, and can be added beside `drop_lowest` if a school asks.
4. **Excuse one student from one assessment** (082's deferred item). `excused` (Check) and
   `excused_reason` on Course Assess Results Detail, set by course staff or the registrar, never
   by the student. An excused row leaves that student's grade like a dropped one and does not
   count toward `drop_lowest`. When 081 marks a meeting Excused, the existing dialog that offers
   a due-date override also offers "Excuse from this assessment".
5. **Freed weight goes back where it came from.** For each student, the rows still counting in a
   category share its weight by rule 2, recomputed. If nothing counts in a category, its weight
   spreads over the other categories in proportion to theirs. In a section without categories,
   an excused row's weight spreads over the other rows in proportion. Ungraded rows: the current
   and projected grades (`grade_projection`) drop among graded rows only. At Send Grades an
   ungraded row counts as 0, as today, and can be dropped.
6. **One function computes it, everyone reads it.**
   `seminary.seminary.gradebook_weights.effective_weights(roster)` returns each row's weight for
   that student, or 0 with a reason (dropped, excused). `_fgrade_this_std`, `grade_projection`
   and the Gradebook all call it. `maximum_score` and `score` on Course Assess Results Detail
   become its stored output, refreshed for the student whenever one of their grades, an excuse or
   the section's categories change. Send Grades freezes them, as with 082.
7. **The template import copies categories,** each row's `category_code` and `never_drop`.
   Excuses are not copied: they belong to that section's students.
8. **Where it lives in the app.**
   - **CourseAssessment.vue:** a *Categories* panel beside the Late policy panel. When categories
     exist, the assessment table is grouped under a header per category showing its weight and
     drop rule, instead of a new column (082 rejected more columns). The weight column reads
     "% of category" and the row's share of the final grade shows beside it.
   - **Gradebook.vue:** a subtotal column per category. A dropped cell is greyed, with "Lowest of
     5 Quizzes, dropped" on hover. An excused cell shows "EX". The cell menu gets *Excuse* /
     *Remove excuse*.
   - **Student grade pages:** grades grouped by category; dropped and excused rows are marked and
     say they don't count.
   - **Desk:** the categories table and the row fields on Grade Setup; `excused` on the roster's
     result rows, for the registrar.

**Rejected: categories on the Course master.** Course Assessment Criteria already seeds row weights
for a new section, and categories could ride along. But 082 kept policies per section because one
course serves intensive and 12-week sections. The template import carries them instead.

**Rejected: Moodle's aggregation methods** (mean, median, natural, highest). Weighted mean is what
syllabi state; the others add a setting nobody here has asked for.

## Consequences

Instructors enter the syllabus as written, and adding an assessment no longer breaks the 100%
total. Excuses and drops give accommodations a home without hand-edited grades. The cost is that
a row's weight now differs between students, so every place that reads `maximum_score` or `score`
must accept per-student values; a student's grade can move when a different assessment is graded.
Open: whether the Course master should seed categories later, and a school-wide default
`drop_lowest`, both waiting on the Course Schedule type 082 mentions.
