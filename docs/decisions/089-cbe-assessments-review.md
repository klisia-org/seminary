# 089 — CBE gradebook: Assessments review

**Date:** 2026-10-19
**Status:** Accepted 2026-10-19

## Context

A competency section's gradebook shows the levels recorded (Overview) and one student at a time
(By student), but not which work is waiting. An instructor answering a student's question about
one submission has no direct way to it: the course To-Do lists owed verdicts, not ungraded work.

## Decision

1. **A third gradebook tab, Assessments review**, with one row per student per assessment mapped
   to a competency. It is grouped by assessment, or by student on request.
2. **Submitted** shows the latest submission's date and links to that submission's page, where the
   competency grading panel already lives. A row without one reads Not submitted.
3. **One column per grading evaluator category.** A cell shows the level given, or a count of the
   dimensions graded so far, with each level on hover. In "One grade per activity" the grade spans
   the row. A category with no evaluator for that student, or switched off for the assessment,
   reads as not applicable.
4. **Overdue.** With Aretenic installed, a submitted row not fully graded turns red once it has
   waited longer than its Feedback Turnaround (days).
5. **Read-only**, and scoped to the students the viewer may see, as the other tabs are.

## Consequences

Grades are paired with submissions by student and assessment, since a grade row does not name its
submission. A resubmission therefore shares the earlier grades. Assessments not mapped to a
competency are left out, as on Overview.
