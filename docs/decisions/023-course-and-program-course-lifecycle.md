# 023 — Course & Program Course Lifecycle

**Date:** 2026-05-26
**Status:** Accepted

## Context

`Course` had no lifecycle field. The only way to retire a course was to remove it from every `Program`'s `Program Course` child table. This worked for student-facing flows that join through `Program Course` (`courses_for_student`, `get_available_courses_categorized`, the `courses_to_offer` report, the public Program page) but leaked everywhere else: **17 doctypes Link to `Course` directly** — Course Schedule, Question, Quiz, Assignment Activity, Exam Activity, Discussion Activity, Course Folder, Course_prerequisite, Partner Seminary Course Equivalence, Partner Transcript Import Row, and more. None of those pickers joined through `Program Course`, so a "retired" course still appeared in every assessment-authoring form, every scheduler, every prerequisite picker.

The retire-by-removal approach also conflated two distinct concerns (per ADR 015's orthogonal-flags principle):

- **Lifecycle**: "this course is gone from the catalog entirely"
- **Curriculum membership**: "this course is no longer required by MDiv (but exists for other programs)"

A single mechanism — yanking `Program Course` rows — was being asked to express both. Yanking also destroys curriculum history: the institution loses the audit trail of "MDiv required Hebrew I from 2018 through 2025."

Three sub-decisions emerged together:

1. How to express course lifecycle without overloading curriculum membership?
2. How to express per-program curriculum changes without destroying history?
3. How to apply the filters across all the downstream consumers without writing JS at each site?

## Decision

### Two orthogonal `disabled` flags, one per layer

- **`Course.disabled`** (Check, with `disabled_on` Date and `disable_reason` Small Text) — global catalog lifecycle. Answers "does this course still exist in our catalog at all?" Applies everywhere a Course is referenced.
- **`Program Course.disabled`** (with the same `disabled_on` and `disable_reason` companions on the child row) — per-program curriculum lifecycle. Answers "is this course part of this program's *current* curriculum?" Each Program Course row can be disabled independently of the Course it references.

The flags do **not** cascade. A Course can be `disabled=1` globally while `Program Course` rows for it remain `disabled=0` — that's the canonical shape of a retired course: curriculum history preserved, but the global filter ensures no new schedules, enrollments, or activities are created against it. Conversely, a Program Course row can be `disabled=1` while `Course.disabled=0` — that's a curriculum change ("MDiv no longer requires Hebrew I but it's still offered to other programs").

The "is this an active curriculum row today?" query is the join:

```sql
WHERE pc.parent = :program AND pc.disabled = 0 AND course.disabled = 0
```

Both layers checked independently. Cascading would conflate two reasons-for-disable (globally retired vs. dropped from this curriculum) and break re-enable semantics — re-enabling a globally retired course shouldn't auto-resurrect every per-program row that was deliberately retired earlier.

### `link_filters` (JSON), not `set_query` (JS), wherever static

For `Course.disabled = 0` Link picker filtering — applied across the 9 high-leverage downstream sites (Question, Quiz, Assignment Activity, Exam Activity, Discussion Activity, Course Folder, Course_prerequisite, Partner Seminary Course Equivalence, Partner Transcript Import Row, Course Schedule) — the filter lives in the field JSON as `"link_filters": "[[\"Course\",\"disabled\",\"=\",0]]"`, not in a `frm.set_query` JS handler.

Trade-off explicit: `link_filters` is **static** (cannot read other field values), but it applies in *every* render context (form, list filter chip, report builder, dialog pickers, quick-entry, API autocomplete). `set_query` is dynamic but only fires on form views. For a static `disabled = 0` filter, `link_filters` is strictly better: declarative, lives with the field definition, no JS file to maintain, survives refactors. We standardized on `link_filters` here and only fall back to `set_query` when the filter actually needs to compose with other field state.

One residual JS-level filter: the `coursecode_cs` lookup in `course_schedule.js` (an ad-hoc `frappe.db.get_list` resolving a typed course code to a Course) keeps a JS `disabled: 0` filter because it isn't a Link picker — there's no `link_filters` analogue for arbitrary client-side queries.

### Server-side filters at every "current curriculum" query site

Where Program Course is queried in Python — SQL or ORM — `pc.disabled = 0` (or `"disabled": 0` in filter dicts) was added wherever the result represents *current* curriculum. Notably **not** added to historical/audit sites:

- **Filter** (current curriculum / new enrollments): `api.get_course`, `api.courses_for_student` (both joins), `api.get_available_courses_categorized` (ORM + two `program.courses` iterations), `program_enrollment.get_program_courses`, `courses_to_offer` report, `course.bulk_add_courses_to_program` dedup, `course.get_programs_without_course`, `program.get_course_list` (public web view).
- **Keep all rows** (historical truth): `graduation_candidate._mandatory_program_courses`, `graduation_candidate._credit_sum`, `course_enrollment_individual.get_credits` / `get_credits2`, anything iterating `pe.courses` (which is `Program Enrollment Course`, not `Program Course`).

The discriminator: if the answer represents "what should happen now," filter. If it represents "what was true for student X / period Y," don't.

`Course.validate_duplicate_course` on CEI (uses `Program Course.repeatable`) was intentionally **not** gated because the upstream `courses_for_student` filter already prevents a `disabled=1` row from reaching that validator.

### Controller-stamped `disabled_on`, mandatory `disable_reason`

- `Course.validate` stamps `disabled_on = today()` when `disabled` is set and `disabled_on` is empty. `disabled_on` is `read_only` in JSON (admins don't hand-pick the date).
- `Program Course` row stamping lives in `Program.validate` (`_stamp_course_disabled_on`), not the child controller. Child-row lifecycle logic belongs to the parent — child `validate` methods fire inconsistently across save paths, and locating the logic on the parent makes it discoverable.
- `disable_reason` is `mandatory_depends_on: "eval:doc.disabled"` on both doctypes — declarative, enforced by the form layer regardless of save path. Forces a written reason on every retirement.

Re-enabling does **not** clear `disabled_on` or `disable_reason`. They become a historical record of the most recent retirement; the next disable refreshes them only if `disabled_on` is cleared manually first.

## Rejected: full term-versioning of curriculum

We considered making `Program Course` a versioned record with explicit `effective_from` / `effective_until` columns and a query API that always takes an as-of date. We declined for three reasons:

### 1. We already have it, accidentally

With `disabled`, `disabled_on`, and Frappe's free `creation` timestamp on every row, the timeline is reconstructable:

```sql
WHERE pc.parent = 'MDiv'
  AND pc.creation <= :asof
  AND (pc.disabled = 0 OR pc.disabled_on > :asof)
```

That's functionally identical to `WHERE :asof BETWEEN effective_from AND effective_until`. `creation` is the de facto `effective_from`; `disabled_on` is the de facto `effective_until`. Temporarily-retired-then-re-added courses produce two rows for the same `(program, course)` pair — the query above naturally returns the right answer at any date, including the gap.

### 2. Per-student curriculum already lives in `Program Enrollment Course`

`PEC` snapshots what each student was required to do at enrollment time. Graduation, GPA, and transcript queries already source from PEC, not Program Course. The institutional question "what did *student X* owe?" — the one that actually matters operationally — is answered by historical PEC rows and doesn't depend on Program Course staying versioned.

### 3. The cost is real, the benefit is query ergonomics

Full versioning would mean: a migration over every existing Program Course row, rewriting every report that reads `Program Course` to consume the as-of API, custom Link picker queries everywhere (since `link_filters` can't express "active at this date"), and a new mental model for every contributor. The capability gain over the current shape is **zero**; the only gain is cleaner SQL at the call sites that need as-of queries (currently a small minority).

### One real gap: per-row attribute changes

The current shape doesn't preserve historical values of `pgmcourse_credits`, `course_term`, or `required` when those are edited in place. Mitigation, by convention: when a semantically meaningful attribute changes on an active Program Course row, treat it as a curriculum change — disable the old row, append a new one with the new value. The disable-and-recreate pattern is already the prescribed handling for temporary retirement, so this is the same workflow.

The secondary mitigation: ensure `Program Enrollment Course` denormalizes the per-row attributes a student is bound by at enrollment time, so per-student history doesn't depend on Program Course staying stable. (PEC's existing fields cover this — verified during this work.)

## Consequences

**Easier:**

- "Retire this course" is a single global flag with a written reason and an automatic timestamp; no curriculum mutation required.
- "Drop this course from MDiv" is a single per-row flag on `Program Course`, also with reason and timestamp; curriculum history preserved.
- 9 downstream Link pickers gained `disabled=0` filtering in JSON, with zero JS files modified. Adding a new doctype that Links to `Course` is now a one-line `link_filters` addition.
- Public Program web pages, the enrollment portal, the demand report, and the Program Enrollment course picker all surface only current curriculum.
- Historical reports (graduation, GPA, transcripts, credit sums on existing CEIs) keep working unchanged — they read from PEC or from full Program Course rows where the historical row is the right answer.

**Friction (accepted):**

- `link_filters` is static. Sites that need dynamic course filtering (e.g., "courses in this program for this term") still need `set_query`. The split (static = JSON, dynamic = JS) is a contributor expectation to internalize.
- The `Course.disabled` filter has to be added at every new downstream Link site. The 9 covered today aren't exhaustive of the 17 doctypes that Link to Course — Course Schedule Chapter, Discussion Submission, and others remain. Each is a one-liner when the time comes, but they're not free.
- Re-enabling a course leaves stale `disabled_on` / `disable_reason` on the row. By design — but admins who toggle disabled back and forth without clearing those fields see misleading "last retired on" data. The simpler behavior (don't auto-clear) was chosen over the more correct one (transition-aware clearing) for predictability.

**Open / residual:**

- Per-row attribute versioning (credits, term, required, repeatable) remains by-convention via disable-and-recreate, not enforced. A future contributor editing `pgmcourse_credits` in place silently loses prior values.
- `Program Track Courses` — the parallel child table for emphasis tracks — does not yet have the same `disabled` lifecycle. When emphasis tracks become operationally important enough to need retirement semantics, mirror this ADR there.
- The pending ADR on term-vs-program rule placement (see [project_pending_adrs]) will reference this one — placing curriculum-affecting rules on Program Course rather than Program is consistent with the lifecycle layer being at the per-row level.

## References

- [`course.json`](../../seminary/seminary/doctype/course/course.json) — `disabled`, `disabled_on` (read-only), `disable_reason` (mandatory_depends_on)
- [`course.py`](../../seminary/seminary/doctype/course/course.py) — `set_disabled_on` in `validate`
- [`program_course.json`](../../seminary/seminary/doctype/program_course/program_course.json) — child-row `disabled` / `disabled_on` / `disable_reason`
- [`program.py`](../../seminary/seminary/doctype/program/program.py) — `_stamp_course_disabled_on` invoked from `validate`; `get_course_list` filters disabled rows
- [`api.py`](../../seminary/seminary/api.py) — `get_course`, `courses_for_student`, `get_available_courses_categorized`, `petb_enroll` all gated
- [`program_enrollment.py`](../../seminary/seminary/doctype/program_enrollment/program_enrollment.py) — `get_program_courses` picker filter
- [`courses_to_offer.py`](../../seminary/seminary/report/courses_to_offer/courses_to_offer.py) — demand report SQL gated
- Field JSONs with `link_filters` on the `Course` link: [`question.json`](../../seminary/seminary/doctype/question/question.json), [`quiz.json`](../../seminary/seminary/doctype/quiz/quiz.json), [`assignment_activity.json`](../../seminary/seminary/doctype/assignment_activity/assignment_activity.json), [`exam_activity.json`](../../seminary/seminary/doctype/exam_activity/exam_activity.json), [`discussion_activity.json`](../../seminary/seminary/doctype/discussion_activity/discussion_activity.json), [`course_folder.json`](../../seminary/seminary/doctype/course_folder/course_folder.json), [`course_prerequisite.json`](../../seminary/seminary/doctype/course_prerequisite/course_prerequisite.json), [`partner_seminary_course_equivalence.json`](../../seminary/seminary/doctype/partner_seminary_course_equivalence/partner_seminary_course_equivalence.json), [`partner_transcript_import_row.json`](../../seminary/seminary/doctype/partner_transcript_import_row/partner_transcript_import_row.json), [`course_schedule.json`](../../seminary/seminary/doctype/course_schedule/course_schedule.json)
- ADR 015 — orthogonal flags principle ("split feature flags by concern") motivated keeping `Course.disabled` and `Program Course.disabled` independent
- ADR 013 — Course Schedule lifecycle (the doctype that consumes Course; gated by this ADR's `link_filters`)
- ADR 012 — graduation requirements architecture (relies on PEC, not Program Course, for per-student curriculum)
