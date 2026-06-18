# 059 — Academic Unit & Faculty Capabilities

**Date:** 2026-06-18
**Status:** Implemented 2026-06-18 (Stages 0–4: foundation; internship pool; verification/placement routing with [ADR 060](060-leveling-placement-assessment-separation.md); CP rework; portal worklist + roster button + audit report)

## Context

The seminary has no way to answer **"who does this academic work?"** at scale. Advising theses and
internships, verifying Manual-Verification requirements, grading placement exams, mentoring groups —
each is wired to its **own ad-hoc instructor list**, maintained independently:

| Subsystem | How faculty are pooled today |
|---|---|
| Internships (ADR 054) | `Internship Type Advisor Slot` child — round-robin pool w/ `max_students`/`current_students`, `claim_advisor_slot()` |
| Course sections | `Course Schedule Instructors` child (instructor + `Instructor Category` role) |
| Culminating Projects (ADR 025/027) | free `advisor` / `second_reader` / `third_reader` links + `committee` child |
| Mentoring | `Student Group.mentor` (single free link) |
| Manual-Verification / placement-exam verification (ADR 058) | **nothing** — no pool, no worklist |

That's five places to keep in sync, and the highest-value one (verification) doesn't exist. The
internship advisor-slot pool (capacity + round-robin) pointed the right way, but per-subsystem pools
don't scale.

There is also **no department concept**. `Program.department`, `Course.department`, and
`Instructor.department` are stubs pointing at ERPNext's HR `Department` — `Program.department` is even
annotated *"hidden until a definition of Academic Departments is made."* The org spine to hang
faculty, courses, and routing on is simply missing.

This ADR establishes that spine. It deliberately does **not** cover the leveling/graduation cleanup —
that is [ADR 060](060-leveling-placement-assessment-separation.md), which reuses the faculty-capability
routing defined here.

