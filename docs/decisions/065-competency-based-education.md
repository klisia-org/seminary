# 065 — Competency-Based Education

**Date:** 2026-08-28
**Status:** Accepted 2026-08-28 — implementation phased; Phase 1 in progress

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
| `pacing_mode` | Select | `Cohort-paced` / `Self-paced`; hydrated on create from the framework using the override-preserving pattern of `_hydrate_graduation_gpa_default` ([ADR 057](057-graduation-eligibility-floors.md)), **not** `fetch_from` |
| `cohort_failure_policy` | Select | `Repeat competency in place` / `Move to next intake cohort` / `Individual remediation plan` / `Not defined — registrar decides` (default) |

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

**`Competency Result`** — `autoname: CRES-.######`. The persisted rollup per student × course competency; what transcripts and the radar read.

| field | type | notes |
|---|---|---|
| `student`, `program_enrollment`, `course_schedule`, `course_competency` | Link | reqd |
| `dimensions` | Table → Competency Result Dimension | |
| `final_value` | Float | aggregate per the framework rule |
| `final_code` | Data | matching interval grade code |
| `status` | Select | Not Started / In Progress / Competent / Not Yet Competent |
| `decided_on` / `decided_by` | Datetime / Link User | |
| `override_value` / `override_reason` | Float / Small Text | instructor-of-record override |

**`Competency Result Dimension`** (child): `dimension_code`, `dimension`, `baseline_value`, `final_value`, `delta`, `final_code`. `baseline_value` is copied from the Baseline self-assessment; that pair is precisely the radar's two series.

### 7. Backend convergence

New module `seminary/seminary/cbe.py`, shaped like [`faculty.py`](../../seminary/seminary/faculty.py):

- `framework_for(course_schedule)` — resolves via the roster's `Program Enrollment.program.competency_framework`; returns `None` for non-CBE sections so every call site short-circuits cheaply.
- `evaluators_for(roster)` — the two-branch resolution of §4: section instructors by category, plus per-student mentors walked through CEI → Program Enrollment → `Program Enrollment Mentor`. Every "who may grade this / who still owes a grade" question goes through here.
- `competency_boundaries(course_schedule)` — maps competencies to chapters (§2) and reports which are complete, driving the `End of each competency` self-evaluation trigger.
- `visible_outline(roster)` — applies `content_release_mode` (§2) to the chapter/lesson/activity tree. The submission endpoints call the same function, so a locked activity refuses a POST rather than merely being hidden.
- `aggregate(values, method, weights, rounding)` — the single place the Average / Sum / Weighted / Highest / Lowest variation lives.
- `rollup_activity_grades(roster, assess_criteria)` — aggregates `Activity Competency Grade` rows and writes the resulting level into the existing `Course Assess Results Detail.rawscore_card` and `graded_card`. **This is the convergence point.** `Gradebook`, `cs_lifecycle.maybe_advance_to_grading`, attendance-failure and `send_grades` keep working untouched.
- `rollup_competency_result(roster, course_competency)` — writes `Competency Result`.

Wired in [hooks.py](../../seminary/hooks.py) `doc_events`: `Activity Competency Grade → {on_update: cbe.on_activity_grade_update}`, `Competency Assessment → {on_update: cbe.on_assessment_update}`.

Touch points in existing grading code:

- `api.grade_thisstudent` and `api.fgrade_this_std` gain a `Competency-based education` branch: `fscore` = the framework aggregate, `fgrade` = the matching interval `grade_code`, `fgradepass` = that interval's `grade_pass`. The existing `failed_for_absence` / `fa_code` override still applies.
- **GPA follows `emit_gpa`, wired now.** `gpa._convert_to_gpa_points` gets an explicit `Competency-based education` branch, and `send_grades` sets `Program Enrollment Course.count_in_gpa` from the framework:
  - `emit_gpa = 0` (**the default, and what the Brazilian seminary uses**) — the branch returns `None` *and* `count_in_gpa = 0`, so CBE rows leave the denominator too rather than being silently dropped from the numerator. `pec_finalgradecode` carries the competency verdict code and the transcript prints competency levels.
  - `emit_gpa = 1` — the branch reuses the existing `Descriptive` path verbatim: match `interval.grade_code == pec.pec_finalgradecode` and take `interval.threshold` as the point value, then scale to `Program.basis_for_gpa`. `count_in_gpa = 1`, and `Program.is_weighted` / `Honors Levels` apply unchanged.

  Implementing both arms now costs a handful of lines because the Descriptive path already exists, and it avoids the rework of retrofitting a GPA into a shipped transcript. What is *not* free and stays out of scope: `Program.min_graduation_gpa` and the graduation eligibility floors ([ADR 057](057-graduation-eligibility-floors.md)) are meaningful only under `emit_gpa = 1`; `Program.validate` warns when a CBE program sets a GPA floor with `emit_gpa = 0`, rather than silently never meeting it.
