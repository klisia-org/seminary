# 100a — Oral answers in exams

**Date:** 2026-11-19
**Status:** Accepted
**Parent:** [100](100-oral-assessment.md)

## Context

Exam questions are Open Questions answered in a Text Editor (Exam Question Result `answer`). An
oral exam needs the same questions answered aloud, under exam conditions: the student should not
read the question ahead, script an answer and read it out, or record ten takes. The instructor
grades each answer as today, question by question, but from audio.

## Decision

1. **`response_mode` on Exam Question**: *Written* (default), *Oral* or *Student chooses*. An exam
   may mix written and oral questions.
2. **Exam conditions.** An oral question shows `prepare_s` (default 30) seconds of reading time,
   then recording starts by itself and stops at `max_answer_s` (default 180) or when the student
   stops. There is no pause. `takes` (default 1) sets how many attempts a student has; only the
   last is kept and graded, and the number used is recorded. Oral answers in an exam must be
   recorded live; uploading a file is refused.
3. **Where the answer lives.** The Oral Recording (100 §2) points at the Exam Question Result. The
   result's `answer` holds the transcript text once `transcribe` has run, so the existing grading
   page and question-level outcome maps keep working unchanged.
4. **Grading.** The grading page plays the audio beside the transcript; clicking a line seeks to
   it. Points stay per question. Rubrics attach to activities, not questions (095 §2), so suggested
   moments are tagged to the question instead of a criterion.
5. **"Question by question" exams** (`qbyquestion`) cannot go back to an oral question once it is
   answered.

## Consequences

- An instructor can turn one question of an existing exam into an oral one with a single field.
- Time limits and single takes make an oral answer hard to script, but not impossible to coach;
  this is a deterrent, not proctoring.
- There are no per-question rubrics - same as text questions; `prepare_s` counts toward the exam's `duration`.
