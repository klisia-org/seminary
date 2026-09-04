 # 067 — Automated cohort mentor assignment

**Date:** 2026-09-03
**Status:** Proposed — extends [ADR 066](066-mentoring-and-program-cohorts.md); supersedes nothing

## Context

[ADR 066](066-mentoring-and-program-cohorts.md) built the blocks and stopped there, deliberately:

> Automation itself — the engine `automation_rule` describes — is deliberately not a phase here. These
> are the blocks it will be written against.

`Cohort Type.automation_rule` says *when* automation fires (`On Program Enrollment`). Nothing reads it.

What 066 never specified is the half the engine cannot run without: **the mentor pool**. It settled how
students reach cohorts and said nothing about where the mentor comes from, how much mentoring one
person can carry, or what makes a pairing good. A rule that says "place the student" has to answer
"with whom", and every answer to that is a fact about staff, not about students.

Two further things are missing, and neither is discretionary:

- **The data the rules need is not on the spine.** The two matching criteria a seminary actually asks
  for — same gender, nearest mentor — read `Person.gender` and a location. `person.ensure_person`
  accepts **no address arguments at all**; `Instructor` never writes gender to `Person` and has no
  address fields; `Student Applicant` promotes neither. The mentor side of both rules is empty today.
- **Nothing distinguishes "we could not decide" from "nothing to do".** 066 §7.1 and §7.2 answered that
  shape of problem with visibility rather than automation. An assignment engine needs the same answer,
  or a student who matched nobody simply vanishes.

This ADR supplies the pool, the criteria, the data plumbing beneath them, and the engine — and keeps
066's posture throughout: the system says what it could not decide rather than deciding badly.

## Decision

### 1. The mentor pool is an org unit, not a new list

A cohort mentor is a member of staff carrying a workload. The app already models exactly that:
`Academic Unit` + `Academic Unit Membership` + `Academic Unit Capability` + `Faculty Capability`, with
`faculty.py` supplying capacity-aware `eligible_instructors` / `claim_for` / `release_capability`
([ADR 059](059-seminary-departments-and-faculty-capabilities.md),
[ADR 062](062-org-units-hierarchy-and-unit-capabilities.md)). The same machinery seats
internship advisors and culminating-project readers. A second, parallel pool would be a second thing to
keep in step, and a second place for capacity to be wrong.

**`Academic Unit.unit_type` gains `Mentoring Department`.** An Academic Department owns courses, a
Program Committee owns programs, a **Mentoring Department owns program cohorts** — and, in the schools
we have talked to, the mentor training and mentor events that go with them.

ADR 059 §7.1 refused a `unit_type` for external readers on the grounds that *"a unit is an org owner,
not a sourcing bucket."* That objection is satisfied here rather than dodged: a Mentoring Department is
an owner in exactly the sense 059 meant. It has a chair, it appears on the org roll-up through
`parent_unit`, and it owns work. A school that wants a pool spanning several departments still uses an
`Academic Interdepartment` with `member_units`, and `faculty._resolve_units` fans out for free.

**`Faculty Capability.routes_to` gains `Program Cohort Mentorship`**, with `requires_instructor = 1`
and `tracks_capacity = 1`.

Deliberately **not** the existing generic `Mentor` route. `Mentor` is `tracks_capacity = 0` and means
"mentors student groups"; retrofitting capacity onto it would change the meaning of every row a school
has already created, and would make one `max_students` budget cover two unrelated commitments.
Capacity is the entire point of the new route.

### 2. Two ceilings, and they mean different things

| ceiling | scope |
|---|---|
| `Academic Unit Capability.max_students` | how much mentoring **this person** can carry, across everything |
| `Cohort Type.automation_max_size` | how large **one cohort** may get |

A mentor with capacity but a full cohort gets a second cohort. A mentor at their capability ceiling is
skipped entirely. ADR 066 §2 described `automation_max_size` as a cut size; under the mentor-first
placement of §4 it reads as students-per-mentor-cohort. Same number, and it is worth saying so once
rather than leaving two readings in the record.