- `send_grades` — extend the pre-flight guard with required-evaluator and development-plan checks alongside the existing "all cells graded" check.
- [`course_pack/constants.py`](../../seminary/seminary/course_pack/constants.py) — add the new competency fields to the export allowlist so course packs round-trip ([ADR 041](041-course-pack-portable-bundle.md)).

### 8. Personal Development Plan

**`Personal Development Plan`** — `autoname: PDP-.######`: `student`, `program_enrollment`, `course_schedule`, `roster` (Links, reqd), `status` (Draft / Submitted / Reviewed / Accepted), `reflection` (Text Editor), `goals` (Table), `submitted_on`, `reviewed_by` (Link → Instructor), `reviewed_on`, `mentor_feedback` (Text Editor).

**`Personal Development Plan Goal`** (child): `standard_question` (Link → Standard Development Question, optional), `course_competency` (Link, optional), `dimension_code` (optional), `goal` (Text Editor, reqd), `action_steps` (Text Editor), `target_date` (Date), `support_needed` (Small Text), `status` (Planned / In Progress / Achieved).

**Each course's plan stands alone.** There is no `carried_forward_from` link and no goal that migrates between plans. A course has its own responsibilities, and a plan that inherits last course's unfinished business turns a formative exercise into an accumulating debt. Continuity is a *reading* concern, not a storage one — §9's aggregate view gives the student and the mentor the whole arc across courses without any plan claiming ownership of another's goals.

**`Standard Development Question`** — child on Competency Framework: `question_key` (Data, reqd, url-safe, unique in parent), `question_text` (Text Editor, reqd, translatable), `sequence` (Int), `active` (Check, default 1).

A school configures the prompts that shape the plan once, on the framework, and every plan in every program using that framework asks the same questions. `Personal Development Plan Goal.standard_question` links a goal to the prompt that produced it, which is what makes the aggregate view coherent: a student can read every answer they have ever given to *"where do you most need to grow in character?"* across four years of courses, and a mentor can read the same. Goals may also be free-standing (`standard_question` blank) so the plan is never a closed form. Deactivating a question stops it appearing in new plans without orphaning historical answers — the same reason `question_key` is stable and separate from the editable text.

### 8a. Development notes — the lifelong-journey problem

Some formation goals — spiritual vitality, besetting sin, vocational clarity — are never "Achieved", and a status field that only offers completion quietly tells a student their real struggles are failures. The `Achieved` state stays, because ordinary goals do complete; what is added is a place for the work that does not.

**`Personal Development Note`** — `autoname: PDN-.#######`: `student` (Link, reqd), `program_enrollment` (Link, reqd), `course_schedule` (Link, optional), `course_competency` (Link, optional), `dimension_code` (Data, optional), `development_plan` (Link → Personal Development Plan, optional), `note` (Text Editor, reqd), `note_date` (Datetime).

Notes are the student's own journal, anchored optionally to a plan, a competency or a dimension, and not tied to a course's completion. They are **not private**: the student's active mentors have read access, granted through Frappe document permissions resolved by `cbe.evaluators_for` rather than by flipping any file or field public (per [ADR 043](043-multichannel-communication-system.md)'s handling of scoped access). Accountability is the point of the mentoring relationship, and the UI says so plainly at the point of writing — a journal whose readership the writer has to guess is worse than one with no readers at all.

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
- Competency-level rendering in `CourseStatus.vue` and `Grades.vue`, and the **Program Enrollments by Mentor** report (§4) reachable from the mentor's worklist as well as from Desk.

**Radar chart:** `import { ECharts } from 'frappe-ui'` — echarts 5.6 is already an installed frappe-ui dependency. Two fixes are required: frappe-ui's wrapper hardcodes `theme: 'light'`, which fights dark mode ([ADR 003](003-dark-mode-and-visual%20standardization.md)), so wrap it in a local `RadarChart.vue` supplying token-derived colors; and add an `echarts` branch to `manualChunks` in `frontend/vite.config.js`, which currently lumps all of `node_modules` into `vendor`.

### 10. Aretenic bridge — a seam, not a build

