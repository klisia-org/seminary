# 065 — Competency-Based Education

**Date:** 2026-08-28
**Status:** Accepted 2026-08-28 — implementation phased; Phases 1-7a complete, Phase 8 next

## Context

The grading engine is built for **numeric** assessment. A [Grading Scale](../../seminary/seminary/doctype/grading_scale/grading_scale.json) maps a percentage to a grade code; a single [Course Assess Results Detail](../../seminary/seminary/doctype/course_assess_results_detail/course_assess_results_detail.json) cell holds one `rawscore_card` per student per assessment; [Course Schedule Instructors](../../seminary/seminary/doctype/course_schedule_instructors/course_schedule_instructors.json) is the only "who grades this" assignment; and both [`api.grade_thisstudent`](../../seminary/seminary/api.py) and `api.fgrade_this_std` are `if grscale_type == "Points":` with no other calculation path. Qualitative, multi-evaluator, competency-anchored assessment has no home.

A Brazilian seminary running CBTE surfaced what the model cannot express. Their practice, and the variation across the wider CBTE community, gives five gaps:

1. **Course = outcome; competencies live inside it.** Their example: the outcome *"Identity — Self-Leadership"* contains the competencies *Life in Christ*, *Personal Integrity*, *Spiritual Vitality*. Each competency carries a general description plus, per dimension (knowledge / character / craft), a "demonstrated by" descriptor. Nothing in the app models this.
2. **Baseline and final self-evaluation by the student**, both categorical (1 = Not Competent, 2 = Developing, 3 = Competent, 4 = Advanced) and narrative, compared on a radar chart. This school evaluates at the end of each competency; others evaluate once at the end of the program.
3. **More evaluators than we model.** The professor is the *Faculty Mentor*. A *Personal Mentor* grades activities and gives a final assessment, and follows the student across the program rather than sitting in one section. Another school adds a *Vocational Mentor*.
4. **Wide, unsettled variation in scoring.** Some schools take two or three grades per activity; others take one grade per activity plus two or three final grades per competency/dimension. Some report on the same 1–4 scale, averaging the mentors; others sum into a 1–12 scale, and disagree about whether the student's self-evaluation is included in the sum.
5. **Pacing is a pedagogical stance, not a given.** This school argues time-variation per student is unhelpful in communitarian cultures, so they hold a fixed cohort with a fixed mentor. US/Canada schools typically let time vary per student. The school is small, runs on intuition, has no failure/remediation policy yet, and plans to grow.

They also require a **Personal Development Plan** authored by the student at the end of each course.

The constraint that frames the solution: this variation is genuine disagreement among practitioners of a young educational model, not indecision that will resolve. It must be **configuration in Desk**, not branches in the grading engine — and CBE work must converge into the existing `send_grades` / roster / transcript spine rather than running beside it, or every downstream subsystem (attendance failure, course lifecycle, transcripts, course packs) needs a second implementation.

Prior work in the tree: `Grading Scale.grscale_type` gained a `Competency-based education` option and a `Grading Scale Dimensions` child table with a single `dimension` field. Nothing reads either — it is a schema-only stub, and this ADR builds on it.

## Decision

### 1. Grading Scale supplies the level vocabulary and the dimensions

The CBE scale remains the transcript-facing object, and it is the single source of both the proficiency levels and the dimension list. [Grading Scale Interval](../../seminary/seminary/doctype/grading_scale_interval/grading_scale_interval.json) already carries `grade_code`, `threshold`, `grade_description` and `grade_pass`; for a CBE scale `threshold` is the level's numeric value (1, 2, 3, 4), exactly as it already doubles as the GPA point value for `Descriptive` scales in [`gpa._convert_to_gpa_points`](../../seminary/seminary/gpa.py).

`Grading Scale Dimensions` is extended:

| field | type | notes |
|---|---|---|
| `dimension` | Data | reqd (exists) |
| `dimension_code` | Data | reqd, url-safe; the stable key every downstream record stores |
| `dimension_icon` | Attach Image | optional icon shown on charts and tables (Frappe's `Image` fieldtype only *renders* another field; the storage field must be `Attach Image`) |
| `sequence` | Int | display order, e.g. radar axis order |
| `description` | Small Text | what this dimension means school-wide |

`grading_scale.py::validate` gains a `Competency-based education` branch: require at least one dimension, require `dimension_code` unique within the parent, require at least one interval, and require every interval to carry a `threshold`. Per [ADR 023](023-course-and-program-course-lifecycle.md) this validation lives on the parent controller, not the child.

**Blocking prerequisite.** `api.get_grade` and `api.get_gradepass` cache intervals on `frappe.local.grading_scale` **without keying by scale name**, and `get_gradepass` writes the key `get_grade` reads. This is latent today; it becomes a wrong-grade bug the moment a CBE scale and a Points scale appear in one request, which any transcript render guarantees. Key the cache by scale name before anything else here ships.

### 2. Course Competency — the curriculum layer

Because course = outcome, competencies belong to the [Course](../../seminary/seminary/doctype/course/course.json) (the catalog record), alongside the existing `assessment_criteria` weighting template — not to the offering.

**`Course Competency`** — standalone, `autoname: format:{coursecode}-{competency_code}`.

| field | type | notes |
|---|---|---|
| `course` | Link → Course | reqd |
| `competency_code` | Data | reqd, url-safe (`utils.assert_url_safe_code`), unique per course |
| `competency_name` | Data | reqd |
| `sequence` | Int | ordering within the outcome |
| `statement` | Text Editor | general description, optional |
| `dimensions` | Table → Course Competency Dimension | |
| `is_active` | Check | default 1 |

**`Course Competency Dimension`** (child):

| field | type | notes |
|---|---|---|
| `dimension_code` | Data | reqd; options sourced from the course's grading scale dimensions |
| `dimension` | Data | read-only label |
| `demonstrated_by` | Text Editor | reqd — how this dimension is demonstrated for this competency |
| `weight` | Float | optional, for weighted aggregation |

It is standalone rather than a child table on Course because assessment criteria, per-evaluator grades, competency results and development-plan goals all need a **Link** to a specific competency, a Frappe Link field cannot target a child row, and Frappe has no grandchild tables — so the per-dimension descriptors could not hang off an inline competency grid in any case. The Course form surfaces them through the Connections tab, the same way [Course Schedule Chapter](../../seminary/seminary/doctype/course_schedule_chapter/course_schedule_chapter.json) hangs off Course Schedule.

**The course outline gives a competency its time boundary.** [Course Schedule Chapter](../../seminary/seminary/doctype/course_schedule_chapter/course_schedule_chapter.json) gains `course_competency` (Link → Course Competency, optional), so a chapter *is* the delivery of a competency. This does three things at once: the competency's `statement` and its per-dimension "demonstrated by" descriptors render in the outline where the student is actually working; activities inside the chapter default their `course_competency` from it; and — decisively — "end of each competency" becomes a computable event (the chapter's lessons are complete), which is what §3's self-evaluation timing needs. A course whose competencies do not map cleanly onto chapters simply leaves the link blank and falls back to course-level timing.

**One chapter per competency, enforced on the controller.** Gating resolves a competency back to the chapter that delivers it (`cbe._chapter_for_competency`); with two candidates it would pick one arbitrarily and lock the other for reasons nobody could explain, so `CourseScheduleChapter.validate` refuses a competency already mapped in the same section, alongside the existing cross-course guard.

**The link is set from the portal, not only from Desk.** Instructors build outlines in [ChapterModal.vue](../../frontend/src/components/Modals/ChapterModal.vue), so the picker lives there — shown only when `get_competency_context` reports the section is competency-based, offering competencies not already taken by another chapter, and stating what the mapping will do in the framework's actual `content_release_mode`. `api.upsert_chapter` gains an optional `course_competency`: absent means "leave the mapping alone" so a caller that knows nothing about competencies cannot clear one, and an empty string is the explicit unlink.

**A section may set its own release mode, where the school allows it.** `Competency Framework.override_contentrelease` (Check) hands the choice to instructors; `Course Schedule.content_release_override` (Select, blank = follow the framework) holds it, edited in [CourseForm.vue](../../frontend/src/pages/CourseForm.vue) and shown only when both the section is competency-based and the flag is set. Everything reads `cbe.content_release_mode(course_schedule)`, never `framework.content_release_mode` directly.

That resolver re-checks the flag rather than trusting the stored value, so a school that withdraws the permission has it withdrawn everywhere at once — leaving old overrides in force would make the flag a suggestion. The stored value is left alone rather than erased, so restoring the permission restores the sections' choices. `CourseSchedule.validate` refuses a *new* override while the flag is off, and refuses one on a non-competency section, so the two directions agree: nothing silently ignored at the point of entry, nothing silently honoured afterwards.

