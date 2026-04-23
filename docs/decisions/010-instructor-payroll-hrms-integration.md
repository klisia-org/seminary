# 010 — Instructor Payroll & HRMS Integration

**Date:** 2026-04-23
**Status:** Accepted

## Context

Before this change, `Instructor.employee` existed as an optional Link field with no callers — a placeholder for a payroll integration that was never built. The `Instructor Log` child table captured what each instructor taught (course × term × student count × "is instructor of record" flag) but nothing consumed it for compensation. Seminaries needed a way to pay instructors across three very different modalities:

1. **Volunteers** — guest / occasional profs from well-resourced donor partners, compensated via honoraria ("love offerings"), not wages.
2. **Salaried** — full-time or part-time staff on a recurring stipend.
3. **Per-course / per-capita** — paid per course taught, sometimes with a per-student component; rates often differ by role (Instructor of Record vs. GTA vs. Grader).

Frappe HRMS supplies the canonical payroll primitives — Employee, Salary Structure, Salary Slip, Payroll Entry — but it's an optional app; most seminaries run without it until they decide to formalize payroll. We needed an integration that's both off-by-default and usable for schools already operating for years when they turn it on.

## Decision

### HRMS is a soft dependency

A `hrms_enable` Check on Seminary Settings gates all HRMS-dependent behavior, mirroring [`portal_payment_enable`](../../seminary/seminary/doctype/seminary_settings/seminary_settings.json) for the Payments app. `Seminary Settings.validate` blocks saving with `hrms_enable=1` unless `hrms` is in `installed_apps`. `on_update` provisions Salary Slip custom fields and creates the stock "Instructor Pay" Salary Component when HRMS is present.

### Three modalities, three party types

`Instructor.instructor_type` (Select: Volunteer / Salaried / Per-Course) drives which flow applies.

- **Volunteer → Supplier + Purchase Invoice.** An auto-create-Supplier button on the Instructor form writes the Supplier back to a new `supplier` Link field. No HRMS needed for this path. Leverages the existing `Supplier.irs_1099` custom field.
- **Salaried → stock HRMS.** Pure config: Employee + Salary Structure Assignment + Payroll Entry. No custom code.
- **Per-Course → computed_instructor_pay.** Covered below.

### Per-course compensation: pre-compute, don't formula-aggregate

HRMS evaluates Salary Component formulas across at least three sandboxes (Salary Structure preview, Salary Structure Assignment base calculation, Salary Slip `calculate_net_pay`). Each whitelists a different subset of builtins — `sum`, `any`, `len` aren't reliably available in all three. A formula that works on the slip throws `name 'sum' is not defined` on the Structure, and the sandbox is not pluggable from app code.

Rather than fight it, we flatten. Our `Salary Slip.before_validate` hook pre-computes everything into a single Currency field `computed_instructor_pay`. Schools configure one auto-provisioned **Instructor Pay** Salary Component with formula = `computed_instructor_pay` — plain field reference, works in every sandbox.

Rates live in a child table **Instructor Category Rate** on **Instructor Category** with `pay_mode` (Per-Course / Per-Student), `amount`, `currency`, `effective_from`, and an `active` Check. Rate resolution at slip-compute time picks the row with the greatest `effective_from ≤ target_date` (ignoring `active`), so historical slips reprice correctly even after rates are deactivated for UI purposes.

### Split policy, cutoff, anti-double-pay

Three coordinating pieces:

- **`Seminary Settings.instructor_payment_split`** (End of period / 50% at start + 50% at end) — global, not per-program or per-course.
- **`Seminary Settings.hrms_live_date`** — cutoff date. Only courses whose effective start ≥ cutoff enter payroll. Lets seminaries adopt HRMS mid-operation without sweeping years of legacy courses into the first run.
- **`Instructor Log Payment`** — parent doctype with unique `(instructor_log, payment_event)`. `Salary Slip.on_submit` writes rows; `on_cancel` removes them. The hook skips events already posted on a non-cancelled slip. A slip that follows a missed month naturally catches up exactly one event per log row.

### Course-level dates win over term

For intensives inside a broader term, the validate hook prefers `Course Schedule.c_datestart` / `c_dateend` and falls back to Academic Term only when blank. A two-week intensive gets paid on the slip whose period contains *its* end date, not the term's.

