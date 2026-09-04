# 067 — Cohort mentor assignment: a reviewed batch, not a trigger

**Date:** 2026-09-03 (§2 and §5–§7 rewritten 2026-09-04)
**Status:** Accepted 2026-09-04 — extends [ADR 066](066-mentoring-and-program-cohorts.md); assumes
[ADR 068](068-person-first-identity-and-shared-attribute-registry.md); supersedes nothing

## Context

[ADR 066](066-mentoring-and-program-cohorts.md) built the blocks and stopped there, deliberately:

> Automation itself — the engine `automation_rule` describes — is deliberately not a phase here. These
> are the blocks it will be written against.

`Cohort Type.automation_rule` says *when* automation fires (`On Program Enrollment`). Nothing reads it.

What 066 never specified is the half the engine cannot run without: **the mentor pool**. It settled how
students reach cohorts and said nothing about where the mentor comes from, how much mentoring one
person can carry, or what makes a pairing good. A rule that says "place the student" has to answer
"with whom", and every answer to that is a fact about staff, not about students.

**And the trigger this ADR first proposed was wrong.** The earlier draft fired placement on Program
Enrollment. At the moment an enrollment is created, nobody — human or rule — can know whether the
cohort will hold. Enrollments arrive one at a time across an admissions season: the first is placed
against a pool of one, and the twentieth against a pool the first nineteen have already consumed.
Placement quality is a property of the **set**, and a per-enrollment trigger never sees the set. That is
also why the draft had no answer to its own open question — *how do you avoid cohorts below a usable
size?* — because with one student in hand you cannot know whether a group of two becomes a group of
eight.

The second reason is not algorithmic. **A placement is not a row.** It is a notification, a channel, an
introduction, a mentor who has already written to a student. Undoing one costs more than making it well
the first time, and a system that places eagerly spends that cost on the school's behalf without asking.

So the engine stays; the trigger goes. What replaces it is **bulk semi-automation**: the rules
pre-populate a set of cohorts-to-create, a human reviews and adjusts them, and nothing exists until they
say so. This is not a smaller ambition than automation — it is the same matcher with a person between
propose and apply, which is the step a school can remove later once it trusts the output.

Two further things were missing, and neither is discretionary:

- **The data the rules need was not on the spine.** Closed by ADR 068 — see §10.
- **Nothing distinguishes "we could not decide" from "nothing to do".** 066 §7.1 and §7.2 answered that
  shape of problem with visibility rather than automation. A matcher needs the same answer, or a student
  who matched nobody simply vanishes.

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

`faculty.eligible_instructors` returns **Instructors**, while `Cohort.leader` is a **Person**. Since
ADR 068 `Instructor.person` is `reqd`, so that hop is a lookup and not a reconciliation — but it is a
hop, and the planner does it once, server-side, rather than at every comparison.

### 2. Placement is a reviewed batch, and the enrollment trigger is withdrawn

**`Cohort Type.automation_rule` is retired to a Check, `plannable`** — *this type may be planned in
bulk*. Its only meaningful value, `On Program Enrollment`, is the trigger this ADR withdraws; the cut
values 066 §2 deferred beside it (`Per intake term`, `Per site`, `Per residence`, `Per denomination`)
are not triggers at all. One Select holding both axes is a large part of why the field was never
implemented as written. A patch flips existing `On Program Enrollment` rows to `plannable = 1`.

Nothing is lost with it, because everything the Select gestured at now lives where a rule lives: the
pool in `mentor_unit` (§4), the matching in the criteria table (§8), the sizes in §3's min and max. That
placement is the design, not tidiness — **the Cohort Type carries the complete run policy, so a school
that later wants unattended placement changes the trigger and nothing else.** §6 states the test of
whether that held: a planner control with no home on the Cohort Type is the signal it did not.

A run of the planner is one operator, one cohort type, one moment, one transaction:

```
choose type  →  choose the student pool  →  choose the criteria for this run
             →  [Match Students and Mentors]        (proposal: groups of mentor + students)
             →  review, drag, rename, exclude
             →  [Create Cohorts]                    (all-or-nothing)
```

