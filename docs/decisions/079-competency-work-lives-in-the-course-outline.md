# 079 — Competency work lives in the course outline

**Date:** 2026-09-24
**Status:** Accepted 2026-09-24 — implemented 2026-09-24 (branch `adr079-cbe-outline`; browser pass on potestas, owner validation pending)
**Implementation notes:**
- **Decision 3.** Deleting a chapter that holds reflection lessons is refused too.
- **Decision 5.** Students can list only their own Self rows through the generic list API. The profile radar plots only complete series, because echarts draws a missing value at the centre.
- **Decision 6.** `save_mentor_assessment` refuses anyone who gives the student no verdict. A submission is found by activity and section when `course_assess` is blank.
- **Decision 8.** A template import replaces an untouched scaffold, then re-scaffolds.
- **Decision 2.** Sections that predate this are scaffolded by the `adr079_scaffold_reflection_lessons` patch. A section that becomes competency-based after creation is scaffolded then, if it has no reflection lessons yet: its course joins a competency programme, or its scale switches.
**Amends:** ADR 065 sections 2 (content release modes), 9 (student entry points), 11b (the chapter chain) and 11e (self-assessment prompts)
**Relates to:** [ADR 041](041-course-pack-portable-bundle.md) (course packs)

## Context

[ADR 065](065-competency-based-education.md) built the CBE records but left the student's path to them bolted on. A self-assessment is reached through My Status (a withdrawals-and-grades page), then a competency list, then a form. The Development Plan can block grades from being sent, yet it appears only on My Status and never in the outline. The §11e outline prompts appear only at certain moments, so there is nowhere to go back to. Students never see a mentor's assessment in the course. The only place that shows it is `/competency-profile`, which is buried under Transcripts and ungated. Mentors cannot submit one from the app anyway: `save_mentor_assessment` has no caller. On the instructor side there are two problems:

- The gradebook detail prints `INST-00006` where it should show the instructor's name.
- An assessment filed on a competency by hand, then moved into another chapter, gets stuck behind a disabled dropdown that reads "Select option".

## Decision

1. **Reflection is lesson content, and the policy places it.** Two new Editor.js tools, `selfAssessment` and `developmentPlan`, sit beside `quiz` and `exam` in `getEditorTools`.
   - Each block resolves its competency from its lesson's chapter when it renders, so it stores no competency.
   - Self-assessment lessons exist only when `course_self_eval = 1`, and development-plan lessons only when `require_pdp = 1`. Frappe keeps a dependent field's stored value after its parent Check is cleared, so `course_self_eval_points` and `pdp_blocks_completion` can hold stale options. Every reader, on the server and on Desk, tests the parent Check first and never the dependent value alone.
   - Where a reflection goes, and at which stage, follows `course_self_eval_points`:
     - *Start of course*: a Baseline lesson opens the first chapter and covers every competency.
     - *End of each competency*: each chapter ends with a Final lesson.
     - *End of course*: one Final lesson closes the last chapter.
   - When `require_pdp` is set, the course's last lesson holds a `developmentPlan` block. It is badged as required when `pdp_blocks_completion` is set.

2. **A competency section is scaffolded from its competencies.** When a CBE section is created, the system creates one chapter per active Course Competency, already mapped to it, each holding its reflection lesson. The first chapter can hold two reflection lessons (Baseline and Final), and so can the last (Final and Development Plan). The scaffold is skipped where a course-pack import has already supplied it.

3. **Generated lessons are governed, not just generated.** A new read-only Check, `Course Lesson.autocreated`, marks them. On such a lesson an instructor may:
   - change the title;
   - add text around the block.

   The server refuses deleting the lesson, moving it out of its position, and removing or swapping its block. Any of those would contradict the policy the framework sets. The check sits on the lesson controller and on the delete and move endpoints, so neither the portal nor Desk can get round it.

4. **The lesson is the student's surface.**
   - The outline drops its ad-hoc prompt banners.
   - A lock explanation links to the self-assessment lesson.
   - The icon and badge follow the block type.
   - Once the mentor's assessment is visible to the student, a "Mentor feedback" badge appears on the reflection lesson.
   - Submitting the block marks the lesson complete.
   - My Status keeps a read-only competency summary that links into the lessons.
   - The standalone routes stay for deep links and mentor mode.