### 3. Who is in the pool: named by the framework, or by the type

`Competency Framework Evaluator` gains **`academic_unit`** (Link → Academic Unit, filtered to
`Mentoring Department`), shown when `assignment_source = Program Cohort`.

But the pool must not be reachable **only** through a framework, because ADR 066's own Consequences
say the opposite:

> Mentoring stops being competency-only. ADR 065 §5 reduces to "competency-based programs draw their
> evaluators from this", and a non-CBE seminary gets cohorts.

An automating `Cohort Type` whose program carries no framework would have nowhere to resolve a unit
from. So `Cohort Type` also gains **`mentor_unit`**, and resolution is two-step:

1. the `academic_unit` on the framework's `Program Cohort` evaluator row for this cohort type;
2. else `Cohort Type.mentor_unit`;
3. else nothing — a `no_mentor_unit` placement exception, never a guess.

**`academic_unit` is placement metadata and never evaluation metadata.** `cbe.cohort_evaluator_rows`
does not read it and must not start: if it ever filtered evaluators, renaming a unit would silently
revoke someone's grading rights and their access to a student's development notes. The field
description says so on the record itself.

**Mandatory only where it means something.** The field is required when
`assignment_source == 'Program Cohort' && cohort_type` — the second clause is load-bearing, not
fussiness. ADR 066 Phase D's `retarget_evaluators_to_program_cohort` patch deliberately left migrated
rows at `Program Cohort` with no `cohort_type`, inert; a plain `mandatory_depends_on` would make every
framework carrying one unsaveable.

### 4. Placement is mentor-first; the cohort is still the record

On a new Program Enrollment, for each active automating `Cohort Type` bound to the program:

```
pool   = faculty.eligible_instructors(unit, "Program Cohort Mentorship")
pool   = [m for m in pool if every Filter matches (student, m)]
pool.sort(by each Ranking, in idx order)
mentor = first with capacity        else → unplaced, and say why
cohort = mentor's open cohort of this type with room, else open one
join(cohort, student); faculty.claim_for(unit, route, mentor)
```

This is not a reversal of 066 §4 ("cohorts first; the program mentor is derived from membership"). §4
fixes the **source of truth** for who mentors whom, and that is unchanged: after placement the cohort
is the record, `mentors_for_enrollment` still derives the enrollment's mentors from it, and rotating a
mentor later is one membership change that moves no student. §4 governs what the records mean; this
governs how the first one gets made.

*** 4. Unanswered issues ***  If a school has a low ratio of students / mentor, how to avoid assigning cohorts below a certain size?

**Place-once, exactly as 066 §3 requires.** The guard is the existing
`discipleship.enrollment.active_cohort_of_type` — a student already in a cohort of the type is not a
gap, so nothing happens. No `placed_by_automation` marker is introduced; §3 explains at length why
there is nothing to protect a hand-moved member from.

`Cohort Membership` does gain **`placed_by_rule`** (Data, read-only) — the criteria that chose. That is
an **audit stamp on an automated decision about a person**, not the protective marker §3 rejected: it
changes no behaviour and nothing branches on it.

New members are inserted `Active`, not `Invited`. An invite the student must accept leaves the
placement in limbo while the mentor's capacity slot has already been consumed.
`discipleship.api.place_student_in_cohort` uses `Invited` because a *human* chose and is asking; the
system placing someone is not asking.

### 5. Criteria are a seeded catalog with a kind

A seeded `Cohort Assignment Criterion` catalog, referenced from a child table on `Cohort Type`:

| code | kind | needs |
|---|---|---|
| Match student and mentor gender | `Filter` | `Person.gender` |
| Mentor closest distance to student | `Ranking` | `Person` coordinates |