Nothing is written before the second button. There is no draft record, no partially-created cohort, and
no state a second operator can collide with mid-review — the collision surface is the apply step alone,
which §7 handles.

**Why the matcher survives the trigger's death.** Everything expensive here — the pool, the criteria
catalog, the ranking, the capacity arithmetic — is unchanged by who pulls the lever. A school that later
wants placement to happen unattended runs the same function on a schedule and skips the review. This ADR
does not build that, and deliberately does not leave a half-built hook for it.

### 3. Three ceilings and a floor, and they mean different things

| bound | scope | on a drag |
|---|---|---|
| `Academic Unit Capability.max_students` | how much mentoring **this person** can carry, across everything | **warned in-line and with a message on save to contact that mentor to confirm the exception** |
| `Cohort Type.automation_max_size` | how large **one cohort** may get | warned |
| `Cohort.max_size` | this group's own ceiling, seeded from the above | warned |
| `Cohort Type.automation_min_size` *(new)* | below this, a group is not worth forming | flagged |


`automation_min_size` is the answer to the question the earlier draft could not answer, and it is only
answerable in batch: with the whole cohort in hand, "too small" is a fact rather than a guess. It never
refuses — a school with three students and ten mentors gets one flagged group of three and a planner
that says so, which is more useful than three pairs or an error.

ADR 066 §2 described `automation_max_size` as a cut size; under §5's placement it reads as
students-per-mentor-cohort. Same number, and it is worth saying so once rather than leaving two readings
in the record.

### 4. Who is in the pool: the cohort type names its unit

`Cohort Type` gains **`mentor_unit`** (Link → Academic Unit, filtered to `Mentoring Department`), and
that is the entire resolution. It is set, or the planner refuses to run and names the missing setting
rather than guessing.

An earlier draft resolved through a new `Competency Framework Evaluator.academic_unit` first and fell
back to the type. That field is dropped: the evaluator row **already carries `cohort_type`**, so a unit
named beside it says nothing the cohort type could not say itself — and it would have said it in a
second place, reachable only by CBE programs. Two homes for one fact, and only one of them works for
every school.

Which is also how ADR 066's own Consequences are kept rather than contradicted:

> Mentoring stops being competency-only. ADR 065 §5 reduces to "competency-based programs draw their
> evaluators from this", and a non-CBE seminary gets cohorts.

A seminary with no framework has no evaluator rows at all, and reaches the pool anyway.

**This ADR adds nothing to `Competency Framework Evaluator`, deliberately.** Evaluation and placement
now read the same cohort type from opposite sides and share no field. Had a unit lived on the evaluator
row and `cbe.cohort_evaluator_rows` ever grown to filter on it, renaming a unit would silently revoke
someone's grading rights and their access to a student's development notes. Not adding the field is a
better guarantee than a comment asking nobody to read it.

### 5. The matcher: how many groups first, then who leads them, then who joins

Mentor-first greedy — *walk the students, give each one the best mentor with room* — is what an
on-enrollment trigger forces, and it is the wrong shape even in batch: it spreads a small intake across
every available mentor and produces exactly the undersized groups §3 is trying to prevent. With the
whole set in hand the group count can be decided **before** anybody is placed:

```
students   = pool_students(type, filter)          # §6
mentors    = [m for m in faculty.eligible_instructors(unit, ROUTE)
                if every Filter matches (student-agnostic parts) ]
n_groups   = clamp(ceil(len(students) / max_size), 1, floor(len(students) / min_size) or 1)

leaders    = greedy_seed(mentors, students, n_groups)   # each pick: the mentor who
                                                        # ranks best for the most
                                                        # still-unserved students
for s in students:
    candidates = [m for m in leaders if every Filter matches (s, m) and m has room]
    assign s to candidates sorted by each Ranking in idx order   # §8
    else → unplaced, with the reason
```

`greedy_seed` is an approximation of a facility-location problem, and it is stated as one. We are not
solving it optimally, because **an optimum nobody can explain is worse than a good arrangement they can
adjust** — and adjusting it is what §6 exists for. The matcher's job is to get a chair from a blank page
to something 90% right; the last 10% is a person who knows that these two students should not be in the
same room.

