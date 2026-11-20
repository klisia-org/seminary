# 100b — Recorded peer conversations and talk time

**Date:** 2026-11-19
**Status:** Proposed
**Parent:** [100](100-oral-assessment.md)
**Related:** 097 (discussions, student groups)

## Context

Graded discussions (097) are written threads. A seminar, a mock counselling session or a
case-study debate is spoken, among several students, and the instructor cannot listen to every
group. To grade it they need to know who said what and when, and how much each student took part,
without a person timing it by hand.

## Decision

1. **Oral Activity**, a new course activity beside Assignment and Discussion Activity: `title`,
   `prompt`, `mode` (*Individual* or *Conversation*), `rubric` (095), `max_duration_s`,
   `allow_upload`, the steps chosen (100 §5) and, for *Conversation*, `group_size` and student
   groups as in 097. *Individual* covers a recorded sermon outline or a reading, outside an exam.
2. **Oral Activity Submission**, one per student, as every activity has one per student, so grades,
   due dates (082) and the gradebook work as they do. A conversation has one Oral Recording shared
   by every member's submission; each submission points at it through `recording`.
3. **Who records.** Any member of the group starts the recording on one device; the others are
   named as present before it starts. With `allow_upload`, a file recorded elsewhere (a phone in a
   classroom) may be uploaded instead, and its `started_at` is the upload time, marked as such.
4. **Expected speakers** are the members present. They go to `diarize` as the number of speakers,
   which makes the split far more reliable than guessing the count.
5. **Labelling speakers.** `diarize` returns *Speaker 1…n*. A person links each label to a student
   by listening to a short sample of each; students in the group may do it before submitting, the
   instructor may correct it. A step that can name speakers itself may propose the link, still
   shown as *Suggested*. Unlinked speech (a visitor, the instructor) stays under its label.
6. **Talk time.** From the labelled segments: seconds spoken, share of the conversation, number of
   turns and longest turn per student; overlapping speech counts for both. Shown to the instructor
   as a bar per student and on each student's own submission; never to classmates.
7. **Talk time is not a grade.** It is never written into a score. A rubric criterion may be about
   participation; the instructor still chooses the level.

## Consequences

- Instructors can grade group work they did not attend, and see at a glance who dominated or stayed
  silent.
- Diarization errors land on a person's record; labelling stays human-confirmed, and a student who
  disputes their share can ask the instructor to relabel.
- Recording from a virtual meeting is 100d.
- Open: whether students see the whole group's breakdown;
  a minimum talk share as an optional requirement.
