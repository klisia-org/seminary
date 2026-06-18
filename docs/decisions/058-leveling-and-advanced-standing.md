# 058 — Leveling and advanced-standing (entrance-conditioned requirements)

**Date:** 2026-06-18
**Status:** Accepted — implemented 2026-06-18 (forks resolved same day; "Required leveling blocks graduation" confirmed)

## Context

The [configuration audit](research/graduation-requirement-configuration-audit.md) flagged, and
[ADR 057](057-graduation-eligibility-floors.md) deferred, the last gap: requirements that vary by a
student's **entrance status**. Two faces of the same thing:

- **Leveling** — a student lacking a prerequisite (e.g. no biblical languages) must take remedial
  courses that don't count toward the degree.
- **Advanced standing** — a student who already has the competency is *exempted* from otherwise-
  mandatory courses or requirements.

Three properties the seminary needs (from the request):

1. **Standard profiles cover most cases** — the common entrance situations (e.g. "No Greek/Hebrew",
   "Transfer from accredited seminary", "Undergrad in Bible") should be registered once and applied
   quickly.
2. **The process is full of exceptions** — applying a profile must just *seed editable rows on the
   Program Enrollment*; the registrar then overrides freely per student. A profile is a convenience
   template, never a binding policy. Ad-hoc rows with no profile must also work.
3. **Mixed, score-gated outcomes** — a placement exam's *score* decides the consequence: e.g. waive
   Greek I; or Greek I & II; or I, II & III; plus the leveling courses still owed below the threshold.

This is a *per-student* axis, distinct from emphasis (a declared sub-program) and from the
program-flat requirement set. The design leans almost entirely on existing machinery.

## Decision

### 1. A per-student Leveling Plan on the Program Enrollment, seeded by reusable Profiles

Mirror the graduation-requirement **template → snapshot → edit** idiom (ADR 012):

- **`Leveling Profile`** (new, non-submittable, Active/Retired like `Graduation Requirement Item`;
  registered once for the common cases — property 1). Optional `program` filter, else reusable across
  programs. Holds **one flat child table** of leveling items (shape in §2).
- **Program Enrollment** gains a `leveling_profile` Link **and** an editable child table
  **`Program Enrollment Leveling`** (same columns as the template). An **Apply Leveling Profile**
  action snapshots the profile's rows into that table (idempotent, like `resnapshot`). The registrar
  then edits/adds/deletes rows freely, or builds the plan ad hoc with no profile at all — property 2.

### 2. One flat item table (no grandchildren), `kind`-discriminated, with per-course score thresholds

[ADR 056](056-course-gated-and-emphasis-scoped-requirements.md) established that **Frappe forbids
table fields on a child doctype** ([[no grandchild tables]]). A tier→many-outcomes rubric would be a
grandchild, so the rubric is **flattened**: every outcome is one row in the single item table, with a
score *threshold per row* rather than a nested tier→outcomes structure.

Columns (identical on template and PE instance):

| field | meaning |
|---|---|
| `kind` | `Placement Assessment` · `Leveling Course` · `Course Exemption` · `Requirement Waiver` |
| `graduation_requirement_item` | Link GRI — on a `Placement Assessment` row, the exam itself; on a `Requirement Waiver` row, the requirement to waive |
| `gating_assessment` | Link GRI — on a `Leveling Course` row, the placement exam whose score gates it. Matches a `Placement Assessment` row's `graduation_requirement_item`. Blank = unconditional. |
| `course` | Link Course — for Leveling Course / Course Exemption |
| `exempt_if_score_at_least` | Float — on a Leveling Course: at/above this score the course is *placed out* instead of required (blank = always required) |
| `score` *(PE instance only)* | the recorded exam score that drives resolution |
| `resolution` *(PE instance only)* | `Pending` · `Required` · `Exempt` · `Waived` — computed, overridable |
| `note` | free text |

**What groups rows under one exam** is a real Link, not a magic string: each `Leveling Course` row's
`gating_assessment` points at the same GRI as its `Placement Assessment` row. The tiered Greek case is
flat — one `Placement Assessment` + one `Leveling Course` per language course with its own threshold:

```
kind=Placement Assessment  graduation_requirement_item="Greek Placement Exam"
kind=Leveling Course  course="Greek I"    gating_assessment="Greek Placement Exam"  exempt_if_score_at_least=60
kind=Leveling Course  course="Greek II"   gating_assessment="Greek Placement Exam"  exempt_if_score_at_least=75
kind=Leveling Course  course="Greek III"  gating_assessment="Greek Placement Exam"  exempt_if_score_at_least=90
```

A score of 80 → Greek I & II resolve `Exempt`, Greek III `Required`. No `gating_assessment` /
threshold → `Required` (leveling) or `Exempt`/`Waived` (advanced standing) unconditionally — property 3.
The PE form can populate the `gating_assessment` picker from the `Placement Assessment` rows in the
same table, so the registrar never types a free identifier.

### 3. The placement exam reuses a Manual Verification graduation requirement (+ a score field)

