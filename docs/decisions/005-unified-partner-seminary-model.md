---
# Configuration - fill in metadata when accepted
status: proposed
date: 2026-04-19
decision-makers: Murilo Melo
consulted:
informed:
---

# Unified Partner Seminary Model for Legacy Data and Transfer Credits

## Context and Problem Statement

SeminaryERP needs to support two superficially distinct use cases for ingesting prior coursework into a student's record:

1. **Legacy data backfill.** A seminary adopting SeminaryERP after years of operation has historical course enrollments and grades recorded elsewhere (another system, spreadsheets, paper files). These must be loaded so that continuing students have complete transcripts, degree audits reflect actual progress, and GPAs are accurate.
2. **Transfer credit acceptance.** A student arrives from another institution with coursework the receiving seminary may accept toward its own degree. Course titles, credit hour conventions, grading scales, and academic quality all differ, and the receiving registrar evaluates equivalence course-by-course.

The business processes feel different — legacy import is a one-time bulk registrar activity, transfer credit is a recurring per-student evaluation — which invites a design with two parallel modules. However, the underlying data shape is nearly identical: a source institution, a source course with a code and credit value on some grading scale, a receiving-institution course it maps to, and a grade that needs to be recorded against the student's transcript.

The question is whether to build one pathway or two.

## Decision Drivers

* **Forward compatibility.** Seminaries in the target deployment contexts (Liberia, Ghana, Nigeria, Brazil) will need both capabilities over their lifetime with SeminaryERP. Legacy import happens at onboarding; transfer credit recurs indefinitely.
* **Registrar mental model.** Registrars already think of "where did this credit come from?" as a single question. Splitting legacy and external transfer into different screens fragments a unified concept.
* **Code path count.** Two modules means two grade-entry UIs, two validation paths, two reporting surfaces, two sets of bugs. The project is maintained by a small team with limited contributor bandwidth.
* **Reporting and audit.** Accreditation reviews and internal audits ask "what percentage of this student's credits were earned at this institution vs. transferred in?" A unified model answers this with a single query; a split model requires union logic.
* **Migration risk.** If the two modules diverge and later need to be merged, the migration touches live transcript data — a high-stakes operation.

## Considered Options

* **Option A: Two separate modules** — a "Legacy Grade Import" tool and a "Transfer Credit" module, each with its own doctypes and flows.
* **Option B: Unified Partner Seminary model** — a single pathway where the originating institution is always modeled as a `Partner Seminary`, including the receiving seminary's own historical self ("ESWA Legacy (pre-2026)" as a Partner Seminary record).
* **Option C: Transfer module only, with legacy as a bulk-import shortcut** — one module, but legacy treated as a special code path within it (e.g., `if is_legacy: skip_equivalence_evaluation`).

## Decision Outcome

Chosen option: **Option B — Unified Partner Seminary model**, because it collapses two use cases into one set of doctypes, one grade-entry pipeline, and one reporting surface, while the "legacy as self-referential partner" framing is conceptually honest: historical coursework genuinely did come from a prior instance of the institution that predates the current system.

The legacy case is handled as a degenerate instance of the transfer case:

* A `Partner Seminary` record is created for the institution's pre-SeminaryERP history (e.g., "ESWA Legacy (pre-2026)").
* Its default grading scale equals the internal grading scale.
* Its default grade conversion policy is an identity policy (no conversion applied).
* All course equivalence rows are self-mappings with `mapping_type: legacy_identity`.
* Manual transcript entry flows through the same pipeline as true external transfers; because the conversion policy is identity and equivalences are self-mappings, no transformation runs.

### Credit Unit Conversion

Credit unit conversion is orthogonal to grade conversion and lives on the Partner Seminary / equivalence records, not in the Grade Conversion Policy:

* `Partner Seminary.credit_unit_ratio` (Float) — default internal credit hours per 1 partner credit unit (e.g., 0.5 for 1 ECTS → 0.5 US credit hour).
* `Partner Seminary Course Equivalence.credit_override` (Float, optional) — overrides the default for the unusual case (lab, half-course, compressed term).
* Transcript entries store the **resolved internal credit** at entry time; subsequent changes to `credit_unit_ratio` do not retroactively shift existing transcripts.

For self-referential legacy Partner Seminaries, `credit_unit_ratio = 1.0`.

