# 035 — Deferred auto-enrollment for mandatory-on-enrollment courses

**Date:** 2026-06-08
**Status:** Accepted

## Context

A `Program Course` row carries `pgm_course_reqonenroll` ("Mandatory on program
enrollment"): a course the student must be auto-enrolled into. (This is distinct
from `required`, which marks a course mandatory **for graduation / degree
audit** — read by `graduation_candidate._mandatory_program_courses`. This ADR
touches only `pgm_course_reqonenroll`.)

The obvious implementation — enroll on Program Enrollment (PE) submit — does not
work in general. Enrollment requires a **Course Schedule (CS)**, a concrete
offering of a Course in a specific Academic Term. A student may submit their PE
in a term where the mandatory course has **no open offering yet**; it will be
scheduled some future term. So fulfillment cannot always happen at PE-submit
time and must be **deferred** until an offering opens.

Two further constraints shaped the design:

- **Snapshot semantics.** The module already freezes graduation requirements onto
  the PE at submit (`snapshot_graduation_requirements`). Mandatory-on-enrollment
  must behave the same way: adding the flag to a Program later must **not**
  silently cascade into already-enrolled students. The requirement set is a
  property of the enrollment *as submitted*, not of the live curriculum.
- **No new lifecycle to drift.** The system's pattern is recompute-from-canonical
  -state (candidacy, payment status, cancel cascade), not maintaining parallel
  status records.

## Decision

**Two-sided, event-driven auto-enrollment. The requirement *set* is snapshotted
per PE; fulfillment *status* is computed on the fly from CEI/PEC.**

1. **Snapshot at submit.** A new child table `Program Enrollment Required Course`
   (`required_on_enroll_courses` on Program Enrollment) is frozen in
   `ProgramEnrollment.before_submit` from the Program's `pgm_course_reqonenroll`
   (non-disabled) courses — mirroring the grad-requirements snapshot. All
   matching reads this frozen list, never the live Program flag.

2. **Seam (a) — forward, at PE submit.** `Program Enrollment` `on_submit` →
   `required_enrollment.fulfill_for_program_enrollment_hook`, registered **after**
   `api.get_payers` (ordered `doc_events` list) so auto-created CEIs invoice
   against a populated fee structure. Enrolls into any snapshot course that
   already has an open offering.

3. **Seam (b) — deferred, when an offering opens.** Course Schedule is **not
   submittable** (every workflow state is `docstatus=0`), so
   `on_update_after_submit` never fires for it. The seam is therefore
   `Course Schedule` **`on_update`** (guarded on a `workflow_state` change into
   "Open for Enrollment"; the daily `advance_due_course_schedules` reaches Open
   via `apply_workflow` → `doc.save()`), plus **`after_insert`** for a CS born
   directly Open. It back-enrolls every active PE whose **snapshot** lists that
   course and who still owes it.

4. **Single enrollment primitive.** All enrollment goes through
   `api.course_enroll(pe, cs)`; roster + Program Enrollment Course rows are its
   downstream side effects and are never hand-rolled. The CEI's own
   `validate_duplicate` / `validate_duplicate_course` is the **authoritative**
   idempotency guard — the module's pre-checks are an optimization, and a
   duplicate throw is swallowed as a benign skip.

5. **Eligibility / dedup.** A course is skipped if the student already has a live
   CEI for it (any non-withdrawn / non-cancelled / non-audit state) or a passing
   (graded, non-Fail) Program Enrollment Course — which also makes a *repeatable*
   mandatory course fulfill once via the auto path. A Failed PEC leaves it owed.

6. **Prerequisites.** If a snapshot course has an unmet **mandatory**
   prerequisite, it is **not** enrolled; a ToDo is raised for the Registrar
   (idempotent per PE+course).

7. **Payment.** Auto-CEIs flow through `course_enroll` unchanged: paid programs
   invoice and sit in Awaiting Payment until the threshold is met, then advance
   to the roster. Mandatory ≠ free. `Program.registrar_block_cei` still defers to
   Draft where configured.

8. **Offering selection.** When several offerings are open, `_pick_offering`
   orders by: same term as the enrollment → `modality = Virtual` → earliest class
   start → name (deterministic).

9. **Backfill is explicit only.** Toggling the flag on a Program does not touch
   existing PEs. `reconcile_required_enrollments(program)` — exposed via the
   Program form button *"Apply Mandatory-on-Enrollment to Active Students"* and
   bench — **appends** newly-flagged courses to active PEs' snapshots (never
   wipes) and fulfills. No automatic / scheduled backfill.

## Capacity (out of scope)

The system has **no** max-participants / room-capacity / waitlist logic. Course
Schedule has `room` and `modality` but enforces neither. This is deferred to
future work (candidate ADR 036). As an interim hedge, `_pick_offering` prefers
`modality = Virtual` to avoid physical-room contention when a course is offered
in multiple modalities the same term.

## Consequences

- Adding the flag is safe and non-retroactive; existing cohorts change only on an
  explicit registrar action.
- A cancelled CS cascades (`cancel_course`) to mark the CEI `course_cancelled` /
  drop the PEC, so the student again "owes" the snapshot course and the next open
  offering re-fulfills — no special handling.
- Withdraw/LOA flips `pgmenrol_active=0` → the fulfiller skips; on return, the
  snapshot persists and the next event/reconcile re-evaluates.

## Rejected alternatives

- **Materialized Pending/Fulfilled/Waived queue doctype** — a second source of
  truth for "owes course X" that must be reconciled against CEI/PEC forever
  (flag toggled, course made repeatable, withdrawn-then-returned, CS cancelled).
  Rejected for drift.
- **Live-flag deferred matching** (no snapshot) — would cascade retroactively
  when the flag is toggled, violating the snapshot principle.

## Touch points

- `program_enrollment_required_course/` — new child doctype (snapshot row).
- `program_enrollment.json` / `program_enrollment.py` —
  `required_on_enroll_courses` field + `snapshot_required_on_enroll_courses()`.
- `required_enrollment.py` — fulfiller, deferred backfill, reconcile, predicates.
- `hooks.py` — PE `on_submit` (appended); Course Schedule `on_update` /
  `after_insert`.
- `program.py` / `program.js` — `apply_required_on_enroll` + conditional button.
