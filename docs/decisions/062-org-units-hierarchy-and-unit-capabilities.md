# 062 — Org-unit hierarchy & person-keyed unit capabilities

**Date:** 2026-06-24
**Status:** Implemented 2026-06-24 (Seminary foundation; consumed by aretenic ADR 028)

## Context

Seminary is the people/org spine the rest of the EOMS hangs on (Academic Unit, Academic Unit
Membership, Faculty Capability, Person). Documenting organizational relationships for the whole EOMS —
e.g. *who oversees a unit's training?* — exposed three gaps in that spine:

1. **No org hierarchy among units.** The only unit-to-unit relationship is an Academic
   Interdepartment's `member_units` ([ADR 059](059-seminary-departments-and-faculty-capabilities.md)),
   which means *academic co-ownership* (faculty eligibility is unioned transitively from constituents,
   one level). There is no "this department rolls up under this school" hierarchy for oversight.
2. **Capability routing is instructor-keyed.** `faculty._capability_rows` joined on
   `m.instructor IS NOT NULL`, so only people with an Instructor record could hold a routed capability.
   An administrative overseer (often a non-instructor) had no way to hold one.
3. **No notion of who oversees a unit's people** — the consumer need (aretenic team training oversight,
   ADR 028) had nothing to build on.

A hard constraint frames the solution: **`aretenic` requires `seminary`; `seminary` must never
reference `aretenic`.** So the mechanism lands here, generic; consumers build on top.

## Decision

### 1. Person-keyed unit capabilities (one engine)

The capability engine ([faculty.py](../../seminary/seminary/faculty.py)) now resolves on **`m.person`**
(always present); `m.instructor` becomes optional metadata. A new **`Faculty Capability.requires_instructor`**
(Check, default 1) decides whether a capability needs a faculty record:

- **Academic capabilities** keep `requires_instructor=1`. All instructor-keyed helpers
  (`eligible_instructors`, `claim_capability`, `claim_for`, `release_capability`, `wired_instructors`,
  the link pickers, roster, worklists) read the **instructor-bearing subset** via the new
  `_instructor_rows` — behaviour is identical to the pre-062 instructor-only core.
- **Organizational capacities** (`requires_instructor=0`, e.g. **"Oversees Unit Training"**,
  Committee/Board Member) may be held by a plain Person. New person-keyed helpers serve them:
  `persons_with_capacity(unit, route)`, `units_with_capacity(person, route)`,
  `holds_unit_capacity(person, route, unit=None)`, `require_unit_capacity(person, route, unit)`.

Membership validation (`academic_unit_membership._validate_instructor_for_capabilities`) now requires an
Instructor only when the capability's `requires_instructor` is set — replacing the hardcoded
`Committee/Board Member` exemption. Seeds carry the flag; a backfill patch
(`set_faculty_capability_requires_instructor`, modeled on `set_faculty_capability_capacity_flag`) sets it
1 everywhere then clears it for the organizational routes.

The `Faculty Capability` doctype keeps its name (rename blast radius is large) but its description now
reads "unit capability"; the routing engine was always generic by `routes_to` machine key.

### 2. Academic Unit `parent_unit` hierarchy

Academic Unit gains an optional **`parent_unit`** (Link → Academic Unit) — a true org tree, **distinct
from** Interdepartment `member_units`. A cycle guard (`_validate_parent_unit`) walks the ancestor chain
and rejects self/loops. Two cycle-safe module helpers expose the tree:
`descendant_units(unit)` (self + all descendants, for oversight roll-down) and `ancestor_units(unit)`.
`faculty._resolve_units` (Interdepartment, one level) is **unchanged** — academic eligibility and org
rollup are deliberately separate relationships. `unit_type` also gains "Administrative Office" / "Task
Force" so non-academic and fluid cross-cutting units fit the spine.

### 3. No `reports_to` on Person

Oversight derives from **unit capacity + parent_unit hierarchy**, not a person-to-person line on Person.
This is rule-based and auditable, and avoids duplicating HRMS `Employee.reports_to` (which consumers may
optionally derive from via the Via-User bridge when HRMS is enabled). Person stays a flat identity spine.

## Consequences

- One capability engine serves both academic (instructor-bearing) and organizational (person-only)
  functions; academic routing is provably unchanged because those capabilities stay
  `requires_instructor=1`.
- Org oversight has a generic, person-keyed foundation; aretenic (ADR 028) and any future consumer build
  on `units_with_capacity` + `descendant_units` without seminary depending on them.
- Cost: the capability doctype name ("Faculty Capability") now under-describes its scope; mitigated by
  the updated description and machine-key routing. A future rename is possible but deferred.
