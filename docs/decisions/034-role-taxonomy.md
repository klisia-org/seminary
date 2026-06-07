# 034 — Seminary role taxonomy

**Date:** 2026-06-07
**Status:** Accepted

## Context

Roles had been applied inconsistently across the module's doctypes. A DocPerm
audit showed two failure modes:

- **Forgotten roles** — `Registrar` carried permissions on only 14 doctypes, and
  four doctypes (`buildings`, `course_gradebook`, `course_result_tool`,
  `payers_fee_category_pe`) were `System Manager`-only. `Seminary Manager` was
  absent from many academic doctypes it should administer.
- **Conflated roles** — `Academics User` had become the catch-all, holding
  permissions on ~85% of permissioned doctypes, absorbing work that belonged to
  the Registrar.

Two structural problems compounded this:

1. **Names didn't match meaning.** `Academics User` was the de-facto
   programs/curriculum authority, while the role literally named `Instructor` was
   used in code as a grader (`utils.get_user_info` set `is_evaluator =
   "Instructor"`).
2. **The app didn't own its roles.** `Academics User` and `Seminary Manager` were
   never created by `install.py`; the module silently depended on ERPNext's
   legacy Education roles. References to nonexistent `Course Moderator` /
   `Evaluator` / `Seminary Admin` roles lingered in `auth.py` and the docs.

## Decision

Adopt an explicit role taxonomy and make the app own it.

| Role | Access | Responsibility |
|------|--------|----------------|
| **Seminary Manager** | Desk | Module administrator; full CRUD (+workflow) on academic & config doctypes. |
| **Registrar** | Desk | Student-records lifecycle: admissions, enrollment, academic terms, withdrawals, graduation, transcripts, disciplinary records. |
| **Program Chair** | Desk | Programs & curriculum authority: programs, courses, assessments, grading, academic policy. |
| **Instructor** | Desk | Teaches & grades own courses; may report disciplinary incidents. |
| **Student / Alumni / Student Applicant** | Portal | Own records, submissions, published curriculum. |

Key moves:

- **Rename `Academics User` → `Program Chair`** (the only role rename). The
  `Instructor` role keeps its name and is no longer treated as a grading-only
  role. A single, unambiguous rename — `Academics User` is always a role —
  avoids any collision with the `Instructor` doctype/role string.
  - DB: `patches/rename_academics_user_to_program_chair.py` runs
    `frappe.rename_doc("Role", ...)`, which cascades `tabDocPerm.role` and
    `tabHas Role.role`. The doctype JSON, workflow fixtures, report/page/
    onboarding role lists are updated as source of truth so `bench migrate`
    doesn't re-import the old name.
  - The rename moves **all** former Academics User holders to Program Chair.
    Staff who do records work must additionally be granted **Registrar** — that
    user-data split can't be automated.
- **App owns its roles.** `install.py` now creates `Program Chair` and
  `Seminary Manager` (alongside Registrar, Instructor, Student, Alumni, Student
  Applicant). No dependency on ERPNext Education roles.
- **By-function re-grant** of permissions: records-lifecycle doctypes and
  workflows move to Registrar with Program Chair trimmed to read; curriculum/
  grading stays with Program Chair; `Seminary Manager` parity is restored
  wherever it was forgotten; the `System Manager`-only doctypes gain proper
  roles; `Instructor` is added to `Disciplinary Incident` so faculty can report.
  Field-level (`permlevel > 0`) perms and portal/Accounts/HR roles are preserved
  untouched. The transformation is recorded in `scripts/regrant_seminary_perms.py`
  and `scripts/regrant_seminary_config_roles.py`.

The portal-facing `is_instructor` / `is_evaluator` / `is_moderator` flags in
`get_user_info` keep their (LMS-derived) names to avoid churning the frontend;
only the roles they check were updated. `is_instructor` is true for **either**
`Instructor` or `Program Chair` (both get the instructor course view — the
frontend `Courses` page switches student/instructor views on this flag), and
`is_evaluator` stays mapped to `Instructor`.

## Consequences

Easier: each role has one clear job; the Registrar is a first-class operator; the
app installs its own roles on any site. Harder: existing Academics User accounts
that did registrar work need the Registrar role added post-migration; the LMS
portal flag names no longer literally match the Seminary role names (documented
inline where they're set).