### Category as role, not payroll modality

`Course Schedule Instructors.instructor_category` (Link to Instructor Category) replaces the legacy `inst_record` boolean. When `hrms_enable` is on, `CourseSchedule.validate` requires every instructor row to have a category. The accreditation semantics of `inst_record` migrate into `Instructor Category.is_instructor_of_record`; existing boolean rows backfill to "Instructor of Record" via [`migrate_inst_record_to_category.py`](../../seminary/seminary/patches/migrate_inst_record_to_category.py). One category taxonomy serves both reporting and payroll.

### Hook ordering: before_validate, not validate

HRMS's own `Salary Slip.validate` calls `calculate_net_pay`, which evaluates every Salary Component formula against the slip's current field state. `doc_events.validate` runs *after* the class method, so if we used `validate`, formulas would read a stale `computed_instructor_pay = 0`. The hook lives on `before_validate` so the computed field is in place before HRMS starts adding earnings.

## Alternatives considered

### Timesheet-linked Salary Slip — rejected

HRMS supports generating Salary Slips from Timesheets. Seminary doesn't track instructor hours and "teaching a course" isn't cleanly convertible to hours. Instructor Log already has the unit we want (course + student count).

### Additional Salary per Instructor Log row — rejected

At term end, iterate Instructor Log and create one Additional Salary per row. Workable, but rate logic lives in Python (not HRMS config), and earnings get scattered across many small rows instead of one Instructor Pay component. Accountants read slips component-by-component; we preferred one line item with a child-table breakdown.

### Extending HRMS's formula sandbox — rejected

`_safe_eval` uses `frappe.safe_eval` and HRMS pins its own `whitelisted_globals`. We tried injecting `sum` via the Salary Slip's validate hook; it only landed in the Slip sandbox, not the Structure preview sandbox. Fixing this upstream is the right long-term answer; for now, flat fields sidestep the whole issue.

### Submittable Instructor Category — rejected

Matches the Fee Category precedent, but Instructor Category is school-configurable setup data, not transactional. A submit/amend workflow adds friction without buying audit value that a simple "active + effective_from" doesn't already provide.

### Per-Course-Schedule split policy — rejected

Putting `payment_event` or split policy on each Course Schedule row was our first instinct (and would support per-course flexibility). Rejected because a school runs thousands of Course Schedules and one per policy decision each is a multiplier for human error. Global `Seminary Settings` is the right granularity for v1. A per-Program override is deferred until real need demands it.

## Consequences

**Easier:**
- Rate changes happen in one place (Instructor Category Rate); formulas never change.
- Mid-operation HRMS adoption is safe: set `hrms_live_date` and legacy courses stay out of payroll.
- Anti-double-pay is structural (DB unique constraint), not convention.
- Accountants get a read-only per-course breakdown on every slip via `instructor_log_summary`.
- Accreditation-mode categories (`is_instructor_of_record`) and payroll-mode categories (rates) share a single taxonomy.

**Friction (accepted):**
- Schools must pre-declare categories and attach rates before the first payroll. No dynamic category bootstrap from CSI.
- Category rename is an admin pain: all formulas that reference the field name would break. Mitigation: an admin never sees those formulas (there's only the auto-provisioned "Instructor Pay" component); only the hidden `courses_<slug>` / `students_<slug>` pilot fields rename-drift.
- Split policy is global. A seminary with two programs following different pay schedules must fold that into Salary Structures (different employees → different structures → different formulas referencing the same computed field).

**Open / residual risks:**
- **`update_instructorlog` appends rather than reconciles.** When a roster changes, a second log row gets inserted with the new `n_students`. The pay pipeline dedups on `(course, category)` taking `max(n_students)`; accreditation queries that count log rows will double-count until that upstream is cleaned up.
- **Per-Program / per-Category payment split** isn't supported. If demand materializes, the natural shape is `Program.instructor_payment_split` (optional override) + maybe a fall-through resolution order. Deliberately not built.
- **HRMS version pinning.** HRMS `v16.5.1` calls `Accounts Settings.append("repost_allowed_types", ...)` — a field ERPNext 16.x doesn't ship. Seminaries must pin to `v16.4.8` or older until HRMS fixes this upstream. Noted in the installation runbook.
