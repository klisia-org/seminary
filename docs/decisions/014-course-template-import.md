# 014 — Course Template Import

**Date:** 2026-04-27
**Status:** Accepted

## Context

Setting up a Course Schedule each term meant re-creating the LMS structure
(chapters, lessons, assessment criteria) by hand even when the underlying
Course was unchanged. Profs and registrars typed the same chapter/lesson/
SCAC layout every term, with predictable copy/paste errors and drift
between sections of the same course.

Two related needs surfaced together:

1. **One-click clone of a "template" CS** into a new CS of the same course,
   carrying the structural content (chapters, lessons, assessment criteria)
   without copying per-instance state (roster, grades, dates, enrollment
   counts).
2. **Auto-seed of `Scheduled Course Assess Criteria`** from the parent
   `Course.assessment_criteria` on every new CS — the previous flow left
   SCAC empty, and the recently-added `title` field on SCAC made saving
   any CS without manually filling SCAC impossible.

Both share the same insight: most of a CS's structure is properties of
the *Course*, not properties of *this term's instance*. Wherever we can
derive structure from the Course (or another CS of the same course), we
should.

## Decision

### `Course.default_cs_template` — opt-in pointer

A new optional Link field on Course points at one CS the registrar
chooses as the canonical template. The picker is restricted client-side
to CSes of the same Course (Frappe's static `link_filters` JSON cannot
reference `parent.course_name`; the filter lives in [course.js](../../seminary/seminary/doctype/course/course.js)
via `set_query`). Optional — the import dialog still allows picking any
same-course CS at runtime.

### Custom form button on Course Schedule, not a workflow transition

Following the pattern established in ADR 013, the import is **not** a
workflow Action menu entry. Cancel, Send Grades, and Begin Grading were
removed from the Workflow fixture there because they carry side effects
that a bare `apply_workflow` would skip. Same logic for Import: it
mutates child tables and creates new Chapter / Lesson docs — needs
structured input (which source CS) and side-effect handling — so it
flows through a custom form button → whitelisted controller method.

The button appears in the **Actions** group on the CS Desk form when:

- `workflow_state ∈ {Draft, Open for Enrollment}` — once enrollment has
  closed, the prof has effectively committed to the structure
- the user has `Academics User`, `Seminary Manager`, or `Registrar`
- the target CS has zero chapters

### Validations as cheap reads, then writes — no rollback path

The import method runs **all** validations (target + source) up-front
as read-only checks, throws on any violation, and only then begins the
write phase. There is no expected rollback path: every "expected"
failure mode (wrong state, wrong role, source weight imbalance,
target has chapters, source has no SCAC, self-import, cross-course)
is caught before any DB writes.

This is a deliberate inversion of the typical Frappe `save()` →
`validate()` → throw → savepoint-rollback pattern. Cleaner because:

- Errors surface with full context at the validation step (e.g. "source
  schedule's weights total 75% — fix source first") rather than at a
  generic save-time validator
- Half-written state is impossible by construction
- Frappe's request-level transaction still rolls back true exceptions
  (DB connectivity, code bugs) — we don't need a defensive savepoint

### Direct child-doc inserts; no parent `self.save()`

The import does not call `self.save()` on the target CS. All
persistence happens via direct child-doc inserts (Scheduled Course
Assess Criteria rows, Course Schedule Chapter Reference rows, Course
Schedule Lesson Reference rows). This sidesteps a subtle bug:

`Course Lesson` has an `updates_lessons` denormalization hook that
increments `Course Schedule.lessons` via `frappe.db.set_value` on
every Lesson insert. Each lesson insert during import bumps the
target's denormalized count *and* its `modified` timestamp. A
subsequent `self.save()` would then:

1. Throw `TimestampMismatchError` because `_original_modified` is
   stale (caught by `check_if_latest`).
2. *If we papered over (1)*, overwrite the hook-driven `lessons` count
   with the in-memory zero from before the inserts.

Refreshing `_original_modified` only fixes (1), not (2). Avoiding
`self.save()` entirely fixes both — and protects against any future
denorm hook that writes back to Course Schedule during a child insert.
We lose the implicit `validate_assessment_criteria` check at save, but
the explicit source-side weight validation up-front is the same check
applied to the same data, just earlier.

### SCAC link remap on copied lessons

Each Course Lesson on the source carries four Link fields
(`assessment_criteria_quiz`, `_assignment`, `_exam`, `_discussion`)
pointing at SCAC rows on the *source* CS. After we copy SCAC rows,
the new SCAC rows have new names; the copied lessons would otherwise
reference the source's SCAC, not the target's. The import builds a
`{source_scac_name → new_scac_name}` map during the SCAC copy and
remaps each lesson's four Link fields via `frappe.db.set_value`
(bypassing `Course Lesson.on_update`'s `update_lesson_assessments`
hook so we don't race it).

`Course Lesson.on_update` will run `update_lesson_assessments` again
the next time someone opens and saves the lesson, but it looks up
SCAC by `parent = target_cs` and matches on `quiz` / `assignment` /
`exam` / `discussion` Link — finds the same SCAC row we mapped.
Idempotent.

### Replace target SCAC, refuse on chapters

The chapter-empty gate catches the common case (registrar accidentally
imports into the wrong CS). SCAC replacement is unconditional: target
CSes are required to have at least one SCAC row to satisfy `reqd:1`,
so the registrar's placeholder gets overwritten. There is no "merge"
mode — the import is destructive on SCAC and additive on chapters.

### Auto-seed SCAC from Course on insert

In `before_insert`, if `courseassescrit_sc` is empty and `course` is
set, the CS auto-populates SCAC from `Course.assessment_criteria`.
Mapping: `title → title`, `assessment_criteria → assesscriteria_scac`,
`weightage → weight_scac`, plus an explicit `extracredit_scac = 0`
(Course Assessment Criteria has no extra-credit field; everything
copied is non-extra-credit, and `validate_assessment_criteria`'s
`if/elif` on `extracredit_scac == 0/1` silently skips rows where the
value is `None` — see Consequences below).

This addresses two issues in one hook:

- The recently-added `SCAC.title = reqd:1` made it impossible to save
  a fresh CS without manually filling SCAC, even when the parent
  Course had complete assessment criteria.
- The previous flow had no auto-population at all — registrars
  re-entered the same data per term.

Importantly, this hook runs on insert *before* the template-import
flow can replace the seeded rows. No conflict.

## Consequences

**Easier:**

- New CSes for a Course with configured `assessment_criteria` are
  saveable without manual SCAC entry.
- Registrars can clone a known-good CS structure in one click instead
  of re-typing chapters, lessons, and SCAC each term.
- The import surface area is small and predictable: chapters + lessons
  + SCAC. No grades, dates, roster, or enrollment counts ever sneak
  in. No partial state on failure.
- Direct child-insert pattern (no parent save) is now demonstrated as
  the right answer when denorm hooks are involved — reusable for
  future bulk operations.

**Friction (accepted):**

- The button's visibility logic (state + role + no chapters) is
  duplicated client-side and server-side. Server is authoritative;
  client is UX hint. Drift would require both to be updated; intentional
  redundancy.
- `Cancel Course`, `Send Grades`, `Begin Grading`, and `Import Course
  Template` all live outside the workflow Action menu and instead as
  custom buttons. A future contributor reading `workflow.json` first
  will not see them. Both this ADR and 013 document the asymmetry; the
  `course_schedule.js` button code is the canonical reference.
- The import is **not idempotent**: re-running on a populated target
  refuses via the chapter-empty gate. Safer than silent doubling.
  To re-import, the registrar must delete chapters manually.
- The auto-seed only fires on insert. Changing `course` on an existing
  CS does not re-seed — that's a separate policy decision (out of
  scope here).

**Open / residual risks:**

- **`validate_assessment_criteria` is fragile.** The
  `if extracredit_scac == 0 / elif == 1` pattern silently skips rows
  where the value is `None` — caused the auto-seed weight-sum bug.
  The explicit `extracredit_scac = 0` in the seed sidesteps it, but
  any other code path that creates a SCAC row without setting the
  field will hit the same bug. Durable fix: change the validate to
  `if criteria.extracredit_scac: continue / total += criteria.weight_scac or 0`.
  Out of scope for this iteration.
- **SCORM file references shared between CSes.** Multiple Chapter docs
  reference the same File doc. Deleting the source CS does not break
  target's SCORM links (Frappe File doc is independent), but admins
  should know that templates create shared file references.
- **Concurrency.** Two imports into the same target simultaneously —
  both pass chapter-empty validation, the second fails late on
  conflicting child rows or weight totals. Rare; acceptable for typical
  seminary scale.
- **`TEMPLATE_IMPORT_STATES` is hardcoded.** If the workflow ever adds
  a new pre-enrollment-close state, this list needs review. Comment in
  the constant declaration directs the reader.

## References

- [`course_schedule.py`](../../seminary/seminary/doctype/course_schedule/course_schedule.py) — `import_template`, `_validate_target_for_import`, `_validate_source_for_import`, `_replace_scac_rows`, `_copy_chapters_and_lessons`, `_remap_lesson_scac_links`, `_seed_assessment_criteria_from_course`.
- [`course_schedule.js`](../../seminary/seminary/doctype/course_schedule/course_schedule.js) — Import button + dialog.
- [`course.json`](../../seminary/seminary/doctype/course/course.json), [`course.js`](../../seminary/seminary/doctype/course/course.js) — `default_cs_template` field + `set_query` filter.
- ADR 013 — established the "side-effect actions live outside the workflow as custom buttons" pattern this ADR extends.
