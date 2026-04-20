---
# Configuration - fill in metadata when accepted
status: proposed
date: 2026-04-19
decision-makers: Murilo Melo
consulted:
informed:
---

# Grade Conversion as a Standalone Policy Entity

## Context and Problem Statement

With the unified Partner Seminary model in place (see related ADR), SeminaryERP must translate grades recorded on a partner institution's scale into grades on the receiving seminary's scale. Partner scales vary widely: French/Francophone 0–20, Brazilian 0–10, percentage 0–100, letter A–F with various grade-point conventions, narrative grades ("Distinction," "Merit," "Pass").

Two facts make this non-trivial:

1. **The same scale can require different conversions for different partners.** A strong Francophone seminary's 17/20 might be treated as equivalent to an A in the receiving scale; a weaker partner's 17/20 might only warrant a B+. Same source scale, different conversion factor, based on the receiving registrar's assessment of institutional quality.
2. **Conversion method varies.** Some conversions are linear (multiply 0–20 by 5 to get 0–100). Some are interval-based letter-to-letter mappings (partner's A- → our B+). Some require per-course manual judgment.

The existing `Grading Scale` doctype (with child table `Grading Scale Interval`) defines scales in an institution-agnostic way: a scale is a set of intervals with symbols, grade points, and passing thresholds. The open question is where to put the *conversion policy* between two scales.

## Decision Drivers

* **Reusability of scale definitions.** Common scales (ECTS 0–20, percentage, US letter) should be defined once and reused across many partner seminaries rather than duplicated per partner.
* **Per-partner differentiation.** Two partners using the same nominal scale may still warrant different conversions based on the registrar's quality assessment.
* **Method flexibility.** The system must handle linear conversion, interval-based symbol mapping, and per-course manual overrides without forcing all cases into one method.
* **Debuggability.** A registrar asked "why did this student's 17/20 become a B+?" must be able to inspect the conversion logic in the admin UI.
* **Separation of concerns.** A grading scale *is* (a definition); a conversion policy *does* (transforms values between definitions). Conflating the two muddies both.

## Considered Options

* **Option A: `is_external` flag on `Grading Scale`** — mark scales as internal vs. external; store conversion factor on the external scale record itself.
* **Option B: Conversion fields on `Partner Seminary`** — put a grading scale reference plus a conversion multiplier (or interval mapping child table) directly on the Partner Seminary doctype.
* **Option C: Standalone `Grade Conversion Policy` doctype** — a separate entity that references two Grading Scales (source and target) and defines how to convert between them; Partner Seminary references a default policy; per-course overrides possible.

## Decision Outcome

Chosen option: **Option C — Standalone `Grade Conversion Policy` doctype**, because it cleanly separates scale definition (institution-agnostic) from conversion policy (relationship-specific), supports multiple conversion methods via a `conversion_method` select field, and allows the same source scale to have different policies for different partners without duplicating scale records.

### Doctype Shape

**`Grade Conversion Policy`** (new doctype)

* `policy_name` (Data) — descriptive label, e.g., "ESWA — Francophone Strong ×5", "ESWA — Francophone Baseline ×4.2", "ESWA — Identity (Legacy)".
* `source_grading_scale` (Link → Grading Scale) — the scale grades come in on.
* `target_grading_scale` (Link → Grading Scale) — the scale grades are converted to (typically the receiving seminary's internal scale).
* `conversion_method` (Select) — one of: `identity`, `linear_multiplier`, `linear_with_offset`, `interval_map`, `manual_per_course`.
* `multiplier` (Float) — shown when method is `linear_multiplier` or `linear_with_offset`.
* `offset` (Float) — shown when method is `linear_with_offset`.
* `conversion_map` (Table → Grade Conversion Map) — shown when method is `interval_map`; rows contain `source_symbol`, `target_symbol`. The target-scale grade-point value is resolved at conversion time via the `threshold` field on the matching `Grading Scale Interval` row (not denormalized onto the map).
* `notes` (Text) — registrar's rationale for the policy, visible to future reviewers.

`threshold` on `Grading Scale Interval` is a Float representing the minimum numeric value (in the scale's native units) that earns the grade code — it serves the grade-point role for both numeric and narrative scales. Narrative scales (e.g., "Distinction / Merit / Pass") are handled via `interval_map`; the source `Grading Scale` populates `threshold` with grade-point values (Distinction = 4.0, Merit = 3.0, Pass = 2.0). Linear methods (`linear_multiplier`, `linear_with_offset`) are invalid for narrative sources; policy-save validation rejects the combination.

`target_grading_scale` must equal the receiving institution's configured internal scale. V1 assumes one internal scale per seminary; per-program scales are future work and would relax this constraint.

**`Grading Scale`** (existing, unchanged)

* Remains institution-agnostic. Shared across internal and partner use.

**`Partner Seminary`** (referenced from the related ADR)

* `default_grading_scale` (Link → Grading Scale).
* `default_conversion_policy` (Link → Grade Conversion Policy).
* Other fields covered in the related ADR (credit unit, minimum transferable grade, accreditation status, etc.).

**`Partner Seminary Course Equivalence`** (submittable)

* `conversion_policy_override` (Link → Grade Conversion Policy, optional) — used when a specific course on a partner's transcript uses a different scale than the partner's default (rare but real: a partner's music department using a pass/fail scale while the rest uses 0–20).
* Submittable (`is_submittable = 1`): equivalences follow the same draft → submit → amend lineage as Grade Conversion Policy (see "Submittable Doctype for Change Traceability" below). An equivalence is a formal registrar decision and deserves the same auditable trail.

### Pass/Fail and Minimum Transferable Grade

Conversion executes first; the receiving institution's `Partner Seminary.minimum_transferable_grade` is then evaluated against the **converted** target-scale grade, not the source grade:

* If the converted grade falls below minimum, the grade-entry form blocks save and surfaces a clear message. A registrar with elevated permissions can override, recording a reason on the transcript entry (stored in `conversion_override_note`).
* This means a passing source grade (e.g., 10/20 in a French scale with passing threshold of 10) that linearly converts to a failing receiving grade (50/100 in a scale with passing threshold of 60) is flagged by default — the policy intent is that transferred credits meet the receiving institution's standards.
* The partner's own pass/fail threshold is informational only (visible for context on the entry form); it does not override the receiving threshold.

### Rounding and Target-Symbol Resolution

Linear methods produce a float on the target scale. That float is resolved to a target-scale symbol by finding the `Grading Scale Interval` whose bounds contain the value; the interval's grade points are recorded on the transcript entry.

* Intermediate arithmetic keeps 2 decimal places; rounding is half-up.
* If the converted value exceeds the target scale's maximum interval, it is clamped to that interval and the transcript entry records a `conversion_warning: clamped_high`.
* If below the minimum, it is clamped to the lowest interval (typically a fail) with `conversion_warning: clamped_low`.
* Clamping is never silent — the warning surfaces in the registrar's view and in audit reports.

### Manual Per-Course Method

When `conversion_method = manual_per_course`, the grade-entry form prompts for both the source grade and a directly-entered target-scale grade — no arithmetic runs. The target grade is stored in the same transcript field used by other methods, so downstream reporting is method-agnostic.

### Submittable Doctype for Change Traceability

`Grade Conversion Policy` is a submittable doctype (`is_submittable = 1`). This leverages Frappe's built-in draft → submitted → cancelled state machine and the amendment pattern to deliver versioning and traceability essentially for free:

* **Draft** — the registrar tunes fields freely while authoring a new policy. Draft policies cannot be referenced by transcript entries or selected from a Partner Seminary's `default_conversion_policy`.
* **Submitted** — the policy becomes canonical and read-only. Only submitted policies can be linked from a Partner Seminary's `default_conversion_policy` or a Partner Seminary Course Equivalence override.
* **Amend** — when a policy needs to change, the registrar cancels and amends. Frappe creates a new document linked via `amended_from`; the cancelled original is retained. Existing transcripts continue to reference the original by ID, so historical conversions remain reproducible.
* `policy_name` and `notes` remain editable on a submitted policy without cancellation (via Frappe's `allow_on_submit` per-field flag) for clarifying labels and rationale without breaking references.

This supersedes a simpler "field-level immutability if in use" pattern and provides a first-class audit trail — every change produces a new document whose lineage is queryable. The future-work item on policy versioning is partially delivered by this choice; per-entry snapshotting can be added later as additional hardening for cases where the `amended_from` chain isn't sufficient.

`Partner Seminary Course Equivalence` uses the same submittable pattern. Combined with the `supporting_document` attach field defined in ADR 005, this gives a complete auditable record of every equivalence decision: who submitted it, when, the policy that applied, and the authorizing artifact.

### Consequences

* **Good**, because one `Grading Scale` record for "0–20 French" serves all Francophone partners. Per-partner differentiation lives in the policy, not the scale.
* **Good**, because the legacy use case fits naturally: an "Identity" policy (source scale = target scale = internal scale, method = `identity`) is created once and reused for all legacy Partner Seminary records. No special-case code needed.
* **Good**, because interval-based conversion keeps grade-point arithmetic honest. Mapping source symbol → target symbol, then reading grade points from the target scale's own intervals, avoids the trap of directly converting grade points across scales (which can produce values that don't correspond to any valid grade on the target scale).
* **Good**, because the policy is inspectable and editable in the Frappe Desk — a registrar can see exactly why a grade converted the way it did.
* **Good**, because per-course override is available for the occasional odd case without requiring a new doctype.
* **Bad**, because the setup workflow is slightly more verbose: creating a new partner requires creating (or reusing) both a Grading Scale and a Conversion Policy. This is mitigated by shipping common policies as fixtures ("Identity", "Francophone 0–20 to Letter A–F Standard", "Percentage to Letter A–F Standard") and by the reusability of both entities across partners.
* **Bad**, because a registrar could create inconsistent or redundant policies (e.g., two nearly-identical ×5 policies under different names). This is a naming/governance issue rather than a structural one; a list view with `source_scale`, `target_scale`, `method`, `multiplier` visible surfaces duplicates quickly.
* **Neutral**, because the conversion logic lives in a single well-named place that future contributors and LLM-assisted modifications can reason about locally.

### Confirmation

Implementation will be validated by:

* Creating fixture policies for identity, linear ×5 (Francophone strong), linear ×4.2 (Francophone baseline), and an interval map (partner letter grades → internal letter grades), and confirming each produces correct output on representative inputs.
* Verifying that two partners can share the same `Grading Scale` record but reference different `Grade Conversion Policy` records, and that their transcripts convert independently.
* Verifying that the legacy identity policy produces byte-identical output to its input across a sample transcript.
* Submitting a policy and then amending it produces a new document with `amended_from` pointing at the original; existing transcripts continue to reference the original policy ID.
* A draft policy cannot be selected from a Partner Seminary's `default_conversion_policy` field — only submitted policies.
* A narrative partner scale with `interval_map` converts correctly, and the same policy saved with `linear_multiplier` is rejected at save time.
* Out-of-range source grades produce clamped target grades with a visible `conversion_warning` on the transcript entry.
* Running the Legacy Bulk Import workflow end-to-end on a ≥50-row sample: stage → resolve equivalences → dry-run → reconcile (with a deliberate data error) → commit produces the expected transcript entries, and a second commit with one corrected row updates in place without duplicating.
* Code review confirming grade conversion logic lives in a single service/utility that takes a `Grade Conversion Policy` and a source grade as inputs — no conversion arithmetic scattered across doctype hooks.

## Pros and Cons of the Options

### Option A: `is_external` flag on `Grading Scale`

* Good, because it requires no new doctype.
* Bad, because a grading scale is not inherently internal or external — the same definition (e.g., 0–10 Brazilian) could plausibly be used internally by a program and externally by a partner.
* Bad, because the same scale often needs different conversions per partner; storing conversion on the scale forces duplicating the scale per partner to get per-partner differentiation.
* Bad, because it conflates definition with policy — a conceptual error that compounds over time as features accumulate on `Grading Scale`.
* Bad, because it does not accommodate interval-based mapping without a second layer of fields that make the flag even leakier.

### Option B: Conversion fields on `Partner Seminary`

* Good, because it keeps everything scoped to the partner.
* Bad, because the conversion policy is not reusable across partners — two partners using the same policy must maintain it in two places.
* Bad, because per-course overrides require duplicating the conversion fields on the equivalence doctype, further fragmenting the logic.
* Bad, because auditing "which partners use this conversion method?" becomes a cross-record query rather than a reverse link.

### Option C: Standalone `Grade Conversion Policy` doctype

* See Decision Outcome above.

## More Information

* Related: 005-unified-partner-seminary-model.md — this ADR's structural decisions depend on the unified-pathway premise established there.
* Future work:
    * Expose a "Test this policy" admin UI: input a source grade, see the converted target grade and grade points, with a side-by-side breakdown. Useful for registrar confidence-building during setup.
    * Extend `conversion_method` with a `formula` option (safe expression evaluated against the source grade) for the rare non-linear case. Deferred until a concrete need appears.
    * Versioning of policies — if a registrar updates a policy, past transcript entries should retain the policy that was applied at the time. Approach: snapshot the policy values onto the transcript entry record at grade-entry time rather than referencing the policy live. Not implemented in v1 but the grade-entry doctype should include the fields needed to store a snapshot when this is added.
