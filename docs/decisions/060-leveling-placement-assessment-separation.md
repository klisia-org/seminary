# 060 — Separate leveling placement assessments from graduation requirements

**Date:** 2026-06-18
**Status:** Implemented 2026-06-18 (with ADR 059 Stage 2)

## Context

[ADR 058](058-leveling-and-advanced-standing.md) shipped leveling by **reusing the graduation-
requirement machinery** for placement exams: a placement exam is a `Manual Verification`
**Graduation Requirement Item**, its score is recorded on a **Student Graduation Requirement** (SGR)
row, `leveling._exam_scores()` reads `pe.graduation_requirements[].score`, and
`graduation.mark_sgr_verified(score=)` writes it.

In use this proved confusing: a *placement exam* (an intake/leveling concern) shows up in the
student's **graduation-requirement** list and audit, mixing two unrelated lifecycles. Putting
leveling content into the graduation policy "makes a mess" (the user's words). The coupling was a
reuse convenience, not the right model.

This ADR separates them. It builds loosely on [ADR 059](059-seminary-departments-and-faculty-capabilities.md)
(a placement exam is graded by a department-bound **Placement Examiner** capability) but does not
structurally depend on it and could ship independently.

## Decision

Give leveling its **own** placement-assessment concept; stop riding `Graduation Requirement Item` /
SGR.

1. **`Placement Assessment`** — a small **global/shared** Setup catalog (e.g. *Greek Placement Exam*,
   *Hebrew Placement Exam*): `assessment_name`, `academic_unit` (Link → Academic Unit — the owning unit
   whose **Placement Examiner** capability grades it, ADR 059 §7), `is_active`, optional `description`.
   It stays **thin**: per-course thresholds keep living on the leveling row (`exempt_if_score_at_least`),
   so the assessment reference (`gating_assessment`) and the threshold sit **in the same place** — the
   leveling row. Replaces "point a leveling row at a GRI."
2. **`Program Enrollment Placement Assessment`** — a new child table on Program Enrollment owned by
   leveling: `assessment` (Link → Placement Assessment), `score` (Float), `status`, `verified_by`,
   `verified_on`, plus private `student_evidence_attachment` / `staff_evidence_attachment` (Attach). The
   score lives **here**, not on an SGR. **Kept a child table** (not a standalone doctype) to match the
   SGR precedent: portal exposure is a curated projection (never the raw PE), writes are
   ownership/capability-checked actions, and the Attach fields are private with file ACL chained to PE
   read-permission (ADR 043). Promote to a standalone doctype only if examiners later need direct
   row-level portal writes — the field shapes won't change.

   **CP reader composition is policy, set on `Culminating Project Type`, not per project.** The type
   carries `apply_reader_policy` (master toggle), `readers_required` (0–2 — a project has exactly two
   named slots, Second + Third Reader; extra reviewers go on the committee), and per-slot
   `second_reader_type` / `third_reader_type` (Instructor / External Examiner) plus, for instructor
   slots, `*_allow_other_units`. When the policy applies, the project **inherits and is validated against**
   it: each slot's type is fixed, slots beyond `readers_required` are forbidden, and an instructor reader
   must belong to the project's Academic Unit unless other units are allowed. The single `reader_scope`
   Select was replaced by these per-slot controls. The **advisor** has its own two gates: it is *always*
   restricted to **qualified Thesis/CP Advisors with capacity** (a wide net across all units —
   `faculty.capability_holders` for the picker, `faculty.holds_capability` enforced in `assign_advisor`),
   and `advisor_from_academic_unit` adds an optional second gate narrowing that pool to the project's
   unit, with an off switch so a dean can step in. (Readers, by contrast, are gated by unit *membership*,
   not capability.)

   Evidence is configured on the global **`Placement Assessment`** (mirroring Graduation Requirement
   Item): `default_student_evidence_required` / `default_student_evidence_label` and
   `default_staff_evidence_required` / `default_staff_evidence_label` drive what the portal surfaces;
   `mark_placement_scored` takes an optional `attachment_url` for the examiner's evidence.
3. **Repoint the leveling rows.** In `Program Enrollment Leveling` and the `Leveling Profile` items,
   the `Placement Assessment` `kind` and a leveling course's `gating_assessment` link
   `Graduation Requirement Item` → `Placement Assessment`. The `Requirement Waiver` kind **stays** →
   `Graduation Requirement Item` (it genuinely waives a graduation requirement — that coupling is
   correct and should remain).
4. **Decouple the code** (touch points):
   - `leveling.py::_exam_scores()` — read scores from the new placement-assessment child, not
     `pe.graduation_requirements`.
   - `leveling.py::_resolve_rows()` / `apply_leveling_profile()` — resolve `gating_assessment` against
     placement assessments; drop the GRI dedup key.
   - `graduation.py::mark_sgr_verified()` — **remove the `score` parameter** and the leveling trigger;
     it goes back to being purely a graduation-requirement verification. Scoring a placement exam
     becomes a leveling action **`mark_placement_scored(program_enrollment, assessment, score)`** that
     writes the placement child and fires the existing `resolve_rows_hook`. Its authorized verifier is
     a **department-bound Placement Examiner** (ADR 059 §3–5) rather than generic "staff."
   - `graduation.py::_build_sgr_row` / `_append_pgr_item_rows` — no longer special-case placement exams.
5. **No migration.** ADR 058 was never put in production, so there is no real placement-SGR data to
   convert — the field/link changes ship without a data patch. (The `score` field simply leaves SGR; the
   new placement child starts empty.)

## Consequences

- **Easier:** the graduation-requirement list/audit shows only real graduation requirements; leveling
  owns its exams end-to-end; placement grading routes to a department Placement Examiner queue
  (ADR 059) instead of generic staff. `mark_sgr_verified` gets simpler.
- **Harder / cost:** a one-time migration of existing placement SGRs; two new doctypes; `leveling.py`
  and `graduation.py` edits. Because ADR 058 is freshly shipped, real placement data is minimal, so
  the migration blast radius is small.
- **Unchanged:** the leveling resolution logic (score → Exempt/Required tiers), candidacy effects, and
  the `Requirement Waiver` → GRI path all stay as in ADR 058 — only the *exam/score storage* moves.

## Resolved

- **Scope** — Placement Assessment is a **global/shared** catalog; thresholds stay per-course on the
  leveling row (`exempt_if_score_at_least`), so the catalog is thin.
- **Sequencing** — shipped **together with ADR 059**: placement grading routes to a department
  **Placement Examiner** from day one (the assessment's `academic_unit`), and `mark_placement_scored`
  is authorized against that capability.
- **Migration / backfill** — none; ADR 058 is not in production.