Seminary keeps `required_apps = []` and never imports aretenic. `Course Competency.competency_code` is url-safe for the same reason `Course.coursecode` is, so aretenic can align a competency to a PLO and pick it up in `attainment.snapshot_offering_on_send_grades`, which `send_grades` already enqueues. Gate server-side on `utils._aretenic_enabled()` and client-side on `has_aretenic`. Documented as a seam; deferred.

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
- GPA is a framework toggle wired on both arms from the start, so a school that later wants one does not force a transcript rewrite. Cost: with the default `emit_gpa = 0`, a school running both CBE and conventional programs sees `Program Enrollment.current_gpa` populated for some students and not others, and honors levels do not apply to CBE students. That is pedagogically correct and will still read as a gap in the registrar UI until the transcript work lands.
- Development plans stay per-course and independent, with continuity supplied by a reading surface rather than by links between plans. This keeps each plan a closed, reviewable artifact and avoids goals accumulating across four years into a debt ledger. Cost: continuity now depends entirely on `SelfDevelopmentPlans.vue` and on schools actually configuring standard questions — a framework with no questions gives the aggregate view nothing to align on, and it degrades to a chronological list.
- `Personal Development Note` is explicitly mentor-readable, granted by document permission through `cbe.evaluators_for` rather than by loosening any field or file. Cost: this is genuinely sensitive pastoral content in a system that also holds disciplinary records, and a mentor's read access must revoke cleanly the moment their `Program Enrollment Mentor` row closes. The permission check must resolve at read time, never be cached onto the note.
- The parallel frontend means two grading experiences to maintain and to document. That is deliberate: the alternative — conditional fields inside the numeric gradebook — produces a page that serves neither model well.
- Fixing the `get_grade` / `get_gradepass` cache key is now on the critical path. It is a latent correctness bug today and a guaranteed one once two scale types coexist in a transcript render.

### Open questions

1. **What happens when a student fails in a cohort-paced program?** The school does not know: do groups shrink, merge, change mentors? This ships as `cohort_failure_policy = "Not defined — registrar decides"` with `Student Group Members` lifecycle fields in place so whatever they choose is recordable. Revisit when they have grown enough to need the rule.
2. **Does `report_basis = Summed` belong on the transcript, or only in the portal?** A 1–12 summed score is an internal aggregation artifact; printing it on a transcript alongside a 1–4 competency verdict may confuse receiving institutions. Deferred to the transcript work.
3. **`emit_gpa = 1` interacts with graduation floors in ways we have not modelled.** The GPA arithmetic is wired (§7), but `Program.min_graduation_gpa`, honors bands and the eligibility floors of [ADR 057](057-graduation-eligibility-floors.md) were designed against percentage scales; a four-point competency scale compresses the distribution enough that existing floor values would not transfer. Revisit when a school actually asks for it.
4. **Is `stall_escalation_days` enough of a response to a stalled student?** It notifies the mentor. It does not withdraw, flag academically, or open a hold. Whether a persistent stall should reach [ADR 030](030-program-status-lifecycle-spine.md)'s status spine is the same question as the failure policy in (1), and waits on the same answer.
5. **Who else may read a development note, and for how long?** Mentors, resolved live, is the shipped answer. A former mentor loses access when their row closes; whether a program director, a registrar handling a disciplinary matter, or the student's next mentor should see historical notes is a policy question no school has yet posed to us. Deliberately not modelled — widening this later is easy, narrowing it after staff have read things is not.

### Phasing

1. Scale hardening — the cache-key fix, `Grading Scale Dimensions` extension (including `dimension_icon`), CBE validation.
2. Config layer — `Competency Framework` and evaluator child, `Course Competency` and dimension child, the `Course Schedule Chapter` competency link, `Instructor Category` flags, Program binding and the program-course filter, `Program Enrollment Mentor`, and the Program Enrollments by Mentor report.
3. Record layer and convergence — `Activity Competency Grade`, `Competency Assessment`, `Competency Result`, `cbe.py`, hooks, the `grade_thisstudent` / `fgrade_this_std` / `gpa` (both `emit_gpa` arms) / `send_grades` branches.
4. Portal — self-assessment, competency gradebook, mentor worklist tab, competency panels in the course outline.
5. Content release — `cbe.visible_outline`, the submission-side guard, lock explanations in the outline, and the `stall_escalation_days` job.
6. Radar and transcript — `RadarChart.vue`, `CompetencyProfile.vue`, CBE rendering in `CourseStatus` and `Grades`.
7. Personal Development Plan — `Standard Development Question` on the framework, plan + goal doctypes, `PersonalDevelopmentPlan.vue`, `send_grades` guard.
7a. Development notes and the aggregate arc — `Personal Development Note` with mentor read permissions resolved at read time, `SelfDevelopmentPlans.vue` in both student and mentor modes.
8. Cohort pacing — `program_cohort_source`, Student Group program fields and member lifecycle, Cohort auto-creation from mentors.
9. Deferred — aretenic bridge; the failure/remediation policy once the school decides.
