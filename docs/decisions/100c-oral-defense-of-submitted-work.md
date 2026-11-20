# 100c — Oral defense of submitted work

**Date:** 2026-11-19
**Status:** Proposed
**Parent:** [100](100-oral-assessment.md)
**Related:** 095 (rubrics)

## Context

An exegesis paper shows what a student can write, not what they understand, and today it may not
be theirs at all. Detectors of machine-written text are unreliable and unfair to non-native
writers. A short viva asks something they cannot fake: explain your reading of the text, defend
this claim, why this source. Doing it for every paper by hand does not scale; questions drawn
from the paper itself do.

## Decision

1. **`oral_defense` on Assignment Activity**, with `defense_questions` (default 3),
   `defense_answer_s` (default 120) and `defense_follow_up` (check). Only for text-bearing types
   (PDF, Document, Text), whose text is already extracted into `plagiarism_text`.
2. **Questions are written when the paper is submitted.** The `questions` step reads the extracted
   text and the rubric and returns questions, each tied to a passage, with what a good answer would
   address. The student sees none of them in advance. The instructor may see, edit or replace them
   before the student starts, and may write questions by hand when no step is provided.
3. **The defense runs under 100a §2's conditions**: one question at a time, short reading time,
   timed recording, one take. With `defense_follow_up`, after each answer the `follow_up` step may
   ask one more question on what the student just said; if it returns none, or does not answer
   within 20 seconds, the defense moves on.
4. **Due.** The defense opens on submission and is due `defense_due_days` (default 3) after it, or
   the assignment's due date if later. A paper without its defense is *Incomplete*; 082's late
   policy applies to the defense like any other part.
5. **It is graded through the rubric.** A criterion may be flagged `from_defense`; the panel and
   moments read the defense transcript for it, the paper for the others. Schools that want the
   defense to weigh more give those criteria more weight (095 §3).
6. **Consistency is an observation, not a verdict.** The `consistency` step notes where the
   defense shows, or fails to show, command of the paper's argument, terms and sources. Only the
   instructor sees it. It never says the paper was machine-written, never changes a grade and is
   never sent to the student; a concern goes through the school's academic integrity process.

## Consequences

- Every paper can be defended in a few minutes of the student's time and of the instructor's.
- Outsourcing a paper becomes costly: the student must still explain it, aloud, unprepared.
- Students anxious about speaking, or with a speech disability, need 100 §9's written alternative.
- A live defense with the instructor needs no recording (100d §9).
- Open: reusing this for culminating projects (024).