`api.save_course` writes it first, before the `frappe.db.set_value` calls that make up the rest of that endpoint: those skip validation, so ordering the validated write last would leave them applied while the save reported failure. Its exception path now rolls back and returns the message under `error`, the key the portal actually reads.

The `upsert_chapter` endpoint also gains a role gate. Students hold `write` on Course Schedule Chapter so progress can be recorded against it, so a doctype permission check lets them through — tolerable while a chapter was only a title, not once it carries the mapping that content gating reads, since clearing it would unlock the course. The role set mirrors `canEditOutline` in the portal, so nothing that could edit an outline before is stopped now.

**The chapter↔competency link is also the pacing gate.** This seminary holds the student's hand closely, and wants the outline to open progressively as the student reflects. `Competency Framework.content_release_mode` (§3) governs it, and every mode reads the same chapter mapping:

- **`Per activity (current rules)`** — the default and the only behaviour for non-CBE courses. Nothing changes; existing per-activity availability applies.
- **`Chapter unlocks after previous competency self-assessed`** — chapter *n* stays closed until the self-assessment for chapter *n−1*'s competency is Submitted. The first chapter is always open, since there is no prior competency to reflect on.
- **`Content open, activities locked until previous competency self-assessed`** — the whole outline is readable from day one, but a chapter's graded activities stay locked until the previous competency's self-assessment is Submitted. The gentler variant: a student may read ahead, but cannot be assessed ahead of their own reflection.

Gating is evaluated server-side in `cbe.visible_outline(roster)` and reflected in the outline payload, not merely hidden in the Vue layer — a locked activity must also refuse a submission. Courses with no chapter↔competency mapping fall back to `Per activity` regardless of the setting, which is the same fallback the self-evaluation timing uses.

Because gating means a student who stops reflecting locks themselves out, `stall_escalation_days` on the framework closes the loop: a daily job flags any roster whose next self-assessment has been due longer than that and notifies the student's mentors through the existing trigger machinery ([ADR 044](044-communication-triggers-and-desk-surfaces.md)), alongside the flagged rows appearing on the mentor worklist. Setting it on the framework rather than per course keeps the response time uniform across a program — a student should not have to learn that one course chases them after a week and another after a month. `0` disables escalation.

**No `outcome_statement` on Course.** `Course.description` already exists and, since course = outcome, it *is* the outcome statement. A second prose field would force us to explain a distinction to users that does not exist in their practice, and would invite duplicated authoring. The CBE section on Course is therefore configuration only.

### 3. Competency Framework — the policy layer

The school's pedagogical choices live in one place, versioned, reusable across programs.

**`Competency Framework`** — standalone, `autoname: field:framework_name`.

| field | type | notes |
|---|---|---|
| `framework_name` | Data | reqd, unique |
| `status` | Select | Draft / Active / Retired |
| `supersedes` | Link → Competency Framework | version chain, mirroring `Program Graduation Requirement` ([ADR 012](012-graduation-requirements-architecture.md)) |
| `grading_scale` | Link → Grading Scale | reqd, `link_filters` to `grscale_type = Competency-based education` |
| `evaluators` | Table → Competency Framework Evaluator | |
| **Self-evaluation — program level** | | |
| `program_self_eval` | Check | |
| `program_self_eval_points` | Select | `Start of program` / `End of program` / `Start and end of program` |
| **Self-evaluation — course level** | | |
| `course_self_eval` | Check | |
| `course_self_eval_points` | Select | `Start of course` / `End of course` / `Start and end of course` / `End of each competency` / `Start of course and end of each competency` |
| `self_eval_counts_in_final` | Check | |
| `self_eval_weight` | Float | |
| `mentor_sees_self_eval` | Select | `Always` / `After mentor submits` / `Never` |
| **Activity grading** | | |
| `activity_grading_mode` | Select | `One grade per activity` / `One grade per evaluator` / `One grade per evaluator per dimension` |
| `activity_evaluators_required` | Check | block send_grades when a required evaluator has not graded |
| **Competency verdict** | | |
| `verdict_source` | Select | `Final assessments only` / `Activity grades only` / `Both` |
| `aggregation_method` | Select | `Average` / `Sum` / `Weighted average` / `Highest` / `Lowest` / `Instructor of record decides` |
| `include_self_in_verdict` | Check | |
| `rounding` | Select | `Nearest` / `Down` / `Up` / `None` |
| `report_basis` | Select | `Framework scale` (report 1–4) / `Summed` (report 1–N) |
| `report_max` | Float | read-only; max interval threshold × contributing evaluators |
| **Content release** | | |
| `content_release_mode` | Select | `Per activity (current rules)` / `Chapter unlocks after previous competency self-assessed` / `Content open, activities locked until previous competency self-assessed`; see §2 |
| `stall_escalation_days` | Int | days a student may sit on an unsubmitted self-assessment before their mentor is notified; 0 disables |
| **Cohorts and completion** | | |
| `default_pacing_mode` | Select | `Cohort-paced` / `Self-paced` — the starting pacing for programs adopting this framework; each program may override it (see §5) |
| `program_cohort_source` | Select | `Student Group` / `Discipleship Cohort` / `None`; see §5 |
| `require_pdp` | Check | Personal Development Plan required at end of course |
| `pdp_blocks_completion` | Check | |
| `emit_gpa` | Check | default 0; see §7 |

**Self-evaluation is two independent blocks, not one timing enum.** Program-level and course-level self-evaluation answer different questions and are configured separately so neither picker has to enumerate the other's combinations. Composing them covers the observed practices: the Brazilian seminary is `program_self_eval_points = Start of program` plus `course_self_eval_points = Start of course and end of each competency`; a school that self-evaluates once at each end is `Start and end of program` with `course_self_eval` off; the correlate the user named — start of program, end of each competency — is `Start of program` plus `End of each competency`. "End of each competency" is only selectable when the course's competencies are mapped to chapters (§2); the framework validates this and the UI explains it.

**No `pass_level_code`.** [Grading Scale Interval](../../seminary/seminary/doctype/grading_scale_interval/grading_scale_interval.json) already carries `grade_pass` (Pass/Fail) per level, and `api.get_gradepass` already walks it. A second threshold on the framework would be a place for the two to disagree. Whether a competency is met is read off the interval the aggregate lands in.

`report_basis` plus `aggregation_method` plus `include_self_in_verdict` is exactly the axis on which schools disagree (average on 1–4 versus sum into 1–12, mentors only versus mentors plus student). Making it three fields rather than three code paths is the point of this ADR.

### 4. Evaluators reuse Instructor and Instructor Category

**No new evaluator doctype.** "Faculty Mentor", "Personal Mentor" and "Vocational Mentor" are [Instructor Category](../../seminary/seminary/doctype/instructor_category/instructor_category.json) records. That category already carries `is_instructor_of_record` and an `Instructor Category Rate` child table feeding the payroll/HRMS path ([ADR 010](010-instructor-payroll-hrms-integration.md)) — mentors must be payable exactly like any other categorised instructor, and a parallel evaluator taxonomy would strand them outside that spine. `Course Schedule Instructors` already carries `instructor_category` per assignment.

`Instructor Category` gains `is_competency_evaluator` (Check) and `mentor_scope` (Select: `Course` / `Program`) so the framework's picker filters sensibly. `is_instructor_of_record` resolves the `Instructor of record decides` aggregation method.

**`Competency Framework Evaluator`** (child):

| field | type | notes |
|---|---|---|
| `instructor_category` | Link → Instructor Category | reqd |
| `assignment_source` | Select | `Course Schedule Instructors` / `Program Enrollment Mentor` — reqd; determines how this evaluator is resolved for a student |
| `evaluates` | Data | read-only, set from `assignment_source`: "Every student in the section" or "Only their assigned students" |
| `grades_activities` | Check | |
| `gives_competency_verdict` | Check | |
| `required` | Check | |
| `weight` | Float | default 1 |

The student is not an Instructor, so self-evaluation is *not* an evaluator row — it is the self-evaluation block on the framework. This keeps the Instructor spine meaning "a person the school may pay".

**Per-student persistent mentors, resolved by the system — not by the registrar.** `Course Schedule Instructors` is per-section and cannot express a mentor who follows the student across a program. Making the registrar add every mentor to every section would not scale: with three mentor types and a growing student body, the section's instructor table becomes a mess and drifts out of sync the moment a mentor changes.

So the registrar adds **only course instructors** to a Course Schedule. Mentors are recorded once, on the student:

**`Program Enrollment Mentor`** — child on [Program Enrollment](../../seminary/seminary/doctype/program_enrollment/program_enrollment.json): `instructor` (Link), `instructor_category` (Link), `from_date`, `to_date`, `active` (Check), `change_reason` (Small Text). Rows are appended, never overwritten — the same auditability precedent as `Program Enrollment Status History` ([ADR 030](030-program-status-lifecycle-spine.md)), so a mid-program mentor change leaves a trail.

