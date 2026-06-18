# 057 — Graduation eligibility floors: GPA minimum and transfer-credit cap

**Date:** 2026-06-17
**Status:** Accepted

## Context

The [graduation-requirement configuration audit](research/graduation-requirement-configuration-audit.md)
found that the requirement engine models *what must be done* well but barely models **eligibility
floors and ceilings**. [ADR 056](056-course-gated-and-emphasis-scoped-requirements.md) deliberately
deferred this cluster — GPA floor, residency / transfer-credit cap, and maximum time-to-degree — to a
follow-up. This ADR resolves it.

Two of the three are real gaps that warrant a small, data-driven addition; the third is already
covered by an existing manual process.

## Decision

### 1. GPA floor — on Program Level, fetched and overridable on Program

A **`min_graduation_gpa`** (Float, 2-dp, `0` = no minimum) lives on **Program Level** (the shared
policy lookup, already Submittable per ADR 015) as the institutional default, and on **Program** as
the operative value. The Program value **defaults from the level but is fully overridable** — pulled
from the level only on create or when `program_level` changes (`Program._hydrate_graduation_gpa_default`),
so an explicit per-program value (including `0`) survives later saves. We do **not** use `fetch_from`
here: it re-pulls on every save and would clobber the override (and a Float can't be null, so
`fetch_if_empty` can't tell "no minimum" from "unset"). Ongoing levels ignore it.

Enforcement is a **graduation-candidacy gate**, not a requirement type: `graduation_candidate._compute`
returns `False` when `current_gpa < min_graduation_gpa` (using the cumulative GPA already maintained by
`gpa.py`), and `api.get_program_audit` mirrors the same check into `graduation_eligible` for the audit
page. It rides the existing recompute hooks (grade send, withdrawal write-back, transcript import all
call `recompute_program_enrollment_gpa` → candidacy), so no new triggers.

### 2. Transfer-credit cap — on Program, enforced at import

A **`max_transfer_credits`** (Int, `0` = no limit) on **Program** caps how many credits a student may
bring in from partner transcripts. It is enforced where transfer credit actually enters the system —
`PartnerTranscriptImportBatch.before_submit` → `_validate_transfer_credit_cap()` — which sums the
student's existing committed transfer credits (`Program Enrollment Course` with `is_transfer = 1`,
`status = 'Pass'`) plus what the batch would add, and blocks submit if the total exceeds the cap.
Enforcing at the single import chokepoint (rather than as a graduation gate) gives the registrar an
error at the moment of over-import, when it is actionable.

### 3. Maximum time-to-degree — already covered; kept manual by design

No new model. `Program.max_time_enrolled` ("Max Years to Graduate") already stamps the Program
Enrollment's max graduation date, and the existing **Time-to-Graduate Risk** report surfaces students
approaching it. This stays a **manual registrar process** (extensions, leaves, and dismissals are
judgement calls, not automatic) — consistent with how the seminary handles the rest of the
time-to-degree lifecycle.

**Requirement expiration** is treated as the *same* category (manual), with one acknowledged
counter-example: **time-bounded external credentials** — a background check / safe-church clearance,
CPR or health clearance, or a language/entrance exam score with a validity window — can legitimately
*expire* if graduation is delayed, unlike a one-off requirement. We deliberately do **not** auto-revert
a Fulfilled requirement on a date (surprising, and rare), leaving it to registrar review for now. If a
real need emerges, it is a small future addition: a validity-period field on the requirement plus a
daily sweep that reverts `Fulfilled → Not Started` past the window — explicitly out of scope here.

## Consequences

- **Easier:** GPA floors and transfer caps become per-program configuration with sane level defaults;
  both default to "off" (`0`), so existing programs are unaffected until a value is set — no data
  migration.
- **GPA gate is silent-by-construction:** a student below the floor simply never becomes a graduation
  candidate; the audit page shows `graduation_eligible = false`. Staff see *why* only via the GPA
  figure already on the audit — we may later add an explicit "below GPA floor" reason string if it
  proves confusing.
- **Transfer cap is best-effort at submit:** it counts committed credits at submit time; an amended or
  re-run batch could in principle double-count against already-committed rows. Acceptable for a
  supervised, one-shot import.
- **Leveling / advanced-standing remains unmodeled** — the audit's fourth gap (requirements that vary
  by a student's *entrance status*) is a distinct modeling problem and is deferred to its own ADR.

## Open questions

- Should the GPA floor also block *filing* a Graduation Request with an explicit message, rather than
  only suppressing candidacy? Deferred until staff feedback.
- Residency (minimum credits earned *in-house*, the complement of the transfer cap) is not modeled;
  the transfer cap covers the common case. Revisit if a program needs an explicit in-residence minimum.
