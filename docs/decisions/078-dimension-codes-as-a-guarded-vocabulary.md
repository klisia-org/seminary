# 078 — Dimension codes are a guarded vocabulary

**Date:** 2026-09-22
**Status:** Accepted 2026-09-22 — implemented 2026-09-22
**Amends:** ADR 065 section 1 (adds the rename guard and `track_changes` to Grading Scale)
**Relates to:** ADR 009 (track_changes convention), aretenic ADR 046 section 7a

## Context

`Grading Scale Dimensions` is a child table, so nothing can Link to a dimension: ten doctypes
across two apps store `dimension_code` as a string and re-stamp a denormalised label. The shape
was never argued — ADR 065 inherited it as a schema-only stub and extended it. It was reopened
before any school runs competency-based education: should a `Competency Dimension` doctype be
linked from both sides instead?

Two of the three reasons to move dissolved on inspection. Performance is a wash, since Frappe
stores a child table as its own SQL table. Change tracking was a missing `track_changes` flag on
an ERPNext Education inheritance, not a missing doctype. The third is real but points elsewhere:
Frappe does not cascade an edit to a `Data` field, so renaming a code silently detaches every
descriptor, weight and grade, and the verdict pipeline then reports a competency as ungraded
rather than failing.

## Decision

1. **The child table and the stable code stand.** Nothing Links to a dimension, which is ADR 065
   section 2's own test for standalone versus child. The code is also the join key *across*
   scales, and aretenic requires frozen snapshot rows keep the code they were cut with — so a
   rename cascade would corrupt the very audit records a Link was supposed to protect.

2. **A code may not be renamed or removed while records store it.**
   `grading_scale.py::protect_dimension_codes` compares against `get_doc_before_save` and refuses
   any lost code that `dimension_code_usage` still finds under this scale. Scoped to the scale,
   since two scales may legitimately both define `knowledge`. The label stays freely editable and
   propagates on the next save of each storing record; only the key is frozen.

3. **One validator, four callers.** `cbe.scale_dimensions`, `assert_known_dimension` and
   `assert_unique_dimension` replace four drifted copies. `scale_dimensions` is deliberately
   uncached, unlike its neighbours: its callers use the label to re-stamp their denormalised
   field, so it must read the scale as of this save. Covered by
   `seminary.seminary.tests.test_dimension_vocabulary`.

4. **`track_changes: 1` on Grading Scale**, per ADR 009 — no flag on the child table.

## Rejected: a `Competency Dimension` doctype linked from both sides

It has real merit: referential integrity and a rename cascade come free, and the four validators
would share one vocabulary by construction. Rejected because nothing Links to a dimension, because
a cascade is the wrong behaviour for frozen evidence, and because aretenic ADR 029 already tried a
separate dimension axis and dropped it as duplicative. The cost also told against it — ten
doctypes, a course-pack format change and a migration, against one flag, one guard and three
helpers for the same outcomes.

## Consequences

Renaming a code in use is now a validation error that names what would break and the way round it:
add the replacement dimension alongside, move the records over, then remove the old row. Amending
a submitted scale can still strand records, because the guard runs on `get_doc_before_save` and an
amendment is a new document; that is pre-existing amendment semantics, not something this ADR
changes. Aretenic is deliberately not consulted by the guard — its snapshot rows are frozen
evidence that must not block a vocabulary edit, and a dimension-qualified KPI matching no current
dimension is already specified to be inert and visible.
