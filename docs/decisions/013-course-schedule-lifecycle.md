# 013 — Course Schedule Lifecycle

**Date:** 2026-04-27
**Status:** Accepted

## Context

Course Schedule had no formal lifecycle. A single `open_enroll` boolean
conflated "enrollment is open" with "course is active", `grades_sent` was
written alongside a no-op `docstatus = 1` (CS is not submittable), and
there was no way to cancel a course due to insufficient enrollment while
preserving an audit trail. The registrar had no first-class view of which
courses were open, closed, in grading, or cancelled, and the prof-facing
gradebook had no Send Grades action — that lived only on Desk as a Server
Action that any user could invoke without role gating.

The full real-world flow is: course is offered → students enroll →
registrar checks enrollment counts a few days before close → cancels
courses that didn't make it → enrollment closes → term runs → grading →
final grade submission → registrar nags late graders. None of this was
modeled.

## Decision

### Six-state native Frappe Workflow on Course Schedule

```
Draft → Open for Enrollment → Enrollment Closed → Grading → Closed
            ↓                       ↓
        Cancelled               Cancelled (terminal)
```

Native [`Workflow`](../../seminary/seminary/fixtures/workflow.json#L256)
fixture, consistent with existing app convention (Course Withdrawal
Request, Recommendation Letter, Culminating Project all use native
workflows). All states are `doc_status: "0"` because Course Schedule is
not submittable.

### Pure transitions vs side-effect-bearing transitions

The workflow has only **pure** state transitions — those that carry no
side effects beyond the state change itself: `Open Enrollment`,
`Close Enrollment`, `Begin Grading`. These are exposed in the Desk Action
menu and gated by Frappe's role check.

Three actions carry side effects (cascades, grade computation, structured
input) and are **intentionally absent from the workflow**:

- **Cancel Course** — needs a `Course Cancellation Reason`, marks every
  enrolled CEI as `course_cancelled`, hard-deletes auto-populated PEC
  rows (preserving partner-seminary rows per ADR 005), and submits a
  Seminary Announcement to enrolled students.
- **Send Grades** — computes finals, writes PEC `pec_finalgradenum` /
  `pec_finalgradecode` / `status`, recomputes emphasis credits, deactivates
  Scheduled Course Roster rows, then transitions to Closed.
- **Begin Grading** (auto-advance variant) — fires automatically when the
  first non-null grade is saved against an active roster.

These flow through whitelisted controller methods reached from custom
form buttons (or, for Send Grades, the frontend Gradebook button) that
prompt for input or run the cascade before flipping state. Removing the
bare workflow transitions prevents the Desk Action menu from bypassing
the side-effect logic — the previous model where `apply_workflow` was the
only path silently lost grades and cascades when registrars clicked the
state chip directly.

### System-driven transitions bypass `apply_workflow`

Three triggers run as the saving user (not a privileged scheduler
context):

- The frontend Send Grades button (clicked by an Instructor)
- `cancel_course` (called by Registrar / Seminary Manager)
- The first-grade-saved auto-advance hook (fires under whoever saved the grade)

`apply_workflow` enforces transition.allowed against the calling user's
roles. For system-driven transitions where the user is not the
authoritative actor, this gate is the wrong abstraction. Each of these
three sets `workflow_state` via [`frappe.db.set_value`](../../seminary/seminary/cs_lifecycle.py)
after running its own role / state checks.

The pure transitions (`Open Enrollment`, `Close Enrollment`,
`Begin Grading` manual) keep using `apply_workflow` — they're either
date-driven (running as Administrator under the daily scheduler) or
genuinely registrar-initiated.

### Event-driven Grading transition

`Enrollment Closed → Grading` is not date-driven. It fires automatically
on the first non-null grade saved against any active, non-course-cancelled
roster row, hooked at Course Assess Results Detail `on_update` and
Scheduled Course Roster `on_update` (both call the same idempotent helper
[`check_and_advance_to_grading`](../../seminary/seminary/cs_lifecycle.py)).
The dual hook covers both grade-via-Submission paths (`quizresult_to_card`
→ `card.save()`) and grade-via-SCR-form paths.

This eliminates a `grading_open_date` registrars would otherwise need to
maintain. The trigger event also doubles as the structural enforcement of
"no cancel after grades exist" — the cancel paths reject any state past
Enrollment Closed, and grading necessarily promotes to Grading.

### Date rules on Seminary Settings, not Program

A Course Schedule's `course` Link can belong to multiple Programs.
Putting the enrollment date rule on Program meant a single CS could face
N conflicting rules with no obvious resolution. Rules live on
**Seminary Settings** instead — six fields, one anchor + offset pair per
window: `enrollment_open`, `enrollment_close`, `grade_close`. Anchors:
`term_start`, `term_end`, `classes_start` (= CS `c_datestart`),
`classes_end` (= CS `c_dateend`). Per-CS overrides on three
`*_date_override` fields take precedence.

Empty anchor + no override → the resolved date is `None` and the
scheduler ignores that window. Initial state on insert defaults to
`Open for Enrollment` whenever no future open date can be resolved,
preserving the previous default-open behavior.

### Cancellation: CEI flag, hard-delete PEC, partner rows protected

Cancellation marks each non-withdrawn `Course Enrollment Individual` with
`course_cancelled = 1` (plus reason + timestamp) — distinct from
student-initiated `withdrawn` so the source of the inactive enrollment is
preserved. The auto-populated `Program Enrollment Course` rows for this
CS are hard-deleted, with a `COALESCE(partner_seminary, '') = ''` filter
to spare transferred rows from the Unified Partner Seminary Model
(ADR 005).

Seminary Announcement is the notification channel; it's skipped when no
enrolled students exist (the announcement rejects empty audiences and
its throw would roll back the transaction).

Sales Invoice handling is **deferred to a later iteration**. The current
cascade leaves invoices untouched; the registrar must reconcile them
manually. This was an explicit scope cut.

### Manual escape hatch for "cancel after grades"

The state machine forbids cancellation past `Enrollment Closed`. The
manual escape — for genuine emergencies (instructor death, force majeure
mid-term) — is to **withdraw each enrolled student individually**, then
**Send Grades on the resulting empty roster**, which transitions to
Closed cleanly. This is the only way; the system intentionally has no
cancel-from-Grading override.

### Auto-advance toggle

`Seminary Settings.auto_advance_course_schedule` (default on) gates the
daily scheduler. When off, all date-driven transitions become manual
(registrar uses workflow Action menu). African and other contexts where
academic schedules are fluid can disable automation entirely without
losing the rest of the lifecycle.

### Late-grade nag

Daily job emails the instructor (CC: Registrar role users) when a CS is
past its `grade_close_date` and still in Enrollment Closed *or* Grading.
Idempotent via `late_grade_nag_sent`. Importantly, the nag fires for
both pre-Grading-and-past-deadline cases — a "very lazy prof" who hasn't
graded anything would otherwise get a free pass on a Grading-only filter.
Direct `frappe.sendmail`, not Seminary Announcement (the latter is
audience-based and has no native CC).

### `graded_card` flag on Course Assess Results Detail

Frappe creates Float columns as `decimal(21,9) NOT NULL DEFAULT 0`. There
is no JSON-level toggle to make a Float nullable, so the gradebook cannot
distinguish "ungraded" from "graded zero" by reading `rawscore_card` alone
— a fresh CARD row created via `copy_data_to_scheduled_course_roster`
already reads `0`, identical to a deliberately-entered zero.

The fix is an explicit **`graded_card`** Check field (default 0, hidden,
read-only). Set to 1 when a real grade is propagated:

- [`quizresult_to_card`](../../seminary/seminary/api.py) flips it on/off based
  on whether the upstream submission carries a non-null percentage.
- The frontend gradebook's [`saveCell` / `saveAllChanges`](../../frontend/src/pages/Gradebook.vue)
  writes both the score field and `graded_card = 1` atomically (or both
  fields with `graded_card = 0` when the prof clears a cell).

Frontend rendering, the `hasNullGrades` computed that gates the Send Grades
button, and the server-side null pre-check in `send_grades` all key off
`graded_card` rather than the Float value. The Float column stays NOT
NULL DEFAULT 0; null values are coerced to 0 at the save boundary and the
flag carries the real "ungraded" signal.

Tradeoff: pre-existing graded CARDs from before this field existed appear
as ungraded until re-saved. A conservative SQL backfill
(`UPDATE ... SET graded_card = 1 WHERE rawscore_card > 0 OR actualextrapt_card > 0`)
catches everything except genuine graded zeros, which are vanishingly
rare in the existing data and recoverable by re-saving the corresponding
Submission.

## Consequences

**Easier:**

- Registrars get a queryable, auditable lifecycle. `workflow_state`
  filtering replaces `open_enroll = 1` everywhere; the Number Card,
  CEI form filter, and `courses_for_student` SQL all updated.
- Cancellation has a single supported path with structured reason capture
  and reliable cascade. Audit trail preserved on CEI.
- The frontend Gradebook now distinguishes null (ungraded) from zero
  (graded zero) and exposes Send Grades to instructors directly,
  closing the Desk-only gap.
- New `Term Enrollment Status` Script Report shows Min/Current/Delta per
  CS for the registrar's "is this course making it?" decision.
- Late-grade visibility is automated — the registrar no longer has to
  manually chase down profs.

**Friction (accepted):**

- Three transitions live outside the workflow fixture. A future
  contributor who reads `workflow.json` first will not see Cancel Course /
  Send Grades / auto-Begin-Grading and may be confused. This ADR is the
  single source of truth for that asymmetry.
- The Desk Action menu intentionally lacks Cancel Course / Send Grades.
  Bulk cancellation from List View is not supported (form-only) — would
  need a separate List View action calling `cancel_course` per row with
  a shared reason if registrars demand it.
- `course_cancelled` is filtered out of "already enrolled" queries
  (`courses_for_student`, `validate_duplicate`, `get_student_enrollments_for_term`,
  in-progress audit checks) but **not** wired into the gradebook payload.
  A cancelled-course student will still appear in Gradebook.vue's
  hasNullGrades calculation; in practice this is fine because cancellation
  zeroes the roster before Grading begins, but it's a cleanup loose end.
- Sales Invoice reconciliation on cancellation is manual — out of scope
  this iteration.

**Open / residual risks:**

- **`grade_close_date` resolution depends on `c_datestart` / `c_dateend`**
  for `classes_*` anchors. If a CS is created with those dates blank,
  the resolved date is `None` and the late-grade nag never fires. Either
  enforce CS dates as required (already are) or surface an "unresolved
  date" warning in the Term Enrollment Status report.
- **No re-snapshot mechanism on date-rule change.** When Seminary
  Settings rules change mid-term, existing CSes keep their previously
  resolved dates until the next save (which triggers
  `_resolve_dates_if_needed`). A registrar who tightens rules mid-term
  may need to bulk-save CSes to propagate. Acceptable for now.
- **The CARD-side null-grade pre-check in `send_grades`** treats every
  active non-cancelled student as needing a non-null grade in every cell
  including extra credit. A prof who deliberately leaves an extra-credit
  cell empty (meaning "no extra credit earned") must explicitly enter 0.
  Documented in the staff docs.
- **`course_cancelled` cascade is idempotent but irreversible.** No undo
  in this version. ADR-005 partner rows survive the cascade by design;
  ordinary PEC rows do not. A registrar who cancels by mistake must
  re-create enrollments manually.
- **The form-button cancellation flow runs synchronously.** A CS with
  hundreds of CEIs will block the registrar's UI for the duration of the
  cascade. Acceptable for typical seminary scale (single-digit-to-low-hundreds
  per course) but worth queuing if scale grows.

## References

- [`seminary/cs_lifecycle.py`](../../seminary/seminary/cs_lifecycle.py) — date resolver, scheduled jobs, event-driven Grading helper.
- [`api.py:send_grades`](../../seminary/seminary/api.py) — Closed transition with grade computation + idempotency.
- [`course_schedule.py`](../../seminary/seminary/doctype/course_schedule/course_schedule.py) — `cancel_course`, cascade helpers, date resolution.
- [Workflow fixture](../../seminary/seminary/fixtures/workflow.json) — the four pure transitions.
- ADR 005 — Unified Partner Seminary Model (PEC `partner_seminary` rows protected from cascade).
