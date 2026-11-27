# 100 — Oral assessment

**Date:** 2026-11-19
**Status:** Accepted 2026-11-20; implemented 2026-11-20 (002b797c, ae6062c2, 856df137)
**Children:** [100a](100a-oral-answers-in-exams.md) (oral answers in exams),
[100b](100b-recorded-peer-conversations.md) (recorded peer conversations),
[100c](100c-oral-defense-of-submitted-work.md) (oral defense of submitted work),
[100d](100d-capture-from-virtual-meetings.md) (capture from virtual meetings)
**Related:** 021 (timestamp comments), 082 (individual due dates), 092 (hooks for other apps),
095 (rubrics), 097 (discussions)

## Context

Every graded activity in Seminary is written: exams, assignments, discussions. Ministry is mostly
spoken: preaching, teaching, counselling, defending a reading of a text in front of people. A
written answer is also the easiest thing for a student to hand to a chatbot. Schools want students
to answer out loud, talk with each other on the record, and defend what they wrote. Grading audio
is slow, so the instructor needs a transcript, timestamps, who spoke when, and the passages worth
grading, but the grade must stay theirs.

## Decision

1. **Three ways to be assessed orally**, each in its own child record:
   - an oral answer to an exam question (100a);
   - a recorded conversation among students, with each person's talk time (100b);
   - an oral defense of a submitted paper, with questions drawn from it (100c).
2. **One record for every recording.** `Oral Recording`: `reference_doctype` + `reference_name`
   (the Exam Question Result, Oral Activity Submission or Assignment Submission it belongs to),
   `audio` (a private File), `started_at` and `ended_at` (server time), `duration_s`, `language`,
   `status` (*Recorded → Processing → Ready*, or *Failed*) and `recorded_by`. Its products live
   beside it, not inside the submission, so a grading page that saves the submission cannot
   overwrite them (the 095 §5 precedent):
   - `transcript`: JSON segments `[{start, end, speaker, text, words?}]`. Segments are not child
     rows: an hour of talk is thousands of them;
   - `Oral Speaker` (child): `label` (*Speaker 1*), `student`, `talk_s`, `turns`, `longest_turn_s`;
   - `Oral Moment` (own records): `start`, `end`, `criterion_code` (095), `note`, `source`
     (*Instructor* or *Suggested*), `state` (*Suggested*, *Kept*, *Dismissed*).
3. **Recording happens in the browser.** The portal records with MediaRecorder and uploads in
   chunks while it records, so a dropped connection loses seconds, not the answer. Upload of a file
   is allowed only where the child record says so (100b, a class recorded on another device).
   Audio is a private file readable by the student, the section's instructors and staff.
4. **Processing is a list of steps, each optional.** Seminary names the steps and what each takes
   and returns; it does not perform the AI ones. An app installed on the site provides a step
   through the `oral_steps` hook, `{step: "dotted.path"}`:

   | Step | Takes | Returns |
   |---|---|---|
   | `transcribe` | audio, language | segments with start, end and text (words optional) |
   | `diarize` | audio, segments, expected speakers | a speaker label on each segment |
   | `moments` | transcript, rubric criteria, prompt | suggested moments with criterion and reason |
   | `questions` | submitted text, rubric, count | defense questions with what a good answer covers |
   | `follow_up` | question, answer transcript | one probing question, or none |
   | `score_suggestions` | transcript and/or text, rubric | per-criterion suggested levels, from a panel |
   | `consistency` | paper text, defense transcript | an observation for the instructor |

   Talk time is computed by Seminary from the labelled segments; it is arithmetic, not a step. A
   step's path returns at once and later calls `seminary.oral.step_done(recording, step, result)`,
   because audio work is slow. Several steps may come from one app or from different apps.
5. **The instructor chooses the steps per activity**, from the steps the site provides. The school
   may turn a step off for everyone in Seminary Settings (`oral_steps_allowed`), so an instructor
   is never offered what the school's policy forbids. With no app providing a step, oral work still
   runs: the instructor listens, leaves timestamp comments (021) and marks moments by hand.
6. **The grade is the instructor's.** No step writes a grade, a `Rubric Score` or a comment a
   student can see. Suggestions show as *Suggested* until the instructor keeps, edits or dismisses
   them. A kept moment becomes a Timestamp comment (021) on the submission, so students see it the
   way they see any timestamp comment once grades are released.
7. **Students are told, not asked.** The activity states, before it starts, that it is recorded,
   who will hear it, which steps will run on it and how long the audio is kept, and a recording
   indicator stays visible while it records. There is no individual confirmation, as in Zoom or
   Teams: taking part in a recorded activity is the school's policy to set, in its syllabus or
   handbook. Asking each student to confirm was rejected: it blocks a shared recording on one
   absent click and adds nothing the notice does not already say.
8. **Retention.** Seminary Settings `oral_audio_retention_days` (default 365) counts from the day
   the course's grades are sent (084). The daily job then deletes the audio and keeps the
   transcript, speakers and moments, which are the evidence behind the grade. A pending grade
   appeal or a hold keeps the audio. This governs Seminary's copy only: a copy a meeting provider
   keeps (100d) follows the school's settings there.
9. **Accommodations.** An instructor may let one student answer in writing instead, per activity,
   in the same per-student override table as 082's individual due dates.

## Consequences

- Oral work becomes gradable at the speed of reading, with every claim tied to a timestamp.
- Seminary carries no AI provider, model or prompt; an app supplies the steps and its own
  governance. A school with none still gets recording, playback and timestamp grading.
- Audio is heavy: chunked upload, private files and a retention job are required on day one.
- Open: video (sermon delivery already uses YouTube, 021); whether students may re-record before
  submitting outside exams; a transcript editor for the instructor. Capture from a virtual meeting
  is 100d.