`cbe.evaluators_for(roster)` derives the evaluator set per student:

1. Framework rows with `assignment_source = Course Schedule Instructors` → match `Course Schedule Instructors` rows on the section whose `instructor_category` equals the framework row's. Same evaluator for every student in the section.
2. Framework rows with `assignment_source = Program Enrollment Mentor` → walk the roster's student to their [Course Enrollment Individual](../../seminary/seminary/doctype/course_enrollment_individual/course_enrollment_individual.json) for that section, follow `program_ce` to the Program Enrollment, and take the `active` mentor rows whose `instructor_category` matches, filtered by `from_date`/`to_date` against the section's dates. Different evaluator per student.

CEI is already the authoritative student↔section link and is already submitted and workflow-governed ([ADR 016](016-payment-gated-cei-lifecycle.md)), so this needs no new join table and no registrar action. A mentor appears in their students' sections automatically, and disappears when the mentor row is closed.

**Report: Program Enrollments by Mentor.** A Frappe query report over `Program Enrollment Mentor`, filterable by instructor, instructor category, program and academic term, listing each mentor's active students with program, current term and status. This is the mentor's own caseload view and the registrar's coverage check — it is the surface that catches an unassigned student before a section starts grading. Phase 2.

### 5. Program binding, pacing, and a real program-course filter

On [Program](../../seminary/seminary/doctype/program/program.json), a CBE section:

| field | type | notes |
|---|---|---|
| `competency_framework` | Link → Competency Framework | its presence *is* "this is a CBE program" |
| `pacing_mode` | Select | `Cohort-paced` / `Self-paced`; hydrated on create from the framework's `default_pacing_mode` (§3) using the override-preserving pattern of `_hydrate_graduation_gpa_default` ([ADR 057](057-graduation-eligibility-floors.md)), **not** `fetch_from` |
| `cohort_failure_policy` | Select | `Repeat competency in place` / `Move to next intake cohort` / `Individual remediation plan` / `Not defined — registrar decides` (default) |

**Self-paced programs may run open-ended sections.** Where cohort-paced schools bound a course by the term, self-paced schools let a student keep working until they reach competency — so a section may legitimately have no end date. [Course Schedule](../../seminary/seminary/doctype/course_schedule/course_schedule.json) gains `open_ended` (Check, permlevel 1 alongside the dates); `c_dateend` becomes `mandatory_depends_on: eval:!doc.open_ended` rather than unconditionally required. The flag is only accepted when the course sits in at least one self-paced competency-based program, so it cannot become a general way around the end date. An open-ended section has no class meetings, so meeting generation and calendar export refuse it explicitly and the attendance policy is forced to `Disabled` — an absence limit derived from an empty meeting list is meaningless. The enrollment and grading windows already degrade correctly: `cs_lifecycle._cs_anchor_dates` simply reports a `None` anchor, which `resolve_window_dates` documents as "no rule, no window".

This also fixes a latent crash: `CourseSchedule.validate_date` compared `c_datestart`/`c_dateend` against the term without null-guarding either operand, raising `TypeError: '<' not supported between instances of 'NoneType' and 'datetime.date'` instead of a validation message whenever a date was absent. Each comparison is now guarded on its own operands.

**The program-course filter.** Today any course can belong to any program. When `competency_framework` is set, `Program.validate` requires each non-disabled `Program Course` row's course to (a) use a `default_grading_scale` equal to the framework's scale, and (b) carry at least one active `Course Competency`. `link_filters` on `Program Course.course` narrows the picker declaratively per ADR 023. This delivers the uniform transcript that motivated putting config on the grading scale, without imposing a global same-scale rule on non-CBE programs.

**The program cohort is an existing grouping, and the school picks which one.** [ADR 064](064-discipleship-cohorts-and-channels.md) deliberately keeps `Cohort` (discipleship, Person-keyed, leader-led) and `Student Group` (course-scoped grading grouping, Student-keyed, mentor-led) apart. A CBE program cohort could reasonably be either: a school that runs cohorts purely as a grading/rostering device wants the Student Group; a school whose cohort *is* its discipleship group — same people, same leader, same formation — wants the Cohort, and would resent maintaining two rosters of the same room. `Competency Framework.program_cohort_source` chooses:

- **`Student Group`** — one group per intake, reused across the program's offerings via the existing `reuse` Check, attached to each section through `Student Group Link`. `Student Group` gains `program` (Link), `intake_term` (Link → Academic Term) and `is_program_cohort` (Check); `Student Group Members` gains `joined_on`, `left_on` and `status` (Active / Moved / Withdrawn).
- **`Discipleship Cohort`** — the program cohort is a [Cohort](../../seminary/seminary/doctype/cohort/cohort.json) whose `Cohort Type.program` points at this program. The bridge already exists in both directions: `Cohort.source_student_group` and `source_course_schedule` are already read-only provenance fields, and `Cohort Membership.course_enrollment` already links a member to their CEI. **Nothing about how Cohorts work changes** — this only automates their creation. Resolution runs Instructor → Person, never the reverse: the mentor is established as always by `Program Enrollment Mentor`, and `Instructor.person` supplies the `Cohort.leader`; members come from the students' CEIs. There is no lookup that can fail on a leader who is not an instructor, because the mentor side is always the origin.
- **`None`** — self-paced programs, or schools that group by section only.

Either way no third grouping doctype appears, and the `Student Group Members` lifecycle fields land regardless so cohort movement is recordable the day the school decides what a failure means.

### 6. The record layer

**`Competency Assessment`** — `autoname: CASMT-.######`. One evaluator's verdict on one competency for one student. Baseline self-evaluation, final self-evaluation, Faculty Mentor assessment and Personal Mentor assessment share this one shape, which is what makes the radar a single query.

| field | type | notes |
|---|---|---|
| `student` | Link → Student | reqd |
| `program_enrollment` | Link → Program Enrollment | reqd |
| `course_schedule` | Link → Course Schedule | reqd |
| `course_competency` | Link → Course Competency | reqd |
| `stage` | Select | `Baseline` / `Final` |
| `evaluator_kind` | Select | `Self` / `Mentor` |
| `instructor` | Link → Instructor | blank when `Self` |
| `instructor_category` | Link → Instructor Category | |
| `status` | Select | Draft / Submitted |
| `submitted_on` | Datetime | |
| `narrative` | Text Editor | the descriptive assessment |
| `ratings` | Table → Competency Assessment Rating | |

**`Competency Assessment Rating`** (child): `dimension_code`, `dimension` (RO label), `level_code` (a `grade_code` from the scale), `level_value` (Float RO, the interval threshold), `narrative` (Small Text).

**`Activity Competency Grade`** — `autoname: ACG-.#######`. One evaluator's level on one activity.

| field | type | notes |
|---|---|---|
| `roster` | Link → Scheduled Course Roster | reqd |
| `student`, `course_schedule` | Link | read-only denorms |
| `assess_criteria` | Link → Scheduled Course Assess Criteria | reqd |
| `course_competency` | Link → Course Competency | fetched from the criteria, or from the chapter (§2) |
| `dimension_code` | Data | blank = whole-activity grade |
| `instructor` | Link → Instructor | reqd |
| `instructor_category` | Link → Instructor Category | |
| `level_code` / `level_value` | Data / Float | |
| `narrative` | Small Text | |
| `graded_on` | Datetime | |

**Activities are graded by mentors only — there is no `evaluator_kind` here.** The framework configures self-evaluation at the competency level, never at the activity level, so a `Self` value on an activity grade would be a state no configuration can produce. Self-evaluation lives entirely in `Competency Assessment`, where `evaluator_kind` does the work and `instructor` is blank. `instructor` is consequently required on every activity grade, which also makes the required-evaluator check in `send_grades` a simple presence test.

[Scheduled Course Assess Criteria](../../seminary/seminary/doctype/scheduled_course_assess_criteria/scheduled_course_assess_criteria.json) gains `course_competency` (Link) and `grading_mode_override` (Select, blank inherits the framework), anchoring each activity to the competency it develops.

**`Assessment Dimension Weight`** — **standalone**, `autoname: format:{assess_criteria}-{dimension_code}`: `assess_criteria` (Link → Scheduled Course Assess Criteria, reqd), `course_schedule` / `course_competency` (read-only denorms), `dimension_code` (Data, reqd), `dimension` (Data, read-only label), `weight` (Float, reqd, default 0).

