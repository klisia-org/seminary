# Graduation Requirement Configuration — Audit & Gap Analysis

> **Status: Research input, not a decision.** This note catalogs how real seminary program
> requirements map onto the current engine, and sketches candidate directions for the gaps it
> finds. Gap A and Gap B below were **decided in [ADR 056](../056-course-gated-and-emphasis-scoped-requirements.md)**
> (Course Passed activation mode + emphasis scope on requirement rows). The eligibility-floor cluster
> (GPA floor, transfer-credit cap, time-to-degree) is **decided in [ADR 057](../057-graduation-eligibility-floors.md)**.
> Still open: **leveling / advanced-standing** (its own future ADR 058) and an explicit **residency
> minimum**. Nothing here is committed design except where ADR 056 / 057 adopt it. Cross-references: ADR 002 (emphasis & track credits), 012 (graduation requirements
> architecture), 024 (culminating projects & policy versioning), 025 (CP milestones / DateRuleResolver),
> 026 (requirement choices), 035 (deferred required-course enrollment), 054 (internships).
>
> _Last verified against code: 2026-06-17._

## Why this note exists

While configuring real school programs, two requirement shapes appeared that the engine could not
express, and a recent review of the flow missed both:

1. **Course-gated requirements** — "to *start* your thesis you must first *pass* the *Writing a
   Thesis* course."
2. **Emphasis-specific requirements** — "MDiv students with a Counseling emphasis must complete a
   counseling internship."

Both are real needs. But investigating them overturned the assumptions behind them, which changes
what the eventual ADR is actually solving.

### Two premises were wrong (this reframes everything below)

**Premise 1 — "I can't gate a requirement on a course because that needs a child-table-of-a-child-table."**
False. A child-table-of-a-child-table (a *grandchild grid*) is indeed forbidden by Frappe, but the
escape hatch — **`Table MultiSelect`** — is already in production on exactly this doctype.
`Program Grad Req Items` (PGRI) is `istable: 1`, and it already carries a `Table MultiSelect` field:

```jsonc
// seminary/seminary/doctype/program_grad_req_items/program_grad_req_items.json
{
  "fieldname": "prerequisite_requirement",
  "fieldtype": "Table MultiSelect",
  "options": "Program Grad Req Items"   // → child doctype "Grad Req Item Prerequisite", also istable:1
}
```

A `Table MultiSelect` stores a flat list of links in a child doctype hung off the parent child row —
which Frappe allows. So gating a requirement on a list of *courses* is **structurally identical** to
the prerequisite mechanism that already ships. The gap is a missing **activation mode + evaluation
logic**, not a schema impossibility.