**Place-once, exactly as 066 §3 requires.** The pool query itself is the guard: a student with an active
membership of this type is not in it. No `placed_by_automation` marker is introduced; §3 of 066 explains
at length why there is nothing to protect a hand-moved member from.

`Cohort Membership` does gain **`placed_by_rule`** (Small Text, read-only) — what chose this pairing.
Under review-first it carries one of two shapes: the criteria that proposed it, or *"moved by hand
during planning"* when a human dragged the student off the proposal. That distinction is the whole
audit: it is the difference between a rule the school can change and a judgement one person made. It is
an **audit stamp on a decision about a person**, not the protective marker 066 §3 rejected — it changes
no behaviour and nothing branches on it.

New members are inserted `Active`, not `Invited`. An invite the student must accept leaves the placement
in limbo while the mentor's capacity slot has already been consumed.
`discipleship.api.place_student_in_cohort` uses `Invited` because a *human* chose and is asking; a
reviewed batch is a decision already taken, announced rather than proposed.

### 6. The Cohort Planner

A Desk page — `seminary/seminary/page/cohort_planner/` — following the three that already exist
(`communication_inbox`, `classes_and_assessments_calendar`, `program_pricing`). Desk, not the portal,
because everything it touches (Cohort, Cohort Type, Academic Unit, the attention report) is staff work
in Desk, and because `Sortable` is already a frappe global (`libs.bundle.js` sets `window.Sortable`) —
the kanban board drags cards between columns with it, which is this page's exact gesture.

Open to the roles that may write `Cohort`, plus the resolved unit's chair.

**Setup — before the first button.**

- **Cohort Type** (required). Resolves the unit through §4, and pre-fills everything below.
- **Students.** Always scoped to those *needing* placement — nobody with an active membership of this
  type is offered. Within that:
  - **All** *(default)*
  - **Never in this cohort type** — no `Cohort Membership` of the type at any status. First placement.
  - **No longer in this cohort type** — a membership exists at `Left` or `Removed`. Re-placement, and it
    is a materially different conversation: this student had a mentor and does not now.
- **Mentors.** The eligible pool, each with remaining capacity, individually excludable **for this run**.
  A mentor on sabbatical next term is excluded here, not by editing their capability row.
- **Criteria.** The type's configured Filters and Rankings (§8), shown and adjustable **for this run
  only, never written back**. A chair trying the intake with and without gender matching is running an
  experiment, not amending policy.

**CTA — "Match Students and Mentors".** Pure computation: no writes, re-runnable, and re-running
discards the current proposal (with a confirm, once dragging has happened).

**Review — one table per proposed cohort.** An editable name, pre-filled `{Cohort Type} — {Mentor}`,
because it is the name students will see. The mentor, their remaining capacity, the member count against
`min`/`max`. Then the members, each with a **Notes** column of short decision hints computed at proposal
time:

- *`12 km — next nearest mentor 34 km`* — the marginal cost of moving this student, which is the number
  a drag decision actually turns on. A bare distance is not.
- *`Only mentor in pool matching gender`*
- *`Mentor at 9 of 10 capacity`*
- *`Left ZZT Cohort B on 2026-03-14`* — for the re-placement filter
- *`Below minimum size (3 of 4)`* — on the group header

The notes generalise past distance on purpose: a future criterion (denomination, site, residence)
contributes its own hint by the same mechanism it contributes its ranking.

**Distances are rendered server-side and units are a school setting.** `Seminary Settings.distance_unit`
(Kilometres / Miles), seeded to Miles for the United States, **Liberia**, Myanmar and the United
Kingdom, and Kilometres everywhere else. Liberia is not a rounding error for this app — it is a
plausible seminary market, and one of the three countries that never adopted the metric system. The UK
is on the list for a narrower reason: it is metric by law and miles by road sign, and *"how far is my
mentor"* is a road-sign question. One setting rather than a per-user preference, because a plan is read
by several people and mixed units across one table would be worse than a defaulted one. The
**coordinate itself never reaches the client**; the
rendered string does. That is the same line §10 draws for the readiness report.