It is standalone for exactly the reason §2 gives for `Course Competency`: Scheduled Course Assess Criteria is *itself* a child table of Course Schedule, and **Frappe has no grandchild tables**. A `dimension_weights` Table field on it would have been accepted by the schema and then silently stored nothing — which is what a first pass at this actually did, and what the weighted-average tests caught. Weights are reached from the assessment's Connections tab in Desk, and edited inline in the competency gradebook (§9).

**Not every assessment measures every dimension equally.** A reading response is mostly knowledge; a field placement report is mostly craft; a spiritual-formation journal is mostly character. Forcing each to contribute equally to all three would flatten precisely the distinction competency assessment exists to make. So each assessment declares, per dimension of its competency, how much it counts. Weights are relative, not percentages: `60/20/20` and `3/1/1` behave identically, and a weight of `0` means the assessment does not measure that dimension at all and is excluded from it entirely rather than pulling it toward the mean.

An assessment that declares no weights falls back to equal weight across its competency's dimensions, so a school that does not care about this never has to configure it.

**Dimension weights are deliberately *not* multiplied by `weight_scac`.** `Scheduled Course Assess Criteria.weight_scac` is the activity's share of the numeric course grade and must total 100 across the section; it belongs to the percentage spine. If it also scaled competency contributions, an activity's administrative weight in a gradebook would silently distort a formation verdict, and a registrar rebalancing course percentages would move competency outcomes without knowing it. The two axes stay independent: `weight_scac` governs the numeric grade, `dimension_weights` governs the competency verdict.

Note also that there are two distinct weightings, at two different levels, and they compose rather than compete:

- **assessments → dimension**: `Assessment Dimension Weight` (here) — how much each assessment counts toward one dimension's result.
- **dimensions → competency**: `Course Competency Dimension.weight` (§2) — how much each dimension counts toward the competency's overall verdict, used when `aggregation_method = Weighted average`.

**`Competency Result`** — `autoname: CRES-.######`. The persisted rollup per student × course competency; what transcripts and the radar read.

| field | type | notes |
|---|---|---|
| `student`, `program_enrollment`, `course_schedule`, `course_competency` | Link | reqd |
| `dimensions` | Table → Competency Result Dimension | |
| `computed_value` | Float | read-only — dimensions rolled up per the framework rule |
| `override_value` / `override_reason` | Float / Small Text | instructor-of-record override; the reason is required |
| `overridden_by` / `overridden_on` | Link User / Datetime | read-only |
| `final_value` | Float | read-only — the rounded result |
| `final_code` | Data | matching interval grade code |
| `status` | Select | Not Started / In Progress / Competent / Not Yet Competent |
| `decided_on` / `decided_by` | Datetime / Link User | |

**`Competency Result Dimension`** (child):

| field | type | notes |
|---|---|---|
| `dimension_code` / `dimension` | Data | |
| `baseline_value` | Float | from the Baseline self-assessment; the radar's first series |
| `computed_value` | Float | read-only — the weighted average of the assessments, before any edit |
| `override_value` | Float | an editor's replacement for the computed value |
| `override_reason` | Small Text | required whenever `override_value` is set |
| `overridden_by` / `overridden_on` | Link User / Datetime | read-only, stamped on save |
| `final_value` | Float | read-only — the rounded result; the radar's second series |
| `final_code` | Data | read-only — the interval `final_value` lands in |
| `delta` | Float | `final_value` − `baseline_value` |

### 6a. The verdict pipeline: weighted average, then edit, then round

The order of these three steps is a decision, not an implementation detail, and every result record stores each stage rather than only the answer.

1. **Weighted average of the assessments,** per dimension:
   `computed_value(d) = Σ(weight(a,d) × level(a,d)) / Σ weight(a,d)` over assessments `a` with `weight(a,d) > 0`.
   Where `activity_grading_mode` is `One grade per evaluator per dimension`, `level(a,d)` is the grade given for that dimension; under the coarser modes the whole-activity grade stands in for every dimension the assessment weights. Where more than one evaluator graded, their ratings are combined by the framework's `aggregation_method` first, so the multi-evaluator rule is applied once and in one place.
2. **Editable, and recorded as edited.** An evaluator with authority may replace the computed value. `computed_value` is never overwritten — `override_value`, `override_reason`, `overridden_by` and `overridden_on` sit beside it, so the arithmetic the system produced and the judgement a human substituted are both legible afterwards. A verdict that quietly replaced its own inputs would be unreviewable, and in formation assessment the reason for a departure matters as much as the number. `override_reason` is required whenever `override_value` is set.

   Deriving the reported values is therefore a separate step from computing the inputs: `cbe.recompute_finals` runs in `Competency Result.validate` and reads only `computed_value` and `override_value`, while `rollup_competency_result` supplies those inputs and preserves any override it finds. Without the split, an override typed into Desk would be stored next to a stale final value until something else happened to recompute the record.
3. **Then rounding,** per the framework's `rounding` setting. Rounding runs *after* the override, not before: the editor works in the same continuous space the average produced (a considered `2.6`), and the framework decides how that becomes a reported level. Rounding first would force the editor to choose between levels and then round a value that was already a level — discarding the distinction the override was making.

`Competency Result` carries the same four-stage shape at competency level (`computed_value`, `override_value`, `override_reason`, `overridden_by`, `overridden_on`, `final_value`, `final_code`), rolling its dimensions up by `Course Competency Dimension.weight` when the framework aggregates by weighted average. Its `override_value` / `override_reason` replace the single pair sketched in §6.

### 7. Backend convergence

New module `seminary/seminary/cbe.py`, shaped like [`faculty.py`](../../seminary/seminary/faculty.py):

- `framework_for(course_schedule)` — resolves via the roster's `Program Enrollment.program.competency_framework`; returns `None` for non-CBE sections so every call site short-circuits cheaply.
- `evaluators_for(roster)` — the two-branch resolution of §4: section instructors by category, plus per-student mentors walked through CEI → Program Enrollment → `Program Enrollment Mentor`. Every "who may grade this / who still owes a grade" question goes through here.
- `competency_boundaries(course_schedule)` — maps competencies to chapters (§2) and reports which are complete, driving the `End of each competency` self-evaluation trigger.
- `visible_outline(roster)` — applies `content_release_mode` (§2) to the chapter/lesson/activity tree. The submission endpoints call the same function, so a locked activity refuses a POST rather than merely being hidden.
- `aggregate(values, method, weights, rounding)` — the single place the Average / Sum / Weighted / Highest / Lowest variation lives.
- `dimension_weights_for(assess_criteria)` — an assessment's per-dimension weights (§6a), falling back to equal weight across the competency's dimensions when none are configured.
- `weighted_dimension_value(roster, course_competency, dimension_code)` — step 1 of the verdict pipeline: the weighted average across assessments, returned unrounded so the override and rounding stages can act on it in order.
- `rollup_activity_grades(roster, assess_criteria)` — aggregates `Activity Competency Grade` rows and writes the resulting level into the existing `Course Assess Results Detail.rawscore_card` and `graded_card`. **This is the convergence point.** `Gradebook`, `cs_lifecycle.maybe_advance_to_grading`, attendance-failure and `send_grades` keep working untouched.
- `rollup_competency_result(roster, course_competency)` — writes `Competency Result`, running the §6a pipeline in order and preserving any existing override rather than recomputing over it.

Wired in [hooks.py](../../seminary/hooks.py) `doc_events`: `Activity Competency Grade → {on_update: cbe.on_activity_grade_update}`, `Competency Assessment → {on_update: cbe.on_assessment_update}`.

Touch points in existing grading code:

- `api.grade_thisstudent` and `api.fgrade_this_std` gain a `Competency-based education` branch: `fscore` = the framework aggregate, `fgrade` = the matching interval `grade_code`, `fgradepass` = that interval's `grade_pass`. The existing `failed_for_absence` / `fa_code` override still applies.
- **GPA follows `emit_gpa`, wired now.** `gpa._convert_to_gpa_points` gets an explicit `Competency-based education` branch, and `send_grades` sets `Program Enrollment Course.count_in_gpa` from the framework:
  - `emit_gpa = 0` (**the default, and what the Brazilian seminary uses**) — the branch returns `None` *and* `count_in_gpa = 0`, so CBE rows leave the denominator too rather than being silently dropped from the numerator. `pec_finalgradecode` carries the competency verdict code and the transcript prints competency levels.
  - `emit_gpa = 1` — the branch reuses the existing `Descriptive` path verbatim: match `interval.grade_code == pec.pec_finalgradecode` and take `interval.threshold` as the point value, then scale to `Program.basis_for_gpa`. `count_in_gpa = 1`, and `Program.is_weighted` / `Honors Levels` apply unchanged.

  Implementing both arms now costs a handful of lines because the Descriptive path already exists, and it avoids the rework of retrofitting a GPA into a shipped transcript. What is *not* free and stays out of scope: `Program.min_graduation_gpa` and the graduation eligibility floors ([ADR 057](057-graduation-eligibility-floors.md)) are meaningful only under `emit_gpa = 1`; `Program.validate` warns when a CBE program sets a GPA floor with `emit_gpa = 0`, rather than silently never meeting it.