**Filter and Ranking are different operations and the catalog has to say which.** ANDing a ranking is
meaningless — a ranking never fails, it orders. Filters are ANDed to produce the eligible pool;
rankings then order the survivors; capacity decides last.

**A child `Table`, not a Table MultiSelect.** Two rankings are only meaningful in an order, and a
MultiSelect neither shows nor stably preserves one. `idx` *is* the precedence.

The catalog's `handler` is `read_only` **and** validated against a hard-coded registry. A free-text
dotted path an admin can type is remote code execution by form field.

A future criterion — denomination, residence, site — declares its Person field and its kind and needs
no new wiring. That was the point of building a catalog rather than two checkboxes.

### 6. A rule may only be chosen when its data is guaranteed

A seeded `Mandatory Personal Field` registry, curated by the school:

| field | who sets it |
|---|---|
| `person_field`, `field_label` | seeded, read-only |
| `automation_valid` | seeded, read-only — this field can carry an automation rule |
| `derived` | seeded, read-only — resolvable rather than typeable |
| `mandatory` | **the school** |
| `sources` | seeded — which doctype/field, on which surface (Desk / Web Form / Import) |

A criterion is offerable only when its `requires_field` has `mandatory = 1 AND automation_valid = 1` —
enforced in `Cohort Type.validate`, not only in the picker, because a picker filter is a convenience
and this is a rule. **Un-mandating a field a live rule depends on is refused**, naming the cohort
types: silently dropping a criterion changes who mentors whom, and that is not a side effect anyone
should get from a checkbox.

`derived` exists because coordinates cannot be made `reqd` — nobody types a latitude. For a derived row
`mandatory` means *"must be resolvable"*, enforced by the readiness check in §9 and nowhere else.

**Mandating happens on intake records, never on `Person`.** `ensure_person` is called with nothing but
a `user` from the comms, communication-trigger and partner-portal paths; a `reqd` on `Person.pincode`
would break notification delivery and partner signup. `Person` is the store; `Student`,
`Student Applicant`, `Instructor` and `Person Import Row` are where a human types.

Three surfaces, three mechanisms, and one of them is not enforcement:

- **Desk** — property setters, the mechanism `SeminarySettings.validate` already uses for
  `Instructor.naming_series`.
- **Web forms** — the shipped form's flags are in its JSON; **admin-built per-program forms cannot be
  edited by us**. They are reached through the existing `SeminaryWebForm` + `webform_include_js`
  injection. Said plainly: **client-side injection is a prompt, not a guarantee.** The actual gate is
  `personal_fields.assert_complete()` in each intake doctype's `validate`, which runs identically for
  web-form submits, desk saves and REST inserts. Where an admin's form simply omits the field, the
  author is warned when they save the form — not the applicant when they submit it.
- **Import** — a warning, not an error. `Person Import Batch` already blocks a warned row until a human
  writes an override note, and importing 400 alumni who will never mentor anyone should not be hard-
  blocked by a mentor-matching rule. The note is the record of that judgement.

And honestly: mandating reaches records created *after* the toggle. It reaches nothing that already
exists. That is what §9 is for.

### 7. The spine gaps this exposes — closed here

None of §5's criteria can read anything until these are fixed. Four are live defects independent of
automation:

- **`ensure_person` / `update_person` accept the address.** Today `address_line_1/2`, `city`, `state`,
  `pincode` reach a Person only through `Person Import Batch` or the portal preferences page — the
  "registrar-intake snapshot" [ADR 046](046-print-voice-personalization-and-address-spine.md) describes
  has never actually reached the spine. Authored fields are last-write-wins under `overwrite=True` but
  **never blank**: a cleared intake field is an omission, not a correction. (`FILL_ONLY_FIELDS` is
  decorative today — `_apply` never reads it — so this needs a real branch, not an added tuple entry.)
- **`Instructor` promotes `gender` to `Person`**, mirroring `Student.update_person_links`. Without it
  the mentor half of the gender filter is permanently empty. `Instructor` gains **no** address fields:
  the mentor's location is on their `Person`, full stop. A fourth writable mirror would repeat exactly
  the duplication ADR 046 regrets on `Student`.