Rather than a new exam doctype, a Placement Assessment **points at a `Manual Verification`
Graduation Requirement Item** (ADR 012). The student's exam already rides the SGR machinery — shows on
the audit, staff-verified with evidence, waivable. The only addition is a **`score` (Float) on
Student Graduation Requirement**, captured at verification. When the exam's SGR is verified, a resolver
reads its score and resolves every `Leveling Course` whose `gating_assessment` is that exam (≥
threshold → `Exempt`, else `Required`). Re-verifying with a new score re-resolves (overridable
afterward).

### 4. Outcomes ride existing systems

- **`Leveling Course` (Required)** → appended to **`Program Enrollment Required Course`** (ADR 035),
  so the student is back-enrolled and must pass it. Leveling courses keep their **real credit value**
  (so they still pass Program validation, which checks credits > 0) but the resulting
  `Program Enrollment Course` is flagged **`non_degree_credit`**; `_refresh_totalcredits` excludes
  flagged rows, so they gate without inflating `credits_complete`. (We do **not** use 0-credit
  Courses — Program validation rejects those.)
- **`Course Exemption` / placed-out `Leveling Course`** → write a `Program Enrollment Course` row with
  a new **`Exempt`** status (`status` is free-form `Data`, so no enum change). This single
  representation is what *every* consumer already reads — which is exactly what property 5 needs:
  - **candidacy** counts `Exempt` as satisfied: `satisfied = {Pass, Exempt}`, so
    `mandatory_program − satisfied` clears the exempted course;
  - **Course Passed activation** ([graduation.py](../../seminary/seminary/graduation.py)
    `evaluate_activation`) matches `status IN ('Pass','Exempt')`, so a placed-out course **activates**
    any PGRI gated on it (property 5);
  - `Exempt` carries **no grade and no credit** — excluded from GPA (`count_in_gpa`) and from
    `totalcredits`. Exemption clears the *requirement*, it does not grant credit.
  A derived exempted-set (no PEC row) was rejected precisely because `evaluate_activation` and the
  transcript would not see it.
- **`Requirement Waiver`**, and the property-5 cascade → reuse the first-class SGR waiver
  (`graduation.waive_sgr`). When the resolver exempts a course it **also** waives any SGR whose
  fulfilling document/requirement is that course (one action, both effects), with a waiver reason
  naming the leveling plan.

### 5. A pre-enrollment "needs review" flag (not a pre-enrollment plan)

We deliberately do **not** build the leveling plan before enrollment — submitted transcripts can't be
authenticity-checked yet, so resolving real outcomes pre-enrollment is unsafe. Instead the
application carries a lightweight **`requests_requirement_review`** Select (`None` / `Leveling` /
`Exemption / Advanced Standing` / `Both`). On acceptance it raises a **Registrar ToDo** (and a small
"Applicants flagged for requirement review" report) so the registrar proactively builds the leveling
plan on the new PE. It is only a signal — it carries no outcomes.

So the whole feature adds **two doctypes** (`Leveling Profile`, `Program Enrollment Leveling`), **one
SGR field** (`score`), **one PEC status** (`Exempt`) + **one PEC flag** (`non_degree_credit`), **one
application field** (`requests_requirement_review`), and a small resolver — otherwise reusing
required-on-enroll, candidacy, Course-Passed activation, SGR/Manual-Verification + waivers, and the
snapshot-then-edit pattern.

## Consequences

- **Easier:** common entrance cases are one-click (apply a profile); every case is fully overridable
  on the PE; score-gated waivers are data, not code. Leveling/advanced-standing finally has a home
  without bolting onto emphasis or the program-flat policy.
- **New surface:** a resolver that maps score → resolution per gating exam (must re-run on re-score
  without clobbering manual overrides), plus small changes so candidacy **and** Course-Passed
  activation treat `Exempt` as satisfied. All small and testable.
- **Catalog-year interaction:** the leveling plan lives on the PE (per-student), seeded at/after
  enrollment; it is *not* frozen to a catalog version (it's about *this* student's entry), which is
  the right semantics — but it means editing it post-submit must follow the allow-on-submit + audit
  conventions the SGR table already uses.

## Resolved (review, 2026-06-18)

- **Non-degree-credit:** flag the PEC `non_degree_credit` and exclude from `totalcredits` — keep real
  credits (0-credit Courses fail Program validation).
- **Exemption representation:** a real PEC `Exempt` row, because Course-Passed activation, candidacy,
  and the transcript all read PEC — and property 5 needs all three.
- **Entry status:** PE-only plan + a pre-enrollment `requests_requirement_review` flag (no
  pre-enrollment resolution; transcripts aren't authenticated yet).
- **Profile scope:** global with an optional `program` filter.
- **Placed-out course that is also a graduation requirement:** auto-waive the SGR *and* activate any
  Course-Passed PGRI (both fall out of the `Exempt` PEC row + the resolver's waive step).

## Open questions

- **Do *Required* leveling courses block graduation** (not just enrollment)? ADR 035 required-on-enroll
  gates enrollment; a leveling course almost certainly must be *passed* to graduate. Leaning: an
  unmet Required leveling row blocks candidacy (treat like a mandatory course). Confirm.
- **Re-score after manual overrides:** the resolver must not clobber a registrar override when an
  exam is re-verified — needs an "overridden" marker on the row (mirror the SGR waiver-preserve idiom).
- **Exact home of `requests_requirement_review`:** Student Applicant vs the Term Admission program
  detail (ADR 019). Minor; pick at implementation.