- `send_grades` — extend the pre-flight guard with required-evaluator and development-plan checks alongside the existing "all cells graded" check, and split it as described in §7a.
- [`course_pack/constants.py`](../../seminary/seminary/course_pack/constants.py) — add the new competency fields to the export allowlist so course packs round-trip ([ADR 041](041-course-pack-portable-bundle.md)).

### 7a. Partial finalization: Send Selected Grades, for open-ended sections only

`send_grades` is all-or-nothing and terminal. It refuses to run until *every* active, non-audit roster is fully graded, and when it runs it finalizes everyone, flips the section to `Closed`, and concludes every enrollment in it. For a section with an end date that is exactly right: the term ends, everyone is graded together, and the section closes as one act. **That behaviour does not change.**

It breaks down only on the open-ended sections introduced in §5 — the ones serving a self-paced competency framework, where a student keeps working until they reach competency. There, by design, there is no moment when everyone is done. A terminal-only operation means grades never reach the transcript at all, and one student still working holds every classmate's `Program Enrollment Course` row hostage indefinitely. Graduation candidacy reads those rows, so a classmate who finished can be blocked from graduating by someone who has not — which is the point at which the delay costs the most.

**Decision: separate per-student finalization from section closure, and offer the partial path only where the section is open ended.**

- `finalize_roster(roster)` — internal helper holding the existing per-student block verbatim: `grade_thisstudent`, `fgrade_this_std`, the `Program Enrollment Course` write (`pec_finalgradenum`, `pec_finalgradecode`, `status`), the credit award with its Fail and leveling-course exclusions, and `Scheduled Course Roster.active = 0`. Extracted rather than reimplemented so the two entry points cannot drift.
- `send_selected_grades(course_schedule, rosters)` — whitelisted. **Refuses any section that is not `open_ended`**, then requires the section to be in `Grading`; checks for ungraded cells **among the selected rosters only**; finalizes each; concludes **only those students'** Course Enrollment Individual records; and runs the emphasis-credit, auto-grant-emphasis and GPA recomputation for only their enrollments. It does not touch `workflow_state`.
- `send_grades(...)` — unchanged signature and meaning, and unchanged behaviour for every dated section. Becomes: finalize every roster still `active`, then close the section, conclude the remaining enrollments, and enqueue the aretenic snapshot.

**`open_ended` is the whole gate, and it is the only check.** A section may only be open ended when its course sits in a self-paced competency-based program (§5), which `CourseSchedule.validate_open_ended` already enforces at the source. So testing `open_ended` transitively guarantees the framework and the pacing without `send_selected_grades` re-deriving either. Re-checking the program's `pacing_mode` here would be a second condition that can fall out of step with the first; there is one rule, in one place, and this reads it.

Partial finalization is therefore not a general capability. A dated section — the ordinary case, cohort-paced or numeric — remains strictly all-or-nothing, and the invariant that its grades are finalized in a single act is preserved exactly as today. Nothing about a conventional term changes.

**Idempotency comes free from `active`.** `finalize_roster` acts only on rosters with `active = 1` and clears the flag as its last step, so a student finalized by a partial send is skipped by the later full send. This matters more than it looks: credits are *accumulated* into `Program Enrollment.totalcredits` rather than recomputed, so a second pass over the same roster would silently double a student's credit total. The `active` flag is what prevents that, and the same flag already keeps finalized students out of the "still ungraded" pre-flight count.

**The aretenic snapshot stays on the closing path only.** `attainment.snapshot_offering_on_send_grades` cuts an offering-level attainment record for accreditation; a snapshot taken when half the section is graded would be an auditable claim about an offering that is not finished. Partial sends produce no snapshot.

**Surface.** Row selection and a *Send Selected Grades* action appear **only when the section is open ended** — in the new Competency Gradebook (§9), and in the numeric [Gradebook.vue](../../frontend/src/pages/Gradebook.vue) for an open-ended section that still grades numerically. Everywhere else the gradebook looks and behaves exactly as it does now, with *Send Grades* alone. Showing a disabled *Send Selected* on every ordinary section would advertise a capability that does not apply and invite the question of why it is greyed out; a control that is absent needs no explanation. Where it does appear, *Send Selected* is the ordinary path and closing the section is an administrative act the school takes when it judges the section finished — or never.

**Security gap to close in the same pass.** `send_grades` is `@frappe.whitelist()` with **no role check at all** — no `frappe.only_for`, no permission call — so today any authenticated user, a Student included, can finalize grades, write transcript rows, award credits and close a section. `api.py` already has both the idiom (`frappe.only_for`, used elsewhere in the file) and the constant (`_GRADER_ROLES`). Both entry points get the gate when this split lands.

### 8. Personal Development Plan

**`Personal Development Plan`** — `autoname: PDP-.######`: `student`, `program_enrollment`, `course_schedule`, `roster` (Links, reqd), `status` (Draft / Submitted / Reviewed / Accepted), `reflection` (Text Editor), `goals` (Table), `submitted_on`, `reviewed_by` (Link → Instructor), `reviewed_on`, `mentor_feedback` (Text Editor).

One plan per roster row, enforced on the controller; `student`, `course_schedule` and `program_enrollment` are *derived* from the roster rather than trusted from the caller, so a hand-built record cannot claim to belong to a section the student is not in. Students see only their own plans, through `get_permission_query_conditions` and `has_permission` registered in hooks, the same pair `Competency Assessment` and `Competency Result` already use.

**The student writes; the mentor answers.** `cbe_api.save_development_plan` and `cbe_api.review_development_plan` are separate endpoints, not one write path with a role branch, so a review can never overwrite the reflection it is responding to. Submitting is final for the student, as self-assessment is. `PersonalDevelopmentPlan.vue` serves both: a mentor reaches it with `?student=`, which the server honours only for staff who are an evaluator for that student, and everything the student authored is read-only in that mode.

**`require_pdp` and `pdp_blocks_completion` are deliberately two settings.** The first says the plan is part of the course; the second says the course cannot close without it. Most schools will want the first without the second — asking for a plan is formative, holding a transcript hostage to it is not — so only `pdp_blocks_completion` gates `_assert_pdp_complete`, which runs in both `send_grades` and `send_selected_grades` and names the students rather than reporting a count. A plan still in `Draft` does not satisfy it.

**`Personal Development Plan Goal`** (child): `standard_question` (**Data**, holding the question's `question_key`, optional — *not* a Link: `Standard Development Question` is a child row of Competency Framework and a Frappe Link cannot target one; the key is the stable identifier anyway, which is what the join across four years of plans actually needs), `question_text` (Small Text, denormalised from the prompt on every save so a rewording never leaves stale text above the answer it produced), `course_competency` (Link, optional), `dimension_code` (optional), `goal` (Text Editor, reqd), `action_steps` (Text Editor), `target_date` (Date), `support_needed` (Small Text), `status` (Planned / In Progress / Achieved).

**Each course's plan stands alone.** There is no `carried_forward_from` link and no goal that migrates between plans. A course has its own responsibilities, and a plan that inherits last course's unfinished business turns a formative exercise into an accumulating debt. Continuity is a *reading* concern, not a storage one — §9's aggregate view gives the student and the mentor the whole arc across courses without any plan claiming ownership of another's goals.

**`Standard Development Question`** — child on Competency Framework: `question_key` (Data, reqd, url-safe, unique in parent), `question_text` (Text Editor, reqd, translatable), `sequence` (Int), `active` (Check, default 1).

A school configures the prompts that shape the plan once, on the framework, and every plan in every program using that framework asks the same questions. `Personal Development Plan Goal.standard_question` links a goal to the prompt that produced it, which is what makes the aggregate view coherent: a student can read every answer they have ever given to *"where do you most need to grow in character?"* across four years of courses, and a mentor can read the same. Goals may also be free-standing (`standard_question` blank) so the plan is never a closed form. Deactivating a question stops it appearing in new plans without orphaning historical answers — the same reason `question_key` is stable and separate from the editable text.

### 8a. Development notes — the lifelong-journey problem

Some formation goals — spiritual vitality, besetting sin, vocational clarity — are never "Achieved", and a status field that only offers completion quietly tells a student their real struggles are failures. The `Achieved` state stays, because ordinary goals do complete; what is added is a place for the work that does not.

**`Personal Development Note`** — `autoname: PDN-.#######`: `student` (Link, reqd), `program_enrollment` (Link, reqd), `course_schedule` (Link, optional), `course_competency` (Link, optional), `dimension_code` (Data, optional), `development_plan` (Link → Personal Development Plan, optional), `note` (Text Editor, reqd), `note_date` (Datetime).

Notes are the student's own journal, anchored optionally to a plan, a competency or a dimension, and not tied to a course's completion. They are **not private**: the student's active mentors have read access, granted through Frappe document permissions resolved by `cbe.evaluators_for` rather than by flipping any file or field public (per [ADR 043](043-multichannel-communication-system.md)'s handling of scoped access). Accountability is the point of the mentoring relationship, and the UI says so plainly at the point of writing — a journal whose readership the writer has to guess is worse than one with no readers at all.