### GPA Participation

Partner Seminary defines whether its converted grades participate in GPA math:

* `Partner Seminary.counts_in_gpa` (Check) — defaults to **False** for external partners (industry-standard: transfer credits count toward the degree but not the GPA); defaults to **True** for self-referential legacy records (these ARE the institution's own historical grades).
* When `False`, transcript entries render a "T" / "transferred" marker in place of a letter grade on the student-facing transcript and are excluded from GPA aggregation, but `target_grade_points` is still recorded for degree-audit tie-breaks and reporting.
* This keeps the GPA decision a per-partner policy rather than a global one; a seminary that does count external transfer in GPA can flip the default at setup.

### Partner Seminary Lifecycle

* `status` (Select: Active / Inactive / Archived) — Inactive partners cannot be selected for new equivalences; existing transcripts remain valid. Archived hides from most UIs; used when a partnership has irrevocably ended.
* `is_internal_legacy` (Check, read-only after creation) — identifies self-referential legacy records. Prevents deletion regardless of reference count and filters these records out of the default Partner Seminary list view (admins can toggle visibility).
* Deletion is blocked when any transcript entry references the Partner Seminary; registrars archive instead.
* Renaming a Partner Seminary record is non-breaking. Merging two partner records (same institution, different entries) is out of scope for v1 and will need a supervised data migration.

### Course Equivalence Decision Trail

`Partner Seminary Course Equivalence.supporting_document` (Attach, optional) stores the decision artifact — director approval email, committee minutes, accreditor letter — for seminaries that want an auditable record of who authorized the equivalence and on what basis. Not required by v1 workflows but available from day one so the trail exists when it matters. Combined with the submittable-doctype pattern (see ADR 006), this gives a complete audit chain: who submitted the equivalence, when, and the authorizing artifact.

### Legacy Bulk Import Workflow

The unified model is designed to support full system migration — not just one-off legacy entries — so the same workflow applies whether a seminary is onboarding 20 years of history or ingesting a single transferring student's transcript.

**Setup (one-time per institution):**

1. Create the self-referential Partner Seminary record (`is_internal_legacy = True`, `counts_in_gpa = True`, `credit_unit_ratio = 1.0`, `default_grading_scale = internal scale`).
2. Create (or select the shipped fixture for) the Identity Grade Conversion Policy and submit it. Link it as the partner's `default_conversion_policy`.
3. Verify Programs, Courses, Academic Terms, and the internal Grading Scale exist for every period covered by the import.

**Per-migration batch:**

1. **Stage** — source data (CSV/Excel) is loaded into a holding doctype (`Legacy Transcript Import Row`) with columns for student, source course code, source term, source grade, credit value, and optional `external_reference`. Rows remain in Draft until reviewed.
2. **Resolve equivalences** — unique source course codes are surfaced; the registrar either maps each to an existing internal Course or promotes a provisional mapping. Equivalences are drafted here and must be submitted before the batch can commit (see ADR 006 for the submittable pattern). For legacy self-referential imports, equivalences are auto-generated as `mapping_type: legacy_identity` self-mappings and auto-submitted at the end of this step since there is no per-mapping judgment call to make.
3. **Dry-run validate** — the importer computes for every row: resolved internal course, resolved credit (`credit_unit_ratio × value` or override), converted grade (identity for legacy), and flags warnings (missing course, out-of-range grade, failed `minimum_transferable_grade` check). No transcript entries are created yet.
4. **Reconcile** — registrar reviews warnings, corrects source data or equivalences, and re-runs the dry-run. Idempotency on `(student, partner_seminary, source_course_code, source_term)` — or `external_reference` when present — means re-runs update rather than append.
5. **Commit** — on registrar approval, the batch creates transcript entries in a single transaction. Each entry is stamped with the batch ID, the policy ID applied, and the resolved credit value snapshot.
6. **Audit report** — post-commit report lists total students touched, credits recorded, warnings carried forward, and discrepancies vs. source totals (for registrar sign-off).

The workflow is the same for external transfer: steps 1 and 2 produce a single student's batch; steps 3–6 are unchanged. This is the concrete payoff of the unified model — one pipeline, one review UX, one audit trail, regardless of scale.

### Consequences

* **Good**, because one set of doctypes, one grade-entry UI, one reporting surface, one code path to maintain and test.
* **Good**, because accreditation and audit queries can distinguish legacy from true external transfer via the `mapping_type` field on equivalence rows without needing to join across separate tables.
* **Good**, because the design forces the team to model grade conversion and course equivalence cleanly from day one, rather than deferring the harder work to "phase 2" and accumulating legacy-specific shortcuts.
* **Good**, because when the workflow-based transfer credit request/approval flow is added later (see Future Work), it extends the existing pipeline rather than a second one.
* **Good**, because the natural key `(student, partner_seminary, source_course_code, source_term)` on the transcript-entry doctype supports idempotent re-import. An optional `external_reference` field accepts source-system IDs when available and takes precedence over the natural key.
* **Bad**, because legacy bulk import carries slightly more ceremony than a purpose-built importer would — registrars must create the self-referential Partner Seminary and identity policy records before entering data. This is mitigated by shipping these as fixtures or a setup wizard.
* **Bad**, because the term "Partner Seminary" is semantically odd when applied to the institution itself. Naming it "Source Institution" would be more accurate but departs from the registrar vocabulary of "partner institutions." The `mapping_type: legacy_identity` flag makes the distinction visible where it matters.
* **Neutral**, because transferred courses satisfy internal prerequisites by default — the registrar-approved course equivalence is the authoritative signal. Exceptions (e.g., a prerequisite that requires the internal pedagogy specifically) are handled by refusing to create the equivalence, not by a separate prerequisite-override field.
* **Neutral**, because the slight conceptual stretch ("our own past is a partner") is documented here and in user-facing help content, so future contributors encountering the pattern understand the rationale. The Partner Seminary list view filters `is_internal_legacy` records by default; a toggle exposes them to admins during setup and audit.

### Confirmation

Implementation will be validated by:

* Loading a representative legacy transcript (≥50 course enrollments across ≥5 students) from a pilot seminary and confirming the resulting Student records, degree audit output, and GPA calculations match the source data.
* Processing a synthetic external transfer case through the same doctypes and confirming the resulting records are distinguishable from legacy in reports that filter by `mapping_type`.
* Re-importing a corrected legacy batch updates existing entries instead of creating duplicates, verified by running the same importer twice with a modified grade in one row and confirming exactly one row per `(student, partner_seminary, source_course_code, source_term)` tuple remains.
* Code review confirming there is no `if is_legacy` branching in the grade-entry or transcript-rendering code paths.

## Pros and Cons of the Options

### Option A: Two separate modules

* Good, because each module's UI can be tuned to its specific business process without compromise.
* Good, because legacy import can skip equivalence logic entirely, which is slightly simpler for the bulk case.
* Bad, because two parallel data shapes diverge over time — fields added to one are forgotten in the other.
* Bad, because reporting requires union queries across two transcript sources.
* Bad, because the grade-entry code is duplicated, doubling the surface area for bugs.
* Bad, because future workflow features (approval flows, document attachment) must be built twice.

### Option B: Unified Partner Seminary model

* See Decision Outcome above.

### Option C: Transfer module only, with legacy as a bulk-import shortcut

* Good, because it retains a single module.
* Bad, because the `if is_legacy` branches accumulate in validation, conversion, and reporting code — exactly the two-code-paths problem the unified approach is trying to avoid, just hidden inside one module.
* Bad, because it implies legacy data is second-class and skips validation that might catch real data-quality issues during import.

## More Information

* Related: 006-grade-conversion-policy.md — formalizes how grade translation works within this unified pipeline and is a prerequisite for the legacy-as-identity-policy pattern described here.
* Future work:
    * A Credit Transfer Request doctype with request → approval workflow, producing transcript entries on approval. The current ADR covers only the data model and manual grade entry for v1.
    * Many-to-many course equivalence (1:many, many:1, partial). v1 ships with 1:1 only but the doctype structure anticipates the extension (see 006-grade-conversion-policy.md).
    * Per-program residency requirement enforcement — transfer credits flagged so degree audit excludes them from in-house residency minimums. This lives on the enrollment record, not this module, but depends on the `mapping_type` field defined here.
    * Partner Seminary merge tooling — supervised data migration for the case where two partner records turn out to represent the same institution (renamed, reaccredited, or initially mis-typed by different registrars).