**Dragging.** A student moves between groups; the group's counts and the moved student's notes
recompute without a round trip, because the proposal payload carries each student's ranked shortlist and
not merely their assignment. A drag that breaks a **Filter** warns and proceeds — overriding the school's
rule in one case is precisely the control being retained, and it is why `placed_by_rule` distinguishes
the two. A student may also be dragged out of the plan entirely, back to the unplaced list.

**Unplaced students are a first-class panel, not an omission.** Each carries why: which Filter emptied
their pool, or which datum was missing. Leaving them unplaced is a legitimate end to a run.

### 7. Applying a plan

**"Create Cohorts" sends the decisions, not the inputs.** The client posts the explicit
`{group name, mentor, [students], placed_by_rule per student}` list, and the server re-derives nothing
from it — it **re-validates** it. Trusting a client-computed proposal would make the drag UI a
permission bypass.

One transaction, all or nothing, and in this order:

1. `for_update` lock on the Academic Unit, so two chairs planning the same pool serialise rather than
   overrun. Different units never contend.
2. Re-check every invariant against current data: each mentor still eligible; each student still without
   an active membership of this type. **Any drift refuses the whole apply** and reports what moved,
   rather than applying the part that still fits — a half-applied plan is the one outcome nobody can
   review.
3. Per group: insert the `Cohort` (`leader` = the mentor's Person — `Cohort.after_insert` seats them as
   an `is_leader` Mentor membership already), then each member as `Active` with its `placed_by_rule`.
4. `faculty.claim_for(unit, ROUTE, mentor)` once per member.
5. No `frappe.db.commit()` anywhere inside — a failure leaves no orphan cohort.

**Capacity is checked but never a veto here**, per §3. A group over its mentor's `max_students` applies,
and the apply response carries the exceptions back so the message telling the chair to confirm with that
mentor is generated from what was actually written, not from what the browser thought it was sending.

`faculty.claim_capability` and `claim_for` do read-then-write on `current_students` with **no lock
today**. They have had that defect all along for internship and CP advisor claims; human-paced
assignment hid it, and a batch apply is what makes two claims read the same last slot. Fixed at the
source with an atomic conditional
`UPDATE … WHERE max_students = 0 OR current_students < max_students`.

That conditional guards the callers who are asking the system to *choose* — `claim_capability`
round-robins, and silently overrunning a ceiling nobody looked at is a bug. It must not become the
planner's answer, so `claim_for` takes an explicit `allow_over_capacity` that the apply path passes
after a human confirmed the overrun. Two different questions: *"is there room?"*, which the atomic
UPDATE answers, and *"will this mentor take one more?"*, which only the mentor can.

Ranking ties break on a stable key ending in the opaque Person id — **never `full_name`**, which is
neither unique nor collation-stable, and would give two mentors called "John Smith" a coin flip nobody
could reproduce.

### 8. Criteria are a seeded catalog with a kind

A seeded `Cohort Assignment Criterion` catalog, referenced from a child table on `Cohort Type`:

| code | kind | needs |
|---|---|---|
| Match student and mentor gender | `Filter` | `Person.gender` |
| Mentor closest distance to student | `Ranking` | `Person` coordinates |

**Filter and Ranking are different operations and the catalog has to say which.** ANDing a ranking is
meaningless — a ranking never fails, it orders. Filters are ANDed to produce the eligible pool;
rankings then order the survivors; capacity decides last.

**The kind is the operand, which is what makes it a category and not a label.** A `Filter` is a
predicate over *(student, mentor)*; a `Ranking` orders mentors given a student. Both are answered by
holding one student against one mentor. A rule that has to hold one student against *another student* is
neither, and would need a third kind — none is added, and Deliberately not decided says what would earn
one.

**A child `Table`, not a Table MultiSelect.** Two rankings are only meaningful in an order, and a
MultiSelect neither shows nor stably preserves one. `idx` *is* the precedence.

The catalog's `handler` is `read_only` **and** validated against a hard-coded registry. A free-text
dotted path an admin can type is remote code execution by form field.

A future criterion — denomination, residence, site — declares its Person field, its kind and its Notes
hint, and needs no new wiring. That was the point of building a catalog rather than two checkboxes.

### 9. A rule may only be chosen when its data is guaranteed