- **`Student Applicant` promotes `gender` and the address.** Every gender hand-off is guarded by
  `frappe.db.exists("Gender", value)` — the applicant's field is a Select of the literals
  `Male`/`Female` while `Person.gender` is a Link, and `setup_genders()` enables the *translated*
  names, so the two coincide on an English site and not necessarily elsewhere.
- **`Student Applicant.zipcode` maps to `pincode`.** `api.enroll_student`'s bare `get_mapped_doc`
  copies same-named fields only, so **every admission silently loses the applicant's postal code**.
- **One address writer.** `person_import_batch._apply_person_address` writes with `frappe.db.set_value`,
  bypassing every hook including the geocoding trigger. It is deleted and its fields passed to the
  `ensure_person` call beside it.

### 8. Coordinates, and who may see them

`Person` gains `latitude`, `longitude`, `geo_status`, `geo_precision`, `geo_source`, `geo_resolved_on`
and `geo_address_hash`, at **permlevel 1**. The hash of the normalised address makes "has this changed
since we geocoded it?" an equality test — it stops re-billing an unchanged address and makes a stale
coordinate detectable rather than merely wrong.

A home coordinate is more sensitive than the address it came from, because it is trivially mappable.
Registrar and Seminary Manager read and write at permlevel 1; **Program Chair gets nothing there** —
they get counts from the readiness report, never a coordinate. The engine reads coordinates server-side
and returns none to any client.

**Geocoding is queued on address change, never inline.** A synchronous third-party call inside
`validate` is how an admission web form times out and how an import of 400 rows becomes a 20-minute
request. It never throws and never blocks a save: a student must be admissible while the geocoder is
down. `Unresolvable` (the provider said "no such place") is never retried automatically and clears only
when the address changes; `Failed` (network, quota) is retried by a daily sweeper up to a bound.

**Provider abstraction, Google adapter, vendor-proxy mode.** Schools we host configure nothing: the
proxy carries a site token and we hold the key. Nominatim was considered and rejected — its usage
policy does not permit this shape of lookup, and self-hosting means owning the data refresh. The
adapter shape copies `seminary/seminary/plagiarism/` and calls through
`integrations/client.py`, so every request is logged as an Integration Request for free.