**Who counts as a mentor is `cbe.mentors_of_student`,** the same two sources as `evaluators_for` composed at *student* scope rather than section scope — a note need not belong to any course, so a roster-scoped question cannot answer it. Program mentor rows count while active and in date; section instructors count only while the student is still actively rostered in that section, because a professor who taught them two years ago is not a mentor now. `cbe.mentees_of` is the inversion, and drives both the mentor's student selector and the list-view scope.

Nothing is granted, ever: `get_permission_query_conditions` materialises the mentee list per request and `has_permission` re-resolves per document, so access ends the moment a mentor row closes or a roster goes inactive. Mentors read only — `has_permission` returns False for any non-read permission even though they hold the Instructor role, and `save_development_note` re-checks on the endpoint, because a role-granted write would otherwise slip through.

### 9. Frontend — parallel pages, converging backend

The numeric [Gradebook.vue](../../frontend/src/pages/Gradebook.vue) is not extended with competency fields. A spreadsheet is the wrong metaphor for narrative, multi-evaluator, dimension-scoped assessment. New pages, routed like `CourseAssessment` / `CourseOutcomeReport` (lazy import, `props: true`, no route-level role meta), gated on `framework_for(section)` being non-null using the optional-feature idiom of [CLOCoveragePanel.vue](../../frontend/src/components/CLOCoveragePanel.vue) — silent `onError`, `watch(..., {immediate: true})`.

| Page | Route | Audience |
|---|---|---|
| `CompetencyGradebook.vue` | `/competency-gradebook/:courseName` | mentors — two panes: roster with per-competency progress rings; the selected student's competency panel showing competency → dimension rows, a level chip group per evaluator, the "demonstrated by" descriptor inline, and a narrative field |
| `CompetencySelfAssessment.vue` | `/courses/:courseName/self-assessment/:competency?` | student — level picker per dimension with the descriptor as guidance, plus narrative; which self-evaluations are open, and when, comes from `program_self_eval_points` / `course_self_eval_points` via `cbe.competency_boundaries` |
| `CompetencyProfile.vue` | `/competency-profile` | student — the radar, dropdown: baseline versus student final (default), baseline x mentor final, student final x mentor final; per competency and per dimension, with the narrative timeline. A section tables each narrative per competency/dimension - with student/faculty mentor/... and what they said and the classification |
| `PersonalDevelopmentPlan.vue` | `/courses/:courseName/development-plan` | student, plus a mentor review/sign-off mode — the framework's standard questions render as the plan's prompts, with free-standing goals allowed alongside |
| `SelfDevelopmentPlans.vue` | `/development-plans` | student — the aggregate arc across every course (see below) |
| `SelfDevelopmentPlans.vue` (mentor mode) | `/development-plans/:student` | mentor — the same view for one of their students, reachable from the worklist |

**`SelfDevelopmentPlans.vue` is the answer to the lifelong-journey problem**, and the reason §8 needs no `carried_forward_from`. It is a reading surface over records that stay independent:

- **By question.** Every answer the student has given to each `Standard Development Question`, in course order — four years of answers to the same prompt, read down the page. This is where growth becomes visible without any goal being copied forward.
- **By competency and dimension.** Goals and notes grouped by what they were about, cutting across courses.
- **By course.** The plans as authored, unchanged.
- **Journal.** `Personal Development Note` entries, composable from anywhere in the view, anchored to whatever the student was looking at. The composer states, at the point of writing and not in a settings page, that the student's mentors can read these — the disclosure belongs where the decision to write is made.

The mentor mode is the same component with a student selector populated from `cbe.evaluators_for` inverted — the same resolution behind the worklist and the Program Enrollments by Mentor report, so a mentor sees exactly their own students and nothing else. Read-only: mentors respond through `mentor_feedback` on a plan, not by editing a student's journal.

Also:

- **The course outline is where competencies become visible to the student.** Where a chapter carries a `course_competency` (§2), the lesson list renders the competency's `statement` and its per-dimension "demonstrated by" descriptors as a header panel, with the dimension icons from §1 — so the student reads *what they are being formed into* in the same place they do the work, and the "end of each competency" self-evaluation prompt appears there when the chapter completes. Under a gating mode, a locked chapter or activity shows *why* it is locked and links to the self-assessment that unlocks it; a lock the student cannot explain is worse than no lock.
- A "Competency Assessment" entry in [CourseCardOverlay.vue](../../frontend/src/components/CourseCardOverlay.vue), behind the existing instructor guard plus the CBE check.
- A "Competency Assessments Due" tab in [FacultyWorklist.vue](../../frontend/src/pages/FacultyWorklist.vue), which is already capability-driven and whose `Faculty Capability.routes_to` already offers a `Mentor` value ([ADR 059](059-seminary-departments-and-faculty-capabilities.md)). Its rows come straight from `cbe.evaluators_for` inverted — the same resolution that means a mentor never had to be added to a section now means their worklist populates itself. Personal Mentors get a caseload with no new plumbing and no registrar action.
- Competency-level rendering in `CourseStatus.vue` and `Grades.vue`, and the **Program Enrollments by Mentor** report (§4) reachable from the mentor's worklist as well as from Desk. On a competency section `CourseStatus.vue` *replaces* the numeric panels rather than adding to them — a level of 3 shown as "3 / 100", with a weight, a class median and a percentile beside it, is a claim the student has no way to correct. `Grades.vue` shows the competency verdicts under their course row, and reaches `CompetencyProfile.vue` from there rather than from the sidebar, so the entry point appears only for students who have something to see.
- A **Course Competency Coverage** report (Desk, ref doctype `Course`) listing every competency-based course with its active competency count and the gaps that make it unassessable: a competency-based scale with no competencies, all competencies deactivated, a competency missing a dimension descriptor, and — in the other direction — competencies stranded on a course whose scale was switched away from competency-based. Reachable from the Course list's menu, carrying its academic-unit filter across. The count cannot be a list column: `Course Competency` is a separate doctype, so a column would need a denormalised counter on `Course` maintained by hooks.

**Radar chart:** echarts 5.6 is already an installed frappe-ui dependency. `RadarChart.vue` builds on `echarts/core` directly rather than wrapping frappe-ui's `ECharts` component, and registers only `RadarChart`, `TooltipComponent`, `LegendComponent` and `SVGRenderer`. The wrapper cannot be used as-is: it calls `init(el, 'light')` once and never re-initialises, so dark mode ([ADR 003](003-dark-mode-and-visual%20standardization.md)) has no way in, and there is no prop to pass a theme. Colours are read from the app's own CSS custom properties (`--ink-gray-7`, `--outline-gray-2`, …) at draw time and redrawn on the `useTheme` ref, so the chart follows the palette rather than carrying a second one.

An `echarts` branch is added to `manualChunks` in `frontend/vite.config.js`, which otherwise lumps all of `node_modules` into `vendor`. Note what this does and does not buy: frappe-ui's barrel (`src/index.ts`) statically re-exports `ECharts.vue`, which statically imports the full `echarts` bundle, so **echarts already shipped eagerly on every page before this ADR** — it sat inside the `frappe-ui` chunk (2.88 MB). The branch splits it into its own 1.03 MB chunk that caches and parses independently, the same rationale as the existing `editorjs` branch; it does not make it lazy. Making it lazy would mean stopping the barrel from pulling `ECharts.vue`, which is a frappe-ui change, not ours.

### 10. Aretenic bridge — a seam, not a build

Seminary keeps `required_apps = []` and never imports aretenic. `Course Competency.competency_code` is url-safe for the same reason `Course.coursecode` is, so aretenic can align a competency to a PLO and pick it up in `attainment.snapshot_offering_on_send_grades`, which `send_grades` already enqueues. Gate server-side on `utils._aretenic_enabled()` and client-side on `has_aretenic`. Documented as a seam; deferred.

### 11. The course-scoped surfaces — assessment configuration and the CBE gradebook

Sections 1-10 settle the *programme* scope: the framework, who evaluates, how ratings become a verdict, the arc across courses. The **course** scope was left half-wired, and the seam shows in four places. The principle that fixes them: **Course Schedule is the hub for everything course-scoped**, and every competency setting that belongs to one section must be reachable from the portal pages that section owns — [CourseAssessment.vue](../../frontend/src/pages/CourseAssessment.vue), [Gradebook.vue](../../frontend/src/pages/Gradebook.vue), [CourseOutline.vue](../../frontend/src/components/CourseOutline.vue) — not only from Desk.