ADR 068 shipped `seminary/seminary/person_fields.py`: the single declared list of what a shared human
attribute is, which role fields mirror it, and which are snapshots. **`Mandatory Personal Field` is a
thin curation layer over that registry, not a second one.** It adds only what the registry has no
opinion about — whether *this school* insists on a field:

| field | who sets it |
|---|---|
| `person_field`, `field_label` | from `person_fields.py`, read-only |
| `automation_valid` | seeded, read-only — this field can carry an automation rule |
| `derived` | from the registry's own `derived` flag — resolvable rather than typeable |
| `mandatory` | **the school** |
| `sources` | from the registry's role bindings — which doctype/field, on which surface |

A criterion is offerable only when its `requires_field` has `mandatory = 1 AND automation_valid = 1` —
enforced in `Cohort Type.validate`, not only in the picker, because a picker filter is a convenience and
this is a rule. **Un-mandating a field a live rule depends on is refused**, naming the cohort types:
silently dropping a criterion changes who mentors whom, and that is not a side effect anyone should get
from a checkbox.

`derived` exists because coordinates cannot be made `reqd` — nobody types a latitude. For a derived row
`mandatory` means *"must be resolvable"*, enforced by the readiness check in §11 and nowhere else.

**"Mandating happens on intake records, never on `Person`" was true when this ADR was drafted and ADR
068 made it false.** It survived here longer than it should have. `Student.gender` is now a
`fetch_from person.gender` mirror: `reqd` on a field nobody can type into is unsaveable, not strict.
`Instructor` is the same. The surfaces where a human still types a shared attribute are exactly three —
**`Student Applicant`**, **`Person Import Row`**, and **`Person` itself, in Desk, by a Registrar** —
and ADR 068 §4 says so in as many words when it observes that after the mirrors land, gender is captured
at the applicant form, the importer, or by a Registrar, *"nowhere else"*.

What has **not** changed is the reason a `reqd` on `Person` is still refused: `ensure_person` is called
with nothing but a `user` from the comms, communication-trigger and partner-portal paths, and a
mandatory `Person.pincode` would break notification delivery and partner signup. So the mandate reaches
Person, but scoped by intent rather than by doctype:

- **`Student Applicant`** — a hard gate, and it already exists.
  `person_fields.assert_capture_complete(doc)` runs in `validate` (ADR 068 §7), identically for
  web-form submits, desk saves and REST inserts. This registry widens the set that call checks; it does
  not introduce the call. Client-side hints still reach admin-built per-program forms through the
  existing `SeminaryWebForm` + `webform_include_js` injection — **a prompt, not a guarantee**, which is
  why the server call is where the sentence ends.
- **`Person` in Desk** — a `msgprint` on save naming the mandated fields still empty, never a throw. A
  Registrar correcting a phone number must not be held hostage to a mentoring rule enabled last week on
  a record created three years ago, and §11's posture is already that data gaps warn while configuration
  contradictions throw.
- **`Person Import Row`** — a warning that `Person Import Batch` already blocks on until a human writes
  an override note. Importing 400 alumni who will never mentor anyone should not be hard-blocked by a
  mentor-matching rule; the note is the record of that judgement.

**And the mentor half has no intake form at all.** An `Instructor` is created by
`seminary.seminary.intake` or by the importer — there is no application, no web form, no capture moment
to hang a mandate on. For mentors, the readiness pre-flight in §11 is not a backstop behind the
enforcement; it *is* the enforcement, and it is the only reason a mentor pool missing gender or
coordinates is discovered before a run rather than during one.

And honestly: mandating reaches records created *after* the toggle. It reaches nothing that already
exists. That is what §11 is for — and, under review-first, a missing datum is far less dangerous than it
was under a trigger. It no longer silently misplaces someone; it shows up in the planner as a student
whose pool was empty, in front of the person who can fix it.

### 10. The spine and the coordinates come from ADR 068