**Consent belongs at collection.** A disclosure on the application form ("your address is used to
assign you a mentor near you"), and enabling the provider account is the school's own auditable act of
consent to transmit addresses to it. `Person Consent` is channel-scoped and drives comms routing;
bending it to cover data-use would break that.

### 9. Nothing is guessed, and nothing is silent

**When the filters leave nobody, the student is left unplaced.** No relaxing a rule, no overflow
cohort. A `Cohort Placement Exception` records the enrollment, the type, the unit and *why* — which
filter emptied the pool, or which datum was missing — and appears on the existing
`Cohorts Needing Attention` report as a fourth issue code beside `no_leader`, `inactive_leader` and
`member_on_leave`. It auto-resolves when the student later gains an active membership of that type:
unlike a membership closed by a job, an exception whose condition has demonstrably gone away carries no
ambiguity about who decided.

**A readiness pre-flight tells a chair at 2pm, not at 2am.** On the `Cohort Type` form, and as a
report: *"3 of 11 mentors in Mentoring Department X have no coordinates."* Mentor gaps are blockers;
student gaps are warnings with a count — **a single student without gender makes that one student
unplaced, but a mentor pool without gender makes the rule inoperable.** The check names people and
counts, never a coordinate.

Data gaps `msgprint` rather than throw on save, mirroring 066 Phase C's own choice to turn the
`default_max_size` throw into a warning: you must be able to configure an intent before the data is
clean. Configuration *contradictions* — a criterion whose field is not mandatory — do throw, because
they are fixable in the record in front of you.

### 10. Concurrency is a real defect here, not a hypothetical

`faculty.claim_capability` and `claim_for` do read-then-write on `current_students` with no lock. They
have had this bug all along for internship and CP advisor claims; human-paced assignment hid it. An
admissions batch is what makes two placements read the same last slot.

Three things: a `for_update` row lock on the Academic Unit for the span of one placement, so
read→filter→rank→claim→insert is atomic and different units never contend; an atomic conditional
`UPDATE … WHERE max_students = 0 OR current_students < max_students` in `faculty.py` itself, fixing the
existing callers too; and no `frappe.db.commit()` inside a placement, so a failed submit leaves no
orphan cohort.

Ranking ties break on a stable key ending in the opaque Person id — **never `full_name`**, which is
neither unique nor collation-stable, and would give two mentors called "John Smith" a coin flip nobody
could reproduce.

## Deliberately not decided

- **Distance is only meaningful for a distributed program.** In a residential one every student is next
  to every mentor and the ranking is noise. The criterion is offered, never implied; a school running
  both shapes runs two cohort types.
- **Gender matching is the school's policy, not ours.** It is opt-in, off by default, and a seminary
  operating where such an assignment would be unlawful simply does not enable it.
- **Backfilling coordinates for existing people** is a one-shot, out of scope here.
- **The Student→Person address reconciliation** ADR 046 defers stays deferred; frappe's `Address`
  doctype is not adopted. What the distance rule needs is coordinates on one record, not a
  multi-address model, and adopting `Address` would mean migrating seven doctypes and every mailing
  surface for no gain to mentoring.

## Consequences

- Cohort automation gets its mentor pool from the same records, and the same capacity counters, that
  already seat internship advisors and project readers. There is one workload story, not two.
- Automation stays usable by a non-CBE seminary, because `Cohort Type.mentor_unit` reaches the pool
  without a framework — which is what ADR 066's Consequences promised.
- The unit machinery is a real cost for a small school, and it is required **only for automation**.
  A hand-authored cohort needs none of it. That is the same conditional-cost principle that made
  `automation_rule` its own axis in 066 §2.
- `ADR 046`'s address spine finally receives addresses from intake, and `ADR 042`'s identity spine
  finally receives gender from every role — both as side effects of needing them, both defects worth
  fixing regardless.
- `faculty.claim_capability` / `claim_for` become concurrency-safe for their existing callers.
- Every automated decision about a person is stamped (`placed_by_rule`) and every non-decision is
  recorded (`Cohort Placement Exception`). Neither changes behaviour; both exist so a person can
  answer "why am I in this group".

## Phasing

Continues ADR 066's A–G.

**H.** `Mentoring Department` unit type; `Program Cohort Mentorship` route + seeder;
`Competency Framework Evaluator.academic_unit`; `Cohort Type.mentor_unit`; the two-step
`pool_unit_for` resolver.
**I.** The `Mandatory Personal Field` registry, its seeder, and the three enforcement surfaces.
**I-bis (blocking, before K).** The §7 spine gaps.
**J.** Coordinates on `Person`, the provider abstraction, the Google and vendor-proxy adapters, the
queued geocode and the daily sweeper.
**K.** The criteria catalog and the placement engine, including the §10 concurrency work.
**L.** The readiness pre-flight and the `unplaced` issue code.

I-bis is strictly blocking. I and J are independent of each other and of H. K needs all of them; L
ships in the same release as K — an engine that can fail quietly and the report that says why must not
be separated by a deploy.

## Open questions

- Whether Google's current terms permit retaining geocodes indefinitely. The vendor-proxy mode is where
  a negotiated term would live, which is an argument for making it the default for hosted schools
  rather than the fallback.
- Whether `automation_rule` should eventually split into trigger and cut (066 §2 lists `Per intake
  term`, `Per site`, `Per residence`, `Per denomination` as deferred). The criteria table introduced
  here is the cut; if more triggers arrive, the Select is the field to revisit.