**11a. Weights do not apply to a competency section, and must stop being demanded.** `Scheduled Course Assess Criteria.weight_scac` expresses a percentage contribution to a numeric final grade. A competency section has no such number: `cbe.rollup_activity_grades` writes a *level* into `rawscore_card`, and the final verdict comes from `Competency Result`, not from a weighted sum. Yet `CourseSchedule.validate_assessment_criteria` throws unless the weights total 100, and `CourseAssessment.vue` disables Save until they do — so a competency section cannot save its assessments at all without inventing weights that nothing reads. Both gates become conditional on `cbe.framework_for(section)` being None, and the weight column is hidden rather than shown empty.

**11b. One derived mode drives the whole page.** Everything competency-specific on `CourseAssessment.vue` — which columns exist, which validations run, which sub-editors open — keys off a single computed mode rather than scattered checks, so the page cannot end up half in one world. The mode is **derived** from `get_competency_context(section).is_cbe`, not stored as a new `assessment_mode` field: a stored mode could contradict the grading scale, and the scale is already the authority on whether a section is competency-based (§1). What the mode adds, for a competency section:

- **`course_competency` per assessment.** Already on the doctype since Phase 2, reachable only from Desk. Without it in the portal an instructor cannot say which competency an activity demonstrates, and every downstream roll-up has nothing to aggregate.

  **The chain must agree: chapter -> lesson -> assessment.** An assessment reaches its lesson through its linked activity, and the lesson names its chapter, and the chapter names the competency (section 2). Where that chain resolves, the assessment's `course_competency` is **defaulted from it** and **refused if it contradicts it** -- an activity sitting in the chapter that delivers *Personal Integrity* cannot be filed under *Spiritual Vitality*, because the outline has already told the student which competency they are working on there. An assessment whose activity is in no chapter, or in a chapter with no competency, is free to name one itself; that is how a course-wide capstone stays possible. Validation lives on the `Course Schedule` controller with the rest of the assessment-criteria checks, per [ADR 023](023-course-and-program-course-lifecycle.md), and reads the lesson through the same index `utils.get_assessments` already uses -- `Scheduled Course Assess Criteria.lesson` is computed on read, not stored, so there is nothing to trust.
- **Per-assessment dimension weights.** `Assessment Dimension Weight` (§6a) is the record that lets one assessment be knowledge-heavy and another character-heavy. It exists, `cbe.dimension_weights_for` reads it, and nothing writes it outside Desk. It renders as an expandable row under each assessment, one weight per dimension of the section's scale, defaulting to equal weights.
- **`grading_mode_matrix` per assessment** — a grid of **evaluator category x dimension**, each cell on or off, so a single activity can be graded per-dimension inside a course that is **also** graded per-evaluator, and so an instructor can *opt out* of a cell: the faculty mentor may be unable to judge character on a written exam while the personal mentor can.

  **Shape first, then cells.** `activity_grading_mode` (framework) and `grading_mode_override` (assessment) answer *what shape the grid has* — one grade for the whole activity, one per evaluator, or one per evaluator per dimension. Only the last two have axes to switch on and off, and "one grade per activity" has no evaluator or dimension axis at all, so it cannot be expressed as cells. The matrix therefore refines the shape rather than replacing it.

  Stored as **`Assessment Grading Matrix`** — standalone, because `Scheduled Course Assess Criteria` is itself a child table and Frappe has no grandchildren (the same constraint that made `Assessment Dimension Weight` standalone): `assess_criteria` (Link, reqd), `course_schedule` and `course_competency` (denormalised), `instructor_category` (Link, reqd), `dimension_code` (Data, reqd), `dimension` (read-only label), `graded` (Check). Rows exist only where an instructor has made an explicit choice; **absence means "follow the shape"**, so a course that never opens the grid stores nothing and behaves exactly as it does today.

  **An opt-out is not a zero, and this is the part that must not be got wrong.** A cell switched off is *not applicable*, not *missing* and not *failed*. Three existing behaviours change accordingly: `cbe.missing_required_evaluators` must not report an opted-out cell as owed; `cbe.weighted_dimension_value` must drop it from the average rather than contribute a value; and the submission surface (11c) must not render a picker for it. A dimension every evaluator has opted out of has no value for that assessment at all — it simply does not participate, and the competency's other assessments carry it.

**11c. Submissions are graded in dimensions, on the qualitative scale.** The four submission grading surfaces (quiz, assignment, exam, discussion) offer a numeric score box. On a competency section they must instead offer one level picker per dimension of that assessment, labelled with the competency's own "demonstrated by" descriptor, plus the narrative field — the same shape `cbe_api.save_activity_grade` already accepts. Which pickers appear follows `activity_grading_mode`: one for the whole activity, one per evaluator, or one per evaluator per dimension.

**11d. The gradebook needs a competency shape, not a numeric grid.** `Gradebook.vue` renders students x assessments x score. For a competency section that grid is meaningless, and it is currently what an instructor sees. Gated on the framework, the section instead gets a **bird's-eye matrix**: rows are students; columns nest **competency -> assessment -> evaluator category (`grades_activities = 1`) -> dimension**, holding a level rather than a score. Below it, the final competency verdicts from evaluators with `gives_competency_verdict = 1`.

The faculty mentor is the arbiter of grades but is not the only person grading, so each student's row carries an icon naming their Personal Mentor on hover — resolved from `cbe.evaluators_for`, the same resolution that put the mentor in the section without a registrar. This is the whole-course view; the existing `CompetencyGradebook.vue` per-student panel becomes its detail pane rather than the only way in.

**11e. Self-assessment is prompted when the framework says, not on every chapter.** `course_self_eval_points` already distinguishes *start of course*, *end of course*, *end of each competency* and *start of course and end of each competency*, but the outline offers the prompt on every mapped chapter regardless of the setting or of the student's progress — so a school configured for "start of course and end of each competency" gets greeted at the *beginning* of each competency and never at the start of the course. The prompt points are derived from the setting instead:

| setting contains | prompt |
|---|---|
| *Start of course* | one Baseline prompt at the top of the outline, before any chapter |
| *End of each competency* | a Final prompt on a chapter once its lessons are complete |
| *End of course* | a Final prompt once the whole outline is complete |

Chapter completion is the same lesson-completion data `get_course_outline(progress=True)` already returns, so this needs no new state. A competency whose self-assessment is not yet due shows its descriptors without a call to action, which is the point of the panel anyway.

## Rejected: Grading Scale as the CBE configuration home

The initial instinct was to make the grading scale the key config and force every course in a program onto the same scale, buying transcript uniformity.

1. It couples pedagogy to a notation. A scale answers "what does a 3 mean"; it cannot answer "who evaluates", "are mentor grades averaged or summed", or "is the student's self-evaluation in the total".
2. Grading Scale is submittable and shared across programs. Versioning a school's aggregation policy would mean amending a document that non-CBE courses also depend on.
3. Forcing one scale across all of a program's courses is a heavy global rule to buy something a targeted `Program.validate` check buys precisely.

The half that survives: the scale still owns the level vocabulary *and* the dimension list, so transcripts stay uniform and there is exactly one place the 1–4 codes are defined.

## Rejected: a dedicated program-cohort doctype

ADR 064 already draws the line between `Cohort` (discipleship, Person-keyed, ADR 042 identity spine) and `Student Group` (course-scoped grading grouping, Student-keyed, mentor-led). A CBE program cohort is one or the other depending on how the school runs it, which is why §5 makes it a framework toggle rather than a ruling. What it is *not* is a third thing: another grouping doctype would fragment rostering across three models, give the frontend three ways to ask "who is in this group", and force a school whose cohort genuinely *is* its discipleship group to maintain the same roster twice. Three fields on `Student Group`, three on `Student Group Members`, and one Select on the framework do the work.

## Consequences