The earlier draft closed five spine gaps here. **ADR 068 closed all of them** — `ensure_person` and
`update_person` take the address; the applicant promotes gender and the address through the registry;
`zipcode` became `pincode` with a value-carrying patch; `person_import_batch._apply_person_address`'s
`db.set_value` bypass is gone; `Instructor.gender` is a mirror of `Person.gender` rather than of
erpnext's optional `Employee`. Coordinates likewise: the `Person` fields at `permlevel: 1`, the
`Address Geocoding Settings` single with its Google and vendor-proxy modes, the queued-on-address-change
trigger and the sweeper that retries a `Failed` lookup but never an `Unresolvable` one.

What stays here is what this ADR is actually about: how distance *orders a pool*, how it is *rendered
for a decision* (§6), and the readiness pre-flight that names mentors without a usable point.

Two consequences of that split worth carrying: **`geo_status`, not latitude, is what says whether a
person has a usable point** — Frappe's Float columns are `NOT NULL DEFAULT 0`, so an unresolved
coordinate reads as `0.0, 0.0`, a real place in the Gulf of Guinea. And **Program Chair gets nothing at
permlevel 1**: they get counts and rendered distances, never a coordinate. The matcher reads coordinates
server-side and returns none to any client.

**Consent belongs at collection.** A disclosure on the application form ("your address is used to assign
you a mentor near you"), and enabling the provider account is the school's own auditable act of consent
to transmit addresses to it. `Person Consent` is channel-scoped and drives comms routing; bending it to
cover data-use would break that.

### 11. Nothing is guessed, and nothing is silent

**When the filters leave nobody, the student is left unplaced** — no relaxing a rule, no overflow
cohort. But under review-first this needs far less machinery than the earlier draft built for it.

**The `Cohort Placement Exception` doctype is dropped.** It existed to carry, out of an unattended job,
the reason a student was skipped — a record only necessary because nobody was watching. In a reviewed
batch the unplaced panel (§6) shows exactly that, to the person running the batch, at the moment it
happens; and a student still unplaced at the end of a run is simply still in the pool the next time the
planner opens. A stored exception would be a second, staler answer to a question the pool query already
answers, with its own auto-resolution rules to get wrong.

What survives is the **push** half, because the planner is pull and somebody has to be told there is
work: `unplaced` joins `no_leader`, `inactive_leader` and `member_on_leave` as a fourth issue code on
the existing `Cohorts Needing Attention` report — computed by query, stored nowhere.

**A readiness pre-flight tells a chair at 2pm, not at 2am.** On the `Cohort Type` form, and inside the
planner's setup step before the CTA is enabled: *"3 of 11 mentors in Mentoring Department X have no
coordinates."* Mentor gaps are blockers; student gaps are warnings with a count — **a single student
without gender makes that one student unplaced, but a mentor pool without gender makes the rule
inoperable.** The check names people and counts, never a coordinate.

Data gaps `msgprint` rather than throw on save, mirroring 066 Phase C's own choice to turn the
`default_max_size` throw into a warning: you must be able to configure an intent before the data is
clean. Configuration *contradictions* — a criterion whose field is not mandatory — do throw, because
they are fixable in the record in front of you.

## Deliberately not decided

- **The proposal is not persisted.** A run lives in the browser until "Create Cohorts". A saved draft
  would need a staleness story (a plan built Monday, applied Friday, against a pool that moved), a
  second permission surface, and a reconciliation UI — all to protect work that a re-run reproduces in
  seconds, since the matcher is a pure function of inputs the setup step still holds. The cost is real
  and named: **a browser refresh loses the drags.** If chairs report that hurting, a `Cohort Plan`
  doctype is an additive change to §7's payload, not a redesign.
- **Unattended placement.** §2 says why the door is left open and why no hook is left half-built for it.
- **A third criterion kind (`Partition`).** 066 §2's deferred cuts — per intake term, site, residence,
  denomination — read like rules about which students may *share* a cohort, and a `Partition` kind was
  drafted to hold them. They do not earn one. **The test: a rule satisfied by running the planner once
  per value of its key is a run scope, not a kind**, and all four pass it. In steady state they do not
  need even the scope, because time supplies the cut — the students needing placement in March *are* the
  March intake. The cut is an artifact of planning a backlog, and §6's student-pool step narrows one ad
  hoc without declaring anything. What would earn the kind is a rule that *fails* the test: a separation
  constraint — "no two students from the same congregation in one cohort" — which is a predicate over
  two students and cannot be run once per congregation. Plausible for a mentoring seminary; nobody has
  asked for it, and adding a kind is precisely the thing §8's catalog cannot absorb without new wiring.
- **Optimal assignment.** §5's `greedy_seed` is an approximation, on purpose.
- **Distance is only meaningful for a distributed program.** In a residential one every student is next
  to every mentor and the ranking is noise. The criterion is offered, never implied; a school running
  both shapes runs two cohort types.
- **Gender matching is the school's policy, not ours.** It is opt-in, off by default, and a seminary
  operating where such an assignment would be unlawful simply does not enable it.
- **Backfilling coordinates for existing people** is a one-shot, out of scope here.
- **Balancing across runs.** A mentor who took eight students in September is no less eligible in
  January than one who took none — `max_students` is the only memory. Fairness over time is a real
  concern and a different one.
- **The Student→Person address reconciliation** ADR 046 deferred is closed by ADR 068; frappe's
  `Address` doctype is still not adopted. What the distance rule needs is coordinates on one record, not
  a multi-address model.

## Consequences

- **Placement quality becomes a property of the batch**, which is the only level at which it was ever
  decidable. Group count, minimum size and mentor load are chosen with the whole intake visible.
- **Nothing is created until a person says so**, so the expensive, socially irreversible half of a
  placement — the notification, the channel, the introduction — is never spent on a guess.
- Cohort automation gets its mentor pool from the same records, and the same capacity counters, that
  already seat internship advisors and project readers. There is one workload story, not two.
- Planning stays usable by a non-CBE seminary, because `Cohort Type.mentor_unit` reaches the pool
  without a framework — which is what ADR 066's Consequences promised.
- The unit machinery is a real cost for a small school, and it is required **only for planning**. A
  hand-authored cohort needs none of it. That is the same conditional-cost principle that made
  `automation_rule` its own axis in 066 §2.
- `faculty.claim_capability` / `claim_for` become concurrency-safe for their existing callers.
- Every proposed pairing is stamped with what proposed it, and every hand override is stamped as one, so
  a person can answer *"why am I in this group"* — and a school can tell how often its rules are being
  overridden, which is the signal for whether it is ready to remove the review step.
- **Harder:** a placement now requires someone to sit down and run it. That is the trade, stated
  plainly. A school that wanted "set it and forget it" does not get it here, and the argument that they
  should not want it yet is §2's, not a hedge.

## Phasing

Continues ADR 066's A–G. ADR 068 absorbed the earlier draft's I-bis and J, which are gone.

**H.** `Mentoring Department` unit type; `Program Cohort Mentorship` route + seeder;
`Cohort Type.mentor_unit` and `automation_min_size`; `automation_rule` retired to a `plannable` Check,
with its patch.
**I.** The criteria catalog (§8), the pool queries (§6 setup) and the matcher (§5) — server-side and
whitelisted, testable with no UI.
**J.** The apply path (§7), including the `faculty.py` concurrency fix, which stands on its own merits.
**K.** The Cohort Planner page (§6).
**L.** The `Mandatory Personal Field` curation layer (§9), the readiness pre-flight and the `unplaced`
issue code (§11).

I and J are independent; K needs both. L can ship after K — under review-first a missing datum degrades
to a visibly unplaced student rather than a silent misplacement, which is exactly what made it blocking
in the earlier draft and no longer does.

## Open questions

- Whether Google's current terms permit retaining geocodes indefinitely. The vendor-proxy mode is where
  a negotiated term would live, which is an argument for making it the default for hosted schools
  rather than the fallback.
- Whether a run should be able to plan **several cohort types at once** for one intake. Cheap to want,
  and it multiplies the review surface; one type per run until someone asks.
- Whether the cut ever needs declaring. §2 retires `automation_rule` on the argument that the criteria
  table holds the matching rules and time supplies the batch boundary. The case that would reopen it is
  a school planning a multi-term backlog often enough that narrowing the pool by hand each time becomes
  the annoyance — at which point the answer is a default on the student-pool step, not a return of the
  Select.