**Premise 2 — "We have no track/emphasis concept."**
False. A full emphasis subsystem exists (ADR 002): `Program Track` (`is_emphasis`, `is_fallback`,
`emphasis_declaration`, `advisory_only`, credit floor/ceiling), `Program Enrollment Emphasis`
(student declarations with `status` Active/Completed/Dropped), `Program Track Courses`
(`pgm_track_course_mandatory`), plus `Program.allow_multiple_emphases` / `emphasis_overlap_policy` /
`fallback_emphasis`. Emphasis-mandatory courses are already enforced for graduation candidacy in
`_mandatory_emphasis_courses()` ([graduation_candidate.py:194-229](../../../seminary/seminary/graduation_candidate.py#L194-L229)).

The catch: emphases differentiate **only courses and credit pools**. There is **no link from a
graduation-requirement row (PGRI) to an emphasis**, so any emphasis-specific *non-course* requirement
(internship, project, manual verification, event) cannot be expressed.

**Net reframing:** Gap A is "the requirement engine has no notion of *course identity*"; Gap B is
"the requirement engine has no notion of *sub-program (emphasis)*." Both are dimensions the engine
simply lacks — see the cross-cutting note at the end.

---

## 1. Current architecture (recap)

**Three-layer model** (ADR 012):

| Layer | DocType | Role |
|---|---|---|
| Library | `Graduation Requirement Item` (GRI) | Reusable requirement definitions (the catalog) |
| Policy | `Program Graduation Requirement` (PGR) + `Program Grad Req Items` (PGRI) | Per-program binding; versioned `Draft → Active → Superseded` (ADR 024) |
| Instance | `Student Graduation Requirement` (SGR) | Snapshot **frozen at enrollment** — the catalog-year contract; a later policy edit never retroactively fails an enrolled student |

**Five requirement types** (on GRI): Event Attendance, Chapel Attendance, Manual Verification,
Linked Document, Choose Option (ADR 026).

**Five activation modes** (on PGRI,
[program_grad_req_items.json:67-73](../../../seminary/seminary/doctype/program_grad_req_items/program_grad_req_items.json#L67-L73)),
evaluated at audit time by `evaluate_activation()` in
[graduation.py](../../../seminary/seminary/graduation.py):

| Mode | Activates when… |
|---|---|
| Always Active | always |
| After Requirement | all listed PGRI prerequisites reach Fulfilled/Waived (`prerequisite_requirement` Table MultiSelect) |
| Credits Passed | `Program Enrollment.totalcredits` ≥ a threshold (**total** credits, not specific courses) |
| On Document Status | a linked document reaches a configured status |
| Time Offset | a date computed from an anchor (Expected Graduation / Last Term Starts / Program Starts) ± offset |

**Candidacy gate** ([graduation_candidate.py:100-140](../../../seminary/seminary/graduation_candidate.py#L100-L140)):
a student becomes a graduation candidate when mandatory program courses **and** mandatory emphasis
courses are satisfied, credits-required is met (for Credits-based programs), and no mandatory
`blocks_graduation_request` SGR row is still open. The trigger (`Enrolled in final courses` vs
`Passed final courses`) is per-program.

---

## 2. Configuration matrix — common seminary requirements vs. the engine

Legend: ✅ Supported · 🟡 Partial / workaround only · ❌ Not modeled.

| Configuration | Status | Mechanism / what's missing |
|---|---|---|
| Total credit hours | ✅ | `Program.credits_complete`; checked in candidacy |
| Distribution / category credit pools (e.g. "6 hrs Greek, choose from 8 courses") | ✅ | Non-emphasis `Program Track` credit organizers (`addcredits`/`max_credits`) |
| Specific required courses | ✅ | Program Course `required`; `pgm_track_course_mandatory` |
| Declarable emphasis/concentration (course & credit effects) | ✅ | `Program Track.is_emphasis` + emphasis-mandatory courses (ADR 002) |
| **Emphasis-specific NON-course requirement (internship/project/verification)** | ❌ | **Gap B** — PGRI has no emphasis dimension; emphases affect only courses |
| **Requirement gated on passing a specific course** ("pass *Writing a Thesis* before thesis") | ❌ | **Gap A** — no "Course Passed" activation mode; `Credits Passed` is a total, not course-specific |
| Thesis / capstone / culminating project | ✅ | Linked Document → Culminating Project (ADR 024/025) |
| Choose-one-of (thesis vs. summative paper; internship vs. elder's letter) | ✅ | Choose Option umbrella + project-type allow-list (ADR 026) |
| Internship / field education / practicum + hours | ✅ | ADR 054 |
| Chapel / spiritual-formation attendance (count-based, self check-in) | ✅ | Chapel Attendance type |
| One-off event attendance (retreat, conference, symposium) | ✅ | Event Attendance type |
| Quantity-based (N service hours, N sermons preached) | ✅ | Manual Verification `quantity_required` |
| Reference / ordination / ecclesiastical endorsement letters | ✅ | Recommendation Letter (Linked Document) |
| Requirement due before a date / after another requirement | ✅ | Time Offset / After Requirement |
| **GPA-floor graduation gate** ("graduate only with cumulative GPA ≥ X") | ✅ | **ADR 057**: `min_graduation_gpa` on Program Level → Program (overridable); candidacy gate in [graduation_candidate.py](../../../seminary/seminary/graduation_candidate.py) + audit display |
| Comprehensive / qualifying / language-proficiency exams | 🟡 | No exam entity; expressible only as Manual Verification or a backing course |
| Transfer-credit cap (max credits brought in) | ✅ | **ADR 057**: `Program.max_transfer_credits`, enforced at Partner Transcript Import Batch submit |
| Residency minimum (min credits earned *in-house*) | ❌ | Not modeled — the complement of the transfer cap; deferred (ADR 057 open question) |
| Maximum time-to-degree | ✅ | `Program.max_time_enrolled` + **Time-to-Graduate Risk** report; manual registrar process by design (ADR 057) |
| Requirement expiration (time-bounded credentials) | 🟡 | Treated as manual like time-to-degree (ADR 057); auto-expiry of a Fulfilled row deferred |
| Leveling / advanced-standing requirements that vary by entrance status | ✅ | **ADR 058** (implemented): per-student Leveling Plan on the PE, profile-seeded, score-gated exemptions + leveling courses; Required leveling blocks graduation. Placement-exam/graduation coupling being separated in **ADR 060** (proposed); faculty routing for verification in **ADR 059** (proposed). |
| Cohort lockstep / fixed term sequence (typical DMin) | 🟡 | No cohort entity; sequencing only via term fields + course prerequisites |
| Dual / joint degree with shared credit | 🟡 | Partial via multi-emphasis `emphasis_overlap_policy` (Shared Credit Pool / Additional Credits) |

> **Sampling caveat:** this matrix was built from a limited set of real school programs the user is
> currently configuring. It is a strong starting point, not a census — the ADR should treat the ❌/🟡
> rows as candidates to confirm against more institutions.

---

## 3. Gap A — Course-gated requirement activation

**Need:** a requirement (often a thesis/project/internship) should not activate until the student has
**passed a specific named course** (e.g. *Writing a Thesis*).

**Why today's modes don't cover it:** `Credits Passed` is a total-credit threshold; `After Requirement`
chains *graduation requirements*, not courses; `Time Offset` is calendar-based. None can reference a
specific `Course`.

### Candidate directions

- **A1 — New `Course Passed` activation mode (recommended to explore first).**
  Add a `prerequisite_courses` **`Table MultiSelect` (→ Course)** to PGRI, mirroring the existing
  `prerequisite_requirement` field one-for-one. `evaluate_activation()` gains a branch that returns
  active only when every listed course has a passing `Program Enrollment Course` row
  (`status == "Pass"`, the same set `_course_status_sets()` already computes in
  [graduation_candidate.py:161-187](../../../seminary/seminary/graduation_candidate.py#L161-L187)).
  Reuses an in-repo precedent end to end; no structural blocker.
- **A2 — Model each gating course as its own GRI** (Manual Verification or a course-completion Linked
  Document) and reuse `After Requirement` chaining. Zero schema change, but it pollutes the
  requirement list with one synthetic requirement per gating course and double-tracks course state.

### Open questions for the ADR
- **Source of truth for "passed":** `Program Enrollment Course.status == "Pass"` vs the grade fields
  (`pec_finalgradecode` / passing threshold). Candidacy already uses the `"Pass"` status — A1 should
  match it for consistency.
- **Repeatable courses & failures** interact with this (ADR 035): a failed-then-retaken course, or a
  repeatable mandatory course, must resolve to a single unambiguous "passed?" answer.
- **Snapshot timing:** course-pass state changes *after* enrollment, so (like the existing activation
  modes) this must stay an audit-time evaluation, not a frozen snapshot value.

---

## 4. Gap B — Emphasis-scoped requirements

**Need:** a requirement should apply **only to students who declared a given emphasis** (e.g. a
counseling internship for the Counseling emphasis), without inventing a separate program.

**Why today's model doesn't cover it:** emphases (`Program Track`) differentiate only courses and
credits. PGRI rows are program-flat — every enrolled student snapshots every row.

### Candidate directions

- **B1 — `applies_to_emphasis` on PGRI** (Link → Program Track, filtered `is_emphasis = 1`, optional).
  An empty value = applies to all (today's behavior). Snapshot includes the row only for students who
  declared that emphasis. Lightest touch.
- **B2 — A per-emphasis requirement policy layer** (a PGR scoped to a track). Cleaner separation but
  doubles policy authoring and versioning surface.
- **B3 — `Table MultiSelect` of emphases on PGRI** (row applies if the student declared *any* listed
  emphasis). More flexible than B1, same snapshot interaction.

### The central design tension (call this out prominently in the ADR)
Requirements **snapshot-freeze at enrollment** (the catalog-year contract), but
`emphasis_declaration` can be **`Anytime`** or **`Auto-grant`** — so a student may acquire (or drop)
an emphasis *after* enrollment. Emphasis-scoped requirements therefore cannot be fully resolved at
snapshot time; they must be (re)materialized when the emphasis set changes. The cleanest path is to
extend the existing **`resnapshot()`** path ([graduation.py](../../../seminary/seminary/graduation.py))
to run on emphasis declaration/drop, while preserving waivers and respecting the frozen catalog
version. The ADR must also define behavior for:
- **`advisory_only` emphases** — these explicitly "do not affect graduation requirements," so an
  emphasis-scoped requirement on an advisory-only track should presumably never materialize.
- **Dropping an emphasis** after its requirement was started/fulfilled (orphan handling).
- **`blocks_graduation_request`** interaction when an emphasis-scoped mandatory requirement appears
  late in the student's timeline.

---

## 5. Cross-cutting observation

Both gaps are the same shape. The requirement engine has rich **temporal** (Time Offset),
**prerequisite** (After Requirement), and **total-credit** (Credits Passed) dimensions, but it has
**no course-identity dimension** (Gap A) and **no sub-program / emphasis dimension** (Gap B). Each
gap is a missing *axis* of the activation/applicability model, not a missing requirement type — which
suggests the ADR frame the solution as "extend the applicability model" rather than "add features
one at a time."

A secondary theme from the matrix: the engine models **what must be done** well, but barely models
**eligibility floors and ceilings** — GPA floor, residency/transfer caps, and time-to-degree limits
are all absent. Those may belong to a separate, later decision than the two gaps that prompted this
note.

---

## Suggested ADR scope

A future **ADR 056** could reasonably take **Gap A + Gap B together** (they share the "extend the
applicability axes" framing and both touch `evaluate_activation()` / snapshot), and explicitly defer
the eligibility-floor cluster (GPA / residency / time-to-degree) to a follow-up. The load-bearing
technical finding to carry forward: **`Table MultiSelect` on a child doctype is an established,
shipping pattern here** — neither gap is blocked by Frappe's grandchild-grid limitation.