- A school configures its entire CBTE stance in Desk — competencies, dimensions, evaluators, aggregation, reporting basis, pacing — and the portal follows. Adding the *Vocational Mentor* school is one Instructor Category and one framework row, no code.
- Mentors stay inside the Instructor / Instructor Category spine, so ADR 010 payroll, ADR 059 capabilities and ADR 062 unit membership all cover them for free. Cost: the student self-evaluation cannot be an evaluator row and is modelled separately on the framework — two configuration surfaces for what a user may perceive as one list of "who evaluates".
- Because activity grades roll into `Course Assess Results Detail`, the course lifecycle, attendance failure, `send_grades`, course packs and the registrar's tooling need no CBE awareness. Cost: `rawscore_card` now holds a value that is a *level*, not a percentage, for CBE sections — anything reading it without checking `grscale_type` will misinterpret it. The Points-only guards in `grade_thisstudent`, `fgrade_this_std` and `scheduled_course_roster.validate_score` become the enforcement points.
- `Course Competency` being standalone rather than a child table costs a nicer Desk authoring experience (a separate list rather than an inline grid on Course) and buys referential integrity everywhere a competency is referenced. Frappe's lack of grandchild tables made the inline grid impossible regardless.
- **The registrar's workload does not grow with the number of mentor types.** Sections carry course instructors only; mentors are recorded once per student and resolved through CEI. Cost: the mentor↔section relationship is derived rather than stored, so an upstream data problem (a missing CEI, a mentor row with a stale `to_date`) surfaces as "no evaluator found" at grading time rather than at assignment time. The Program Enrollments by Mentor report exists to catch that before a section starts grading, and `send_grades` names the missing evaluator rather than failing generically.
- One chapter↔competency mapping serves three purposes: the descriptors render in the outline, "end of each competency" becomes computable, and content gating has something to gate on. Cost: a course that skips the mapping silently loses both the timing trigger and the gating modes, falling back to course-level timing and per-activity rules — so the feature is only as good as the outline authoring, and the Desk form must say so.
- Content gating is enforced in `cbe.visible_outline` on the server, so the submission endpoints gain a guard they did not have. Cost: a new class of support question ("why can't I open chapter 3?"), mitigated by making the lock explain itself and link to the unlocking self-assessment; and a student who stops reflecting stalls indefinitely, which `stall_escalation_days` notifies but does not resolve.
- Per-assessment dimension weights let a school say what each piece of work actually measures, and storing computed value, override and rounded result separately means a verdict can always be explained after the fact. Cost: a third weighting concept in a system that already has `weight_scac` and `Course Competency Dimension.weight`, and three fields where a naive design would have one. The Desk form has to make the distinction obvious or authors will conflate the two weights.
- Splitting finalization from closure is what makes open-ended sections reach a transcript at all, and stops a student who has finished being held back by one who has not. Confining it to `open_ended` sections keeps every dated section's all-or-nothing guarantee intact, so no conventional term changes behaviour. Cost: an **open-ended** section in `Grading` may hold a mix of finalized and unfinalized students, and `workflow_state` does not express that — the roster's `active` flag is the only record of who is done. Anything reasoning about completion from the section's state alone will be wrong for those sections, and their gradebook has to show the distinction clearly or an instructor will not know who is still outstanding.
- Open-ended sections make self-paced programs workable, and fix a real `TypeError` on the way. Cost: `c_dateend` is no longer unconditionally required, so every consumer of it becomes a place a `None` can reach. The ones that exist today are handled — meeting generation, calendar export, window resolution — but new code must not assume a section ends.
- GPA is a framework toggle wired on both arms from the start, so a school that later wants one does not force a transcript rewrite. Cost: with the default `emit_gpa = 0`, a school running both CBE and conventional programs sees `Program Enrollment.current_gpa` populated for some students and not others, and honors levels do not apply to CBE students. That is pedagogically correct and will still read as a gap in the registrar UI until the transcript work lands.
- Development plans stay per-course and independent, with continuity supplied by a reading surface rather than by links between plans. This keeps each plan a closed, reviewable artifact and avoids goals accumulating across four years into a debt ledger. Cost: continuity now depends entirely on `SelfDevelopmentPlans.vue` and on schools actually configuring standard questions — a framework with no questions gives the aggregate view nothing to align on, and it degrades to a chronological list.
- `Personal Development Note` is explicitly mentor-readable, granted by document permission through `cbe.evaluators_for` rather than by loosening any field or file. Cost: this is genuinely sensitive pastoral content in a system that also holds disciplinary records, and a mentor's read access must revoke cleanly the moment their `Program Enrollment Mentor` row closes. The permission check must resolve at read time, never be cached onto the note.
- The parallel frontend means two grading experiences to maintain and to document. That is deliberate: the alternative — conditional fields inside the numeric gradebook — produces a page that serves neither model well.
- Fixing the `get_grade` / `get_gradepass` cache key is now on the critical path. It is a latent correctness bug today and a guaranteed one once two scale types coexist in a transcript render.

### Open questions

1. **What happens when a student fails in a cohort-paced program?** The school does not know: do groups shrink, merge, change mentors? This ships as `cohort_failure_policy = "Not defined — registrar decides"` with `Student Group Members` lifecycle fields in place so whatever they choose is recordable. Revisit when they have grown enough to need the rule.
2. **Does `report_basis = Summed` belong on the transcript, or only in the portal?** A 1–12 summed score is an internal aggregation artifact; printing it on a transcript alongside a 1–4 competency verdict may confuse receiving institutions. Deferred to the transcript work.
3. **`emit_gpa = 1` interacts with graduation floors in ways we have not modelled.** The GPA arithmetic is wired (§7), but `Program.min_graduation_gpa`, honors bands and the eligibility floors of [ADR 057](057-graduation-eligibility-floors.md) were designed against percentage scales; a four-point competency scale compresses the distribution enough that existing floor values would not transfer. Revisit when a school actually asks for it.
4. **Who may override a competency result?** §6a records *that* an override happened and by whom, but not who is entitled to make one. The obvious candidate is the instructor of record, which `Instructor Category.is_instructor_of_record` already identifies; whether a Personal Mentor should be able to override a dimension they graded is a question about authority in the mentoring relationship, not about software. Shipped as: any evaluator with `gives_competency_verdict` may override, and the record says who did.
5. **Can a sent grade be un-sent?** No — and partial sending makes the question sharper, because sending early and often is now the normal rhythm rather than a single end-of-term act. Reversing would have to unwind a `Program Enrollment Course` row, subtract accumulated credits, reactivate the roster and re-open the enrollment, and `send_grades` has never had that. Until it does, *Send Selected Grades* is as final per student as *Send Grades* is per section, and the UI must say so before confirming.
6. **Is `stall_escalation_days` enough of a response to a stalled student?** It notifies the mentor. It does not withdraw, flag academically, or open a hold. Whether a persistent stall should reach [ADR 030](030-program-status-lifecycle-spine.md)'s status spine is the same question as the failure policy in (1), and waits on the same answer.
7. **Who else may read a development note, and for how long?** Mentors, resolved live, is the shipped answer. A former mentor loses access when their row closes; whether a program director, a registrar handling a disciplinary matter, or the student's next mentor should see historical notes is a policy question no school has yet posed to us. Deliberately not modelled — widening this later is easy, narrowing it after staff have read things is not.

### Phasing

1. Scale hardening — the cache-key fix, `Grading Scale Dimensions` extension (including `dimension_icon`), CBE validation.
2. Config layer — `Competency Framework` and evaluator child, `Course Competency` and dimension child, the `Course Schedule Chapter` competency link, `Instructor Category` flags, Program binding and the program-course filter, `Program Enrollment Mentor`, and the Program Enrollments by Mentor report.
3. Record layer and convergence — `Activity Competency Grade`, `Competency Assessment`, `Assessment Dimension Weight`, `Competency Result` and its dimension child, `cbe.py` (including the section 6a pipeline), hooks, the `grade_thisstudent` / `fgrade_this_std` / `gpa` (both `emit_gpa` arms) branches, and the section 7a split of `send_grades` into `finalize_roster` + `send_selected_grades` + `send_grades`, with the missing role gate on both entry points.
4. Portal — self-assessment, competency gradebook, mentor worklist tab, competency panels in the course outline, and row selection plus Send Selected Grades in both gradebooks.
5. Content release — `cbe.visible_outline`, the submission-side guard, lock explanations in the outline, and the `stall_escalation_days` job.
6. Radar and transcript — `RadarChart.vue`, `CompetencyProfile.vue`, CBE rendering in `CourseStatus` and `Grades`.
7. Personal Development Plan — `Standard Development Question` on the framework, plan + goal doctypes, `PersonalDevelopmentPlan.vue`, `send_grades` guard.
7a. Development notes and the aggregate arc — `Personal Development Note` with mentor read permissions resolved at read time, `SelfDevelopmentPlans.vue` in both student and mentor modes.
8. Cohort pacing — `program_cohort_source`, Student Group program fields and member lifecycle, Cohort auto-creation from mentors.
10. Course-scoped surfaces (section 11) — the weight gates, the derived assessment mode with competency, dimension weights and grading-mode override in `CourseAssessment.vue`, dimension grading on the four submission surfaces, the CBE gradebook matrix, and self-assessment prompt timing. Sequenced before 8: a competency section cannot currently save its assessment criteria at all.
9. Deferred — aretenic bridge; the failure/remediation policy once the school decides.