**Guiding constraint (the user's, throughout): single source of truth — never make staff sync the
same fact in two places.**

## Decision

### 1. A typed `Academic Unit`

Not "Academic Department" — a general **typed org unit**, because seminaries route work through more
than teaching departments. New Setup catalog (not submittable; `is_active` retires, like the GRI
library; seeded via the install hook, never fixtures — fixtures clobber desk edits):

- `unit_name` (Data, unique), `unit_code` (Data, e.g. `ST`), `description`,
  `publish_on_web` (Check), `is_active` (Check), `chair` (Link → Instructor — **descriptive only**;
  all gating stays role-based per [ADR 034](034-role-taxonomy.md)).
- `unit_type` (Select, extensible): **Academic Department** · **Academic Interdepartment** · **Program Committee** · **Board** ·
  **Other Committee**. The type declares what the unit *owns/does*:
  - **Academic Department** owns **courses** — rename + unhide `Course.department` → **`Course.academic_unit`**
    (Link → Academic Unit). `unit_code` is the **source** of the course prefix (`ST 501`), *derived*,
    never a second stored copy to keep in sync.
  - **Academic Interdepartment** — a neutral home for a *genuinely co-owned* course (e.g. Pastoral
    Ministries and Theological Studies truly co-own it), so `Course.academic_unit` stays a **single
    Link**. It carries its own `unit_code` (the joint-course prefix) and a **self-referencing member-units
    table** (rows linking to its constituent Academic Departments). Faculty eligibility is **not copied
    in** — `eligible_instructors()` resolves it **transitively at query time**, unioning the member units'
    memberships (single source of truth; see §2/§4). A materialize button is at most an optional
    convenience, never the source. This is how cross-listing is handled (see §6).
  - **Program Committee** owns **programs** — `Program.department` → **`Program.academic_unit`** (Link →
    Academic Unit), *optional*. Degree programs (MDiv) span academic departments, so academic ownership
    flows through **courses**, not the program (the user's "option 2").
  - **Board / Other Committee** — governance/faculty groupings (future report automation, web roster).

`Instructor.department` (HR, fetched from Employee) is **left alone** — it is an org-chart/payroll
concept, orthogonal to academic-work routing. Academic binding lives in membership (below), not on the
HR field (the orthogonal-flags principle — don't overload one field with two meanings).

### 2. Faculty wiring: `Academic Unit Membership` + capabilities

An instructor's participation is a **standalone `Academic Unit Membership` doctype**, *not* a child row
of the unit — because each membership needs its own *list* of duties, and [ADR 056](056-course-gated-and-emphasis-scoped-requirements.md)
established that Frappe forbids table fields on a child doctype (no grandchildren). A standalone
doctype can own a child table.

- **`Academic Unit Membership`**: `unit` (Link), `person` (Link → **Person**, the required key — the
  canonical human-on-record that `Instructor`/`Student`/`Alumni Profile`/`Partner Contact` already link
  to), `instructor` (Link, **derived & read-only** — auto-resolved from the person's Instructor record
  via the existing `Instructor.person` link, never typed in; hidden until present, with a *Faculty /
  Non-instructor* badge on the form), `is_active` (Check), `capabilities` (child). Unique
  (`unit`, `person`). A board member is simply a `Person` with **no** Instructor role; an adjunct who does
  none of this opts out by having no active membership / no capabilities.
- **`Academic Unit Capability`** (child): `capability` (Link → `Faculty Capability`), `max_students`
  (Int, 0 = unlimited), `current_students` (Int, read-only) — the exact
  `(instructor, capability, capacity)` tuple the internship slot already proves, generalized.
  `max_students`/`current_students` are meaningful only for capacity-bearing (instructor) capabilities.
- **Validation:** academic-routing capabilities (Course Instructor, Thesis/CP Advisor, Internship
  Advisor, Placement Examiner, Manual-Verification Verifier) require the linked `person` to have an
  Instructor record; only **Committee/Board Member** is valid for a person without one.

### 3. `Faculty Capability` catalog — a *new* list, not `Instructor Category`

`Instructor Category` (Instructor of Record / GTA / Grader) is a **pay- and accreditation-bearing
teaching role** wired to Course Schedule. Overloading it with advising/verification duties would
conflate compensation roles with committee work and pollute the section instructor picker. So a
separate small Setup catalog, seeded via the install hook:

- `Faculty Capability`: `capability_name` (Data, unique), `is_active`, `routes_to` (Select — a
  stable machine key so routing code filters by *meaning*, not free-text): **Course Instructor ·
  Thesis/CP Advisor · Internship Advisor · Placement Examiner · Manual-Verification Verifier · Mentor
  · Committee/Board Member**, and `tracks_capacity` (Check) — on for the capacity-aware routes
  (advising/examining/verifying), off for Course Instructor / Mentor / Board. The capability child
  fetches this flag and shows `max_students`/`current_students` only when it is set (cleaner UX —
  capacity fields don't clutter capabilities that have no cap).

### 4. One generic claim/release, replacing the five pools

A single `seminary/seminary/faculty.py` generalizes the internship
`internship_type.claim_advisor_slot()` (most-remaining-capacity round-robin):

- `eligible_instructors(unit, route)` — active memberships wired to that route, capacity-aware. For an
  **Academic Interdepartment** unit it unions the member units' memberships transitively (no copy).
- `claim_capability(unit, route)` / `release_capability(...)` — pick + increment / decrement
  `current_students`.

**Manual entry always wins** (the existing internship rule: auto-assign only when the human field is
blank; releasing the prior auto-count on change). Migration order, lowest-risk first:
1. **Internship advisors** — near-mechanical swap of the data source from `Internship Type Advisor
   Slot` to unit capabilities (keep `auto_assign_faculty`; add which unit's pool to draw).
2. **Manual-Verification verifiers & Placement examiners** — *new* routing (no pool exists today), so
   pure addition; this is the big win.
3. **CP advisor** — becomes unit-routed but *not* round-robin: the student-declared department assigns
   it deliberately from a picker fed by `eligible_instructors(academic_unit, "Thesis/CP Advisor")`, and
   the assignment **claims/releases capability** so a professor's thesis-load cap (`max_students`) is
   honoured (a real constraint, unlike a free link). See §7 for the full CP rework.
4. **Student-Group mentor** — stays a free link (single-mentor semantics don't fit a pool); optionally a
   unit-filtered `set_query` "suggest from unit" picker. Deprecate `Internship Type Advisor Slot` over a
   release, then migrate its rows with a patch (don't delete same-release).

### 5. Portal routing — extend the pattern that already works

`utils.get_courses` already does "Program Chair / Seminary Manager / System Manager see all; a plain
Instructor sees only their own sections." Generalize it:

- `FACULTY_FULL_ACCESS_ROLES` (Program Chair, Seminary Manager, System Manager — mirroring the existing
  `COURSE_FULL_ACCESS_ROLES` in `utils.py`) → see every unit's worklist; a plain instructor resolves
  Instructor → active memberships → capabilities and sees only matching work in their unit(s).
- `get_my_faculty_worklist(route=None)` returns the open items (pending verifications, advising to
  claim, placement exams to grade) for the caller; extend `api.get_user_info` with
  `faculty_units` + `faculty_capabilities` so the portal shows/hides "My Advising",
  "Verifications", "Placement Exams" tabs exactly as `is_instructor`/`is_evaluator` gate views today.
- A single query backs the verification queue (*work in a unit I'm wired to with that
  capability*) — no per-subsystem pool to maintain. `publish_on_web` enables future public unit
  / faculty-roster pages.
- **External examiners do *not* get `is_instructor`.** The CP portal gates on `is_instructor`; an
  external examiner is a separate, reduced-access record (see §7) surfaced via its own
  `get_user_info` flag (e.g. `is_external_examiner`) and role, so it can use the CP screens without
  inheriting instructor access/worklists.
- **"See Member Roster" (read-only).** On the Academic Unit form, a button runs the same transitive
  `eligible_instructors`/membership query and *displays* the roster (including member-unit faculty for
  Interdepartment units) — it **adds no rows**, so there is no copy to drift. (This replaces the earlier
  "sync/materialize" idea entirely.)
- **Audit report (group-by unit).** A standalone report lets a Seminary Manager double-check wiring —
  memberships, capabilities, and capacity grouped by Academic Unit — surfacing units with no chair, an
  instructor with no capability, capabilities over capacity, etc.

### 6. Course code & cross-listing — one home, no duplication

A course always has **exactly one home** via the single `Course.academic_unit` Link, and its prefix is
*derived* from that unit's `unit_code` — never a second stored copy, never a duplicate course record or
alias. Genuine co-ownership is the only cross-listing case at this seminary, so it is modelled by an
**Academic Interdepartment** unit (§1): the joint course is homed there, gets the interdepartmental
prefix, and draws faculty transitively from the constituent departments. The additive Table-MultiSelect
cross-listing tag is **dropped** — the Interdepartment unit subsumes it, keeping `Course.academic_unit`
a single source.

### 7. Which unit owns a work item — the routing map

So no relationship is missed, every routable work item names how its owning unit is resolved. **Program
Chair (a `FACULTY_FULL_ACCESS_ROLES` member) overrides every row.**

| Work item | Owning unit resolved by | Notes |
|---|---|---|
| Course teaching | the **Course Schedule** (CS Instructors stay the source of truth) | unit is a non-blocking filter convenience on the CS picker |
| Internship advising | the **Internship Type's** unit | optional explicit unit field; backing-course OR unit required (form toggle) |
| Manual-Verification / Placement exam | the **requirement's / placement assessment's** unit | *new* routing — the big win; pairs with [ADR 060](060-leveling-placement-assessment-separation.md) |
| Thesis / CP advising | the **student-declared `academic_unit`** (an Academic Department) on the project | dept assigns the advisor, capacity-aware (§7.1) — *not* the program committee |
| CP readers | the CP's `academic_unit`, scoped by **CP Type** | count + scope (Same unit / Any unit / External) declared on the type (§7.1) |
| Mentoring | free link (`Student Group.mentor`) | no routing |
| Governance / board service | a **Board / Other Committee** unit | roster only (no capacity); `publish_on_web` for web roster |

Any item whose owning unit is still ambiguous after this map stays a **follow-up**, not a silent gap.

### 7.1 Culminating Project rework — close the advisor short-circuit

Today `Culminating Project.advisor` is `reqd:1` (Link → Instructor), which short-circuits the real
process: the student is forced to name an advisor before the department has decided one. The fix routes
CP work through the unit spine:

- **Student declares the unit, not the advisor.** Add `academic_unit` (Link → Academic Unit, filtered to
  *Academic Department* type) to Culminating Project — **student-declared, required**. Drop `reqd:1` from
  `advisor`. This is the routing owner.
- **No new workflow state.** The student's only action is *save* (no separate submit), so the existing
  **Draft** already means "saved by the student, awaiting advisor" and sits in the department's pipeline
  as-is — optionally **rename Draft → `Pending Advisor`** for clarity. The department assigns the advisor
  from a picker fed by `eligible_instructors(academic_unit, "Thesis/CP Advisor")`; assigning **claims**
  the advisor's capability (honours `max_students`) and moves the project Draft → Active, **the existing
  transition now gated on advisor presence**. Reassigning **releases** the prior advisor's slot. The
  advisor is required to *leave* Draft, never to create it.
- **Reader count + scope are declared on `Culminating Project Type`**: add `readers_required` (Int) and
  `reader_scope` (Select: *Same Academic Unit* / *Any Academic Unit* / *External Allowed*). Reader pickers
  scope by `reader_scope` against the project's `academic_unit`. This is **orthogonal** to the existing
  per-milestone sign-off flags (`signoff_advisor` / `signoff_second_reader` / …): those gate *each
  milestone transition* (which sign-offs are required to advance), not the roster size — e.g. all three
  readers may give feedback throughout, yet a seminary may require only the advisor's sign-off on every
  milestone except the defense-ready one. That gating logic stays where it is (frontend, per-milestone);
  the type just declares how many readers and from where. The two never duplicate each other.
- **External readers → a new, reduced-access `External Examiner` doctype** (Decision Q1), linked to
  `Person`, holding credentials/vetting and institutional memory ("invited before / invite again") so it
  doesn't live in someone's head. It is deliberately **not** an Instructor: the CP portal gates on
  `is_instructor`, so an examiner gets a separate reduced-access role/flag (§5) — and the Employee/HRMS
  link being only a soft requirement was never the blocker; the portal permission was. This **replaces**
  the committee child's free-text externals (`is_external` / `external_name` / `email_external` /
  Link→Contact) with a `Link → External Examiner`. **Externals may occupy the named reader slots**
  (`second_reader` / `third_reader`) — those become a **Dynamic Link** (Instructor *or* External
  Examiner); if that proves awkward, the fallback is to move readers into a child table. A *new*
  `unit_type` for external readers was **rejected** — a unit is an org owner, not a sourcing bucket.

## Consequences

- **Easier:** faculty are wired in *one* place; "who can do X" is one capability query; the verification
  worklist finally exists and scales; the long-stubbed department fields get a real home; Program
  Chair oversight reuses the proven full-access pattern.
- **New surface:** `Academic Unit` (with a self-referencing member-units child table), `Academic Unit
  Membership` (person-keyed), `Academic Unit Capability` (child) + a `Faculty Capability` catalog +
  `faculty.py`; plus the CP rework (§7.1) — an `External Examiner` doctype, `Culminating Project.academic_unit`
  (and `advisor` losing `reqd:1`; existing Draft state reused/renamed, no new state), and
  `readers_required` / `reader_scope` on Culminating Project Type; a read-only roster button and a
  group-by-unit audit report (§5). The five subsystems migrate incrementally (internships first), not in
  a big bang.
- **Migration:** **rename** `Course.department` → `Course.academic_unit` and `Program.department` →
  `Program.academic_unit` (patch renames the column and updates fetches / `set_query` / reports),
  repoint the Link options to Academic Unit, and null stale HR values; move internship advisor-slot rows
  into unit capabilities (later patch). The field rename is the added cost of leaning neutral, paid once.
  Seed capabilities + starter units via the install hook (never fixtures — they clobber desk edits). Any
  new worklist surfaced on a workspace must be added via Desk, not JSON (memory).

## Resolved (this round)

- **One type per unit** — many-to-many membership carries the rest. (Decision §1.)
- **Course Instructor routing is advisory** — Course Schedule Instructors stay the source of truth for a
  CS; the unit is only a non-blocking filter, since deans/others routinely step in to fill. (§7.)
- **Cross-listing → Interdepartment only** — the additive tag is dropped; an interdepartmental course is
  homed in an Academic Interdepartment unit and takes that unit's `unit_code` as its prefix. (§1, §6.)
- **Internship pool default** — an *optional explicit* unit field; backing-course OR unit is required (a
  form toggle makes the choice explicit). (§7.)
- **Non-instructor members** — membership keys on `Person`; `instructor` optional; board members are
  Persons with no Instructor role. (§2.)
- **CP advisor short-circuit** — student declares `academic_unit` and saves (Draft); the department
  assigns the advisor (capacity-aware) to move Draft → Active; advisor loses `reqd:1`. **No new state** —
  Draft is reused (optionally renamed *Pending Advisor*), since the student's only action is save. (§7.1.)
- **CP external readers in named slots** — externals may fill `second_reader`/`third_reader` via a
  Dynamic Link (Instructor *or* External Examiner); fallback is moving readers to a child table. (§7.1.)
- **CP reader count/scope** — declared on Culminating Project Type (`readers_required` + `reader_scope`);
  **orthogonal** to the per-milestone sign-off flags, which keep gating each milestone transition. (§7.1.)
- **External readers** — a new reduced-access `External Examiner` doctype (Person-backed, vetting +
  institutional memory), **not** an Instructor and **not** a `unit_type`; replaces the committee
  free-text externals. (§7.1, Q1.)
- **Roster materialization** — settled as a *read-only* "See Member Roster" button (same transitive
  query, no rows) plus a group-by-unit audit report; no copy is ever stored. (§5.)

## Open questions

- **Per-work-item ownership** — the §7 map covers the known routable items; revisit it as graduation
  requirements / placement assessments firm up in [ADR 060](060-leveling-placement-assessment-separation.md),
  and treat any still-ambiguous item as an explicit follow-up rather than a silent gap.
