# 072 — Descriptive scale grading

**Date:** 2026-09-21
**Status:** Accepted

## Context

`Grading Scale.grscale_type` offers three values. Two of them compute.

[ADR 065](065-competency-based-education.md) gave `Competency-based education` its own calculation
path, and its Consequences section named the Points-only guards in `grade_thisstudent`,
`fgrade_this_std` and `scheduled_course_roster.validate_score` as "the enforcement points" for the
new level-vs-percent split. It left `Descriptive` exactly where it found it: with no calculation
path at all.

Concretely — in [`api._grade_thisstudent`](../../seminary/seminary/api.py) the Points branch
returns, the CBE branch returns, and a Descriptive scale falls off the end of the function having
written nothing, so `Course Assess Results Detail.grade` and `.score` stay empty. In
`api._fgrade_this_std` a Descriptive scale reaches only the Fail-for-Absence tail, so `fscore`,
`fgrade` and `fgradepass` are never written. Both `fscore` and `fgrade` are `read_only` on
[Scheduled Course Roster](../../seminary/seminary/doctype/scheduled_course_roster/scheduled_course_roster.json),
so there is no manual escape hatch either: **a Descriptive section cannot produce a final grade by
any route.**

Two things follow downstream. `send_grades` copies the blank roster fields into the Program
Enrollment Course; because a blank `fgradepass` is not `"Fail"`, the `credits = 0` guard is skipped
and credits are awarded against an empty grade. And
[`gpa._convert_to_gpa_points`](../../seminary/seminary/gpa.py) *does* carry a working Descriptive
branch — it simply keys on `pec_finalgradecode`, which for a Descriptive scale is only ever
populated by
[the transfer importer](../../seminary/seminary/doctype/partner_transcript_import_batch/partner_transcript_import_batch.py).
Descriptive therefore works end to end for imported transfer credit and not at all for a section
the school teaches.

The trap that shapes the decision is units. For a Points scale an interval `threshold` is a
percentage, and `validate` refuses a scale with no threshold of 0. For a Descriptive scale it is
the grade-point value — Distinction = 4.0 — stated in the
[field's own description](../../seminary/seminary/doctype/grading_scale_interval/grading_scale_interval.json)
and relied on by `gpa._points_from_code`. Copying the Points arithmetic would build a 0–100 number
and resolve it against 0–4 thresholds, landing every student in the top band. That is the same
percent-vs-level confusion ADR 065 warns about, in a third place.

## Decision

A Descriptive section is graded **per assessment, weighted** — the same shape as Points, carried
out in threshold units instead of percent.

1. **The cell holds the level, as it already does for CBE.** `rawscore_card` carries the
   `threshold` of the interval the evaluator chose; no new field. `_grade_thisstudent` sets
   `row.grade = get_grade(scale, rawscore_card)` and `row.score = rawscore_card` — *not* a weighted
   contribution, because the weighting in step 2 needs a denominator that is only known once the
   whole roster row is in hand.

2. **The final is a weighted mean, not a weighted sum.** Over graded cells:

   ```
   fscore = Σ(rawscore_card × maximum_score) / Σ(maximum_score)
   ```

   `maximum_score` is the assessment's weight, fetched from `Scheduled Course Assess
   Criteria.weight_scac`. Dividing by the weights actually present renormalizes a section whose
   weights do not total 100, and keeps the result in threshold units so `get_grade` and
   `get_gradepass` resolve it against the right bands. `fgrade` and `fgradepass` follow from
   `fscore`; the Fail-for-Absence override applies last, as in the other two branches.

3. **Ungraded cells are skipped, not counted as zero.** The Points path can treat a missing score
   as 0 because it sums; a mean has a denominator, so an ungraded assessment must leave both sides
   of it. This matches `cbe.aggregate`, which already filters `None`.

4. **Extra credit does not apply.** `extracredit_card` rows are ignored on a Descriptive section.
   Adding points to a narrative band has no coherent meaning, and the CBE branch already ignores
   them.

5. **`validate_score` gains a Descriptive arm.** The value in `rawscore_card` must equal one of the
   scale's thresholds. Without it, a typo resolves silently into a lower band instead of erroring.

6. **`send_grades` refuses a blank `fgradepass`.** This one is independent of scale type: a roster
   that produced no grade must not award credits. It is the guard that would have made this gap
   loud instead of silent, and it belongs in regardless of the rest.

## Consequences

Descriptive becomes a scale the school can actually teach on, and the GPA path it already has stops
being reachable only through transfer credit. The three enforcement points ADR 065 named now branch
on all three scale types, so the next scale type added fails loudly rather than falling through.

What this makes harder, and what stays open:

- `fscore` now holds a threshold-unit number (3.4) on a Descriptive section, as it already holds a
  level on a CBE section. Any surface rendering `fscore` as a percentage is wrong for two of the
  three scale types; the transcript and gradebook renders need auditing, and that audit is not
  scoped here.
- Evaluators type a number (4.0) rather than picking a code ("Distinction"). This is what CBE
  evaluators already do, so it is consistent rather than good. If it proves unusable the follow-up
  is a `gradecode_card` Select on Course Assess Results Detail, which is purely additive — the
  threshold stays the stored value.
- Any Descriptive section already on a live site has blank cells and a blank roster grade today.
  Those must be audited before item 6 starts refusing to send them, and audited on a
  production-shaped site rather than a dev one.
- The transfer path is untouched: `Grade Conversion Policy` and the importer keep writing
  `pec_finalgradecode` directly, and [ADR 006](006-grade-conversion-policy.md)'s ban on linear
  methods for narrative sources is unaffected.
