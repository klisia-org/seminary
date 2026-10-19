# 090 — CBE sections: grading starts, and the class is sent, in the portal

**Date:** 2026-10-19
**Status:** Accepted 2026-10-19

## Context

A numeric section enters Grading on its first saved grade and is sent from the Gradebook. A
competency section does neither: its levels reach the result cards without the save hook, so it
waits in Enrollment Closed for Begin Grading on Desk, and the portal offers only Send Grades for
Selected, which is for open-ended sections. A cohort-paced section can be closed only from Desk.

## Decision

1. **A recorded activity level starts Grading**, through the same check a numeric grade uses.
2. **Competency Assessment gets Send Grades** for a section with an end date while it is in
   Grading, shown to the same people as Send Grades for Selected. It calls the existing send, so
   every gate (ungraded work, required evaluators, development plan, absence decisions) holds.
3. **A blocked send names what blocks it.** An assessment with no competency cannot be graded,
   so it is named first; then each ungraded student and assessment. The numeric "fill in 0"
   message does not apply to levels. The page keeps the message until it is dismissed.

## Consequences

Cohort-paced and self-paced competency sections are both run from the portal, and the two send
buttons never appear together. Desk's Begin Grading and Send Grades stay as fallbacks.

Saving a lesson's content now files its assessments on the chapter's competency, as moving a
lesson already did (ADR 079 §8). An activity added to a lesson after its assessment was created
had been left unfiled, so it could not be graded.