5. **Students see the mentor's view when every mentor has spoken.** A new field, `Competency Framework.student_sees_mentor_eval`, mirrors the existing `mentor_sees_self_eval`. It takes *After all mentors submit* (the default) or *On submit*.
   - *After all mentors submit* is judged per competency and stage: once every required mentor evaluator has submitted, the student sees all of their views together.
   - It does not wait for grades to be sent. A CBE course often allows fresh demonstrations and alternative assignments, so sending can be far off.
   - Once visible, the self-assessment block shows each mentor's level and narrative beside the student's own, per dimension.
   - The same rule gates `get_competency_profile`.
   - Neither this view nor the profile radar has yet been seen with real data. Both get a design pass and a browser review before they are considered done.

6. **A mentor assessment is due work, like any assessment to grade.**
   - It falls due for a student and competency once the student has submitted every assessed activity of that competency, and the Final self-assessment too where one is required.
   - It then appears in each mentor's To-Do: on the course cards (`CourseCardToDo.vue`, beside `get_assessments_tograde`), on the course's own pages, and in the Faculty Worklist, which already lists it.
   - The form lives in the "By student" pane of the competency gradebook, calls `save_mentor_assessment`, and is built on one `CompetencyLevelPicker.vue`, extracted from the self-assessment page and shared with the block.

7. **Release modes say what they mean, and are offered only when they can work.**
   - `Per activity (current rules)` is renamed `Ungated`, and stored values are patched.
   - The two gated modes depend on a self-assessment at the end of each competency. That exists only when `course_self_eval = 1` and `course_self_eval_points` is one of the two options (of five) that include it. The Desk form filters the gated modes out otherwise, and the controller refuses the combination. Clearing `course_self_eval` on a framework in a gated mode is refused too, instead of leaving the gate pointing at nothing. Each refusal names its reason and the way out, for example: "Chapters unlock only after a student's self-assessment at the end of each competency, so self-assessment cannot be turned off while Content Release is set to a gated mode. Set Content Release to Ungated first." The same wording covers choosing a `course_self_eval_points` option that has no end-of-competency assessment.
   - Gating starts at chapter 2. Chapter *n* unlocks after the Final self-assessment of chapter *n − 1*. Chapter 1 is never gated, and a Baseline gates nothing.

8. **The chapter chain needs maintenance only on import.** The scaffold maps every chapter before any activity is authored, so an assessment takes its competency from its chapter from the start. The case of filing it by hand and then moving it no longer arises. What remains:
   - A course pack imported into an already scaffolded section merges into the scaffold chapters by competency instead of duplicating them, and re-derives its assessments' competencies once.
   - A move between two mapped chapters re-derives as part of the move.
   - The assessment page loads the stored competency. It dropped that value before, which is what produced "Select option".

9. **Evaluators are named, and missing ones are structured.**
   - `get_student_competency_detail` returns `instructor_name`.
   - `missing_required_evaluators` returns records instead of preformatted strings.
   - The worklist matches instructors by equality, not by substring. A substring match confuses `INST-00006` with `INST-000061`.

## Rejected: generated lessons an instructor may delete or move

This option would have given instructors full ownership, with the Coverage report as the safety net. It was rejected because every deletion or move breaks the framework's policy: a missing Final lesson silently removes a gate and the prompt that goes with it. A report catches that after students have already been affected, whereas a refusal at the time of the edit prevents it.

## Rejected: an automatic outline row with no lesson

This option had real merit: an instructor has nothing to forget to author. It was rejected for two reasons. The instructor could not frame the reflection. And the row would be a second kind of outline item beside lessons, which is the patchwork this decision removes.

## Consequences

The outline becomes the one place a student does competency work, and the framework, not the instructor, decides where reflections sit. The costs:

- Instructors lose the freedom to restructure a competency section's reflection lessons, which is the point.
- The scaffold is built once and does not follow later policy changes. Changing `course_self_eval_points` on a live section leaves its lessons as they were, and the Coverage report flags the mismatch.
- Import into a scaffolded section becomes a merge, the one place the chapter chain still needs care.
- Renaming a release mode needs a data patch.

### Phasing

A. Instructor fixes: the assessment page's load, decisions 8 and 9. Also carried here, though it has nothing to do with competencies: a free or ungated enrollment is submitted straight to `Submitted` in `CourseEnrollmentIndividual.on_submit`, which rosters the student but never calls `waitlist.recount`. Its section's stored `enrollments` therefore stays at 0. Fix: recount there, and a patch to recount every section.
B. Framework vocabulary: the release-mode rename, patch, Desk filter and validation; `student_sees_mentor_eval`.
C. The mentor To-Do item and form, the visibility gate, the shared level picker, and a design pass on the mentor view and the radar.
D. The two blocks, `autocreated` and its guards, scaffolding, import merge and outline cleanup.
