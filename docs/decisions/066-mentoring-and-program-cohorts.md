# 066 — Mentoring and program cohorts

**Date:** 2026-09-02
**Status:** Accepted 2026-09-02 — building blocks only; Phases A–G implemented, automation deliberately not built

## Context

[ADR 065](065-competency-based-education.md) §5 Phase 8 built program cohorts by **deriving them from
mentors**: one Student Group or Cohort per `(program, intake term, mentor)`, membership reconciled from
`Program Enrollment Mentor` on every enrollment save. It works for the school in front of us and does
not generalise.

Four mentoring patterns observed in practice:

| | pattern |
|---|---|
| **a** | An alumnus or staff member mentors with periodic check-ins only, no academic involvement |
| **b** | Peer-led cohorts — the leader is a student |
| **c** | A program mentor whose mentees *are* the cohort |
| **d** | The cohort is stable for the whole program; mentors rotate yearly |

Only **c** fits what was built. The premise that breaks the others is that **the mentor is part of the
cohort's identity**. Under it, pattern **d** is not merely unsupported — it is inverted: a yearly mentor
rotation moves every student into a new cohort and marks them all `Moved` in the old one, recording an
annual mass migration in which nobody actually moved.

Two further problems surfaced against live data:

- **Derivation claims a whole `Cohort Type` namespace.** `cohorting._sync_discipleship_cohort` treats
  every Cohort of the program's type as its to manage, so a hand-authored cohort of that type has its
  students removed on the next enrollment save. On the development site an automated cohort is already
  sitting beside a hand-built one of the same type.
- **Academic privilege is granted by mentorship alone.** `cbe.evaluators_for` filters mentor rows
  against the framework's evaluator categories; `cbe.mentors_of_student` — which gates read access to a
  student's development notes ([ADR 065](065-competency-based-education.md) §8a) — does not. Any active
  mentor row in a competency program reads the notes, in whatever capacity they were recorded.

[ADR 064](064-discipleship-cohorts-and-channels.md) already has the right spine: `Cohort` with a
Person-keyed leader and lineage, and `Cohort Membership` as a standalone, dated, role-carrying record
whose `is_leader` flag is a **cohort-scoped capability**, not a global role. Mentoring is not a
competency-based concern that happens to touch cohorts; it is a cohort concern that competency-based
education draws on. This ADR moves it there.

Scope is deliberately narrow: **the policy fields on `Cohort Type`, the direction mentoring resolves
in, and where academic privilege comes from** — enough that later automation is additive rather than a
redesign. No assignment automation is specified here.

## Decision

### 1. The cohort is authored; mentoring is a dated role on it

`(program, intake term, mentor)` stops being the cohort's key. A cohort has its own identity and its own
name; the people who mentor it are `Cohort Membership` rows with `role = Mentor`, dated like every other
membership.

This is what makes **d** ordinary: rotating a mentor closes one mentor membership and opens another,
and no student membership is touched. It also makes **b** ordinary, because a membership is keyed on
`Person` and a student has one. And it costs nothing for **c**, which becomes a cohort whose mentor
membership supplies the enrollment's mentor rather than the other way round (§4).

**Co-mentoring already works and is preserved.** `Cohort Membership` permits several concurrent rows
with `is_leader = 1` — `_guard_single_active` guards one *active membership per person*, not one leader
— so a mentor pair, or a supervising professor over several student-led sub-cohorts through
`parent_cohort`, needs nothing new. `Cohort.leader` remains the single nominal owner; capability comes
from membership, per [ADR 064](064-discipleship-cohorts-and-channels.md) §1.

**A program cohort is a `Cohort`, and only a `Cohort`.**
`Competency Framework.program_cohort_source` — the Select that let a framework build its program cohorts
out of `Student Group` instead — **is removed**, along with the `Student Group` branch in
`cohorting.py` that read it. Every pattern in the table above is Cohort-shaped: dated memberships, a
Person-keyed leader, lineage through `parent_cohort`, channels. `Student Group` has none of that and
gains none of it cheaply, and keeping two shapes for one concept means every later rule is written
twice and tested once. `Student Group` keeps what it is good at — course-scoped grading rosters and
their member lifecycle — and stops pretending to be a cohort.

**Ending a mentorship is a manual act.** A mentor membership is closed by the cohort's leader or by
staff, on the date they choose. Nothing expires it on a schedule: a term-bounded supervision and a
program-long mentorship are the same record with different dates, and until a school needs the system
to tell them apart, the person who knows the relationship has ended is the one who says so. Splitting
`Program Enrollment Mentor` into term-scoped and program-scoped records is deferred on the same
grounds.

### 2. Cohort Type is the policy record; Cohort Membership is where policy is enforced

`Cohort Type` already holds `program` (nullable), `category` (never wired, because it was neither
helpful nor clear) and `graduates_to` (never wired), and the *course* binding lives on `Course`
([ADR 064](064-discipleship-cohorts-and-channels.md) §6). Only `allow_self_split`,
`default_visibility` and `default_max_size` currently do anything at all.

Everything a school wants to say about a kind of cohort is said **once, on the type**, and enforced on
each `Cohort Membership` as it is written. Policy on the type rather than the cohort, because a rule
that can be edited per cohort is not a rule; enforcement on the membership rather than the cohort,
because membership is where a person and a policy actually meet.

**Three axes, deliberately separate.** The temptation is one rich `category`; the cost is that a school
which wants a program-long cohort led by an alumnus cannot say so. Lifecycle, leadership and automation
vary independently, and each gets its own field.

**Axis 1 — lifecycle: what binds the cohort, and when does it start and end.**

| field | type | notes |
|---|---|---|
| `category` | Select | `Paced Program` — a stage of a time-based program, advancing with the term; requires `program_type = Time-based`. `Throughout Program` — starts at Program Enrollment, ends at graduation. `Course scoped` — bound to a course; `Course.cohort_type` filters to types of this category. `Unrestricted` — no lifecycle at all; maximum freedom for hand-built cohorts. |
| `program` / `program_level` | Link, nullable | What the cohort is bound to. `Paced Program` requires a Program and `Throughout Program` require one of the two; a level binding lets a formation cohort span the programs at that level. Both set is refused — two bindings is two answers. |
| `graduates_to` | Link → Cohort Type, conditional | **The destination type, and only that.** When this cohort's lifecycle ends its members land in a cohort of that type. *When* it ends is not stated here — that is `category`, the only thing that moves a cohort. Offered to the two program categories: `Throughout Program` → an alumni or staff-facing type; `Paced Program` → another `Paced Program` type for the next term's courses, or an alumni/staff type for the last stage. **Hidden for `Course scoped`** — see below — and for `Unrestricted`, which has no lifecycle to end. |

**A course-scoped cohort persists; it does not graduate.** The mechanism already exists and is the
better answer: persistence stops a later course in a sequence from re-placing a student who already
belongs to a cohort of that type, so a student moving SF1 → SF2 keeps their group no matter which
session of SF2 they land in. `graduates_to` would have to choose among those sessions; persistence
never has to choose at all. Two mechanisms for one job is how they come to disagree, so course-scoped
types get one.

| field | type | notes |
|---|---|---|
| `persists_across_courses` | Check, default on | Members stay in this cohort when the course that formed it ends. **Moves here from `Seminary Settings.cohorts_persist_across_courses`**, which is site-wide today: a school may reasonably want its formation cohorts to persist and its practicum cohorts not to, and that is a statement about a *kind* of cohort, which is what a type is. |

**And course-scoped cohorts stay hand-made.** `create_cohorts_from_student_groups` is staff-triggered
and presupposes someone has organised the roster into Student Groups — a judgement about who belongs
with whom that no rule available to us makes better. Automating it would mean either automating a step
that depends on a manual one, or bypassing Student Groups and cutting groups blindly. Neither is an
improvement on a member of staff who knows the students, so `Course scoped` carries no
`automation_rule` and the existing flow is left exactly as it is.

**Where program graduation is wired.** `set_program_status(pe, to_status="Graduated", …)` is the spine
every path to Graduated passes through — the Graduation Request approval calls it rather than acting
itself — so a `Throughout Program` type's `graduates_to` fires there. Hanging it off Graduation Request
would miss a registrar setting the status directly.

`Time-Scoped` is deferred rather than adopted: a practicum group for one season is expressible as
`Course scoped`, or as `Unrestricted` with dates, and nothing yet distinguishes it that those do not.
**Closing a time-bounded cohort is therefore manual** — the leader or a member of staff archives it
when the season ends. That is the honest state of it: a date field that nothing acts on would look like
automation and be none.

**Axis 2 — leadership.** Who may lead is independent of what the cohort is bound to, which is why
`Alumni-led` and `Staff-only` are not lifecycle values.

| field | type | notes |
|---|---|---|
| `leader_eligibility` | Select | `Anyone` (a peer may lead) / `Instructor` / `Alumnus of the bound program or level` / `Staff`. Enforced on `Cohort Membership` when `is_leader` is set, so the rule is checked against the person in front of it rather than trusted at setup. |

There is no matching `member_eligibility`. An automated type's rule already selects who goes in, and a
hand-authored type is hand-authored precisely because a person is deciding — a second Select would ask
the school to restate in configuration what it is doing by hand. Where a guard is wanted for manual
work it belongs where the work happens: a confirmation when someone is added who does not match the
type's binding, not a rule that refuses them.

**Both readings of the alumnus mentor are valid, and the school picks.** An alumnus leading a current
student cohort may be a `Throughout Program` type with `leader_eligibility = Alumnus`, or a second
cohort of its own alongside the academic one. The two axes make either expressible and neither is
wrong; which reads more naturally depends on whether the school thinks of that person as leading *this*
cohort or as running something beside it. No rule is written to prefer one.

Nothing here says who may read a student's academic record. That question belongs to the framework
doing the evaluating, not to the cohort — see §5.

**Axis 3 — automation.** A type is either automated or hand-authored, and a school that wants both runs
two types. That alone removes the need for any "this cohort was derived" marker: automation only ever
touches types that carry a rule, so a hand-authored type's cohorts are untouchable by construction.

| field | type | notes |
|---|---|---|
| `automation_rule` | Select, nullable | Null = hand-authored; automation never creates or fills cohorts of this type. Set = the system creates cohorts of this type and puts people in them, cut by the rule. Opens with `On Program Enrollment`, offered only to the two program-bound categories. **Course-scoped types are never automated** — see below. Deferred: `Per intake term`, `Per site`, `Per residence`, `Per denomination` and combinations — these are what will eventually make automation worth having, which is why the rule is its own axis and not a mode on `category`. |
| `automation_max_size` | Int, nullable | Part of the rule, not a separate policy: when a cut exceeds it, the rule produces several cohorts rather than one oversized one, named with a `.###` suffix. Cutting evenly is the whole point of an automated rule; `default_max_size` stays what it is today — an advisory ceiling for hand-authored work. |

### 3. What "automation" means — and what it does not

Two things were being called automation, and they are independent. Keeping them apart is what stops the
whole design from needing a conflict-resolution mechanism it should never have had.

| facet | lives on | acts on | when |
|---|---|---|---|
| **Creation and initial placement** | `automation_rule` (Cohort Type) | Cohorts of that type, and people who are not yet in one | Once per person, when they first qualify |
| **Collective movement** | `category` (Cohort Type) | The cohort **as a whole**, whoever is in it | At the lifecycle boundary its category defines — term rollover, graduation, course end |
| **Individual movement** | a person | One membership | Whenever a leader or registrar decides |
| **Bulk creation by staff** | `create_cohorts_from_student_groups` | Cohorts of a course-scoped type, from the groups a member of staff organised | When staff run it |
| **Destination of a move** | `graduates_to` (Cohort Type) | — | Consulted by collective movement; states *where*, never *when* |

Bulk creation is in the table because it is the thing most easily mistaken for automation: it creates
many cohorts at once, but a person decided who belongs with whom, and that judgement is the work. It
stays where it is.

The consequence worth stating plainly: **automation places a person once and never re-places them.** It
fills a gap — someone who qualifies and has no membership of that type — and a person who already has
one is simply not a gap. A leader who splits a cohort or moves a member is therefore never undone by
the next run, and no `placed_by_automation` marker is needed to protect them; there is nothing to
protect them from. Collective movement is a different act on a different subject: it moves a cohort,
not a person, so a member who was moved by hand travels with whichever cohort they are now in.

### 4. Cohorts first; the program mentor is derived from membership

Two directions are possible, and they cannot both be the source of truth. Either a student gets a
mentor and their cohort follows from it — what Phase 8 built (ADR 065) — or a student joins a cohort and their
mentor follows from the cohort's mentor membership.

**The cohort is the source.** Pattern **d** settles it: where mentors rotate yearly over a stable
cohort, mentor-first re-derives a new cohort every year and the school's actual grouping is the thing
that gets destroyed. Cohort-first makes rotation one membership change. Pattern **c** is unharmed —
a mentor whose mentees *are* the cohort is expressed by giving that cohort a mentor, which is the same
statement made once instead of once per student.

`Program Enrollment Mentor` therefore becomes **derived and read-only where a cohort supplies it**: the
mentors of the student's cohort, resolved live, shown on the enrollment so the registrar can still see
who mentors this student without maintaining it there. It stays **authored** where no cohort does —
a school with mentors and no cohorts, or a mentor assigned outside any group — so the record does not
lose a capability it has today.

This is the inversion the rest of the ADR assumes, and it is the one that has to be got right first:
every automation later written against these blocks reads the cohort and derives the mentor, never the
reverse.

### 5. Academic privilege comes from the framework, not the cohort

Neither a flag on `Cohort Type` nor a capacity on `Cohort Membership` is the right home for "may this
person see a student's academic record". Both put a competency-based concept inside a record that
non-competency schools also use, and both let cohort configuration widen academic access.

**The `Competency Framework` names the cohort types whose mentors evaluate.** `Competency Framework
Evaluator` gains `cohort_type` (Link, nullable): the framework states that mentors of *this* kind of
cohort evaluate in *this* capacity. A cohort type no framework names confers no academic privilege at
all, however its leaders are configured.

`assignment_source` stays — sections still supply evaluators and that arm is unchanged — but its second
option becomes **`Program Cohort`** in place of `Program Enrollment Mentor`, which is the same
inversion §4 makes everywhere else: the cohort is where the mentor is found.

**A person has academic privilege over a student — grading, competency verdicts, reading their
development plan or notes — only when both hold: they mentor that student, and an evaluator row in that
program's framework names the cohort type through which they do it.**

`cbe.evaluators_for` already composes the two halves this way for section instructors.
`cbe.mentors_of_student` does not — it grants note access to any active mentor row in a competency
program regardless of capacity — and is corrected to.

The consequence that matters: a peer leader, or a mentor of a cohort type the framework does not name,
holds full cohort capability — invite, split, post, shepherd — and **no** academic privilege. Pattern
**b** becomes safe by construction rather than by a rule someone has to remember, and the disclosure
students are shown ("your mentors can read your notes") stays true of the mentors it was written about.
It also puts the decision in the record a chair already edits when defining who evaluates, rather than
in a checkbox on a cohort type a completely different person maintains.

### 6. Deliberately not supported: the check-in-only mentor

Pattern **a** — an alumnus or staff member with no involvement beyond periodic check-ins — is **not**
modelled as mentoring. A mentor is in the cohort's channels and posts and is present to the group; a
relationship that is only two conversations a year is a different thing, and calling it mentoring would
put someone in a cohort's communications who is not part of its life.

A distinct role — *prayer partner* or similar, person-to-person and outside the cohort — may be
introduced later. It is not a cohort membership and not a mentor, and it is out of scope here.

### 7. Edge cases the building blocks have to survive

Not policy for its own sake — each of these is a case where the model above is silent and something has
to happen anyway.

**People leaving.**

- **7.1 - A mentor leaves the institution** — sabbatical, resignation, death. Their mentor memberships stay
  open today and nothing closes them. Disabling an `Instructor` or archiving a `Person` must close their
  open mentor memberships, dated, and surface the cohorts left without a leader. This is the sabbatical
  case generalised, and it is the tool the registrar actually asked for. --> Solution: instructor.json add a html field to render in-line a report of open course schedules, cohorts, culminating projects   
- **7.2 - A student goes on leave.** A `Throughout Program` cohort runs from enrollment to graduation, and a
  leave of absence is neither. Membership stays open with the student marked absent rather than closed,
  or they lose the cohort they will return to. Solution: Since what happens with the student varies, we need to create a report to make this evident for manual action. 
- **7.3 - A student withdraws or transfers programs.** The binding no longer matches. A `program`-bound cohort
  must release them; a `program_level`-bound one may not need to. Both need to be decided, not left to
  whichever query runs first. Solution: that is a policy decision, thus it should live in Cohort Type. If Cohort Type = `Paced Program` or `Throughout Program` we make available a new field "Automatically remove withdrawn/transferred students" (and wire it)

**Groups changing shape.**

- **7.4 A hand-authored cohort at `default_max_size`.** Automated cuts are sized by the rule
  (`automation_max_size`, §2), so what remains is manual work — and there `discipleship/api.py`
  currently **throws**: "This cohort is at its maximum size." A registrar deliberately seating a
  thirteenth student in a group of twelve should be warned, not refused; the ceiling is advice about a
  healthy group size, not a statement about what is possible.
- **7.5 Splitting an automated cohort** — *resolved, no rule needed.* `split_cohort` already sets the
  child's `cohort_type` from the parent, so the child inherits `graduates_to` with it and graduates the
  same way. The behaviour is right; it was just never written down.
- **7.6 Archiving is not wired.** `set_cohort_status` flips `Cohort.status` and **nothing reads it** —
  not permissions, not capability, not any listing. An archived cohort still confers leader access to
  its members. Archiving reads as a way to end a relationship and ends nothing, which has to be either
  implemented or renamed.
- **7.7 `Cohort Type.is_active` is inert.** Its only reader is the Phase 8 code this ADR unwinds. It
  must gate *creation* once `automation_rule` exists — a deactivated type otherwise keeps producing
  cohorts — while leaving existing cohorts working for the students already in them.

**Identity and overlap.**

- **7.9 Two cohort types may not conflict over the same student.** A program may run several automated
  types at once — an academic grouping and a formation grouping serve different purposes and a school
  may want both. What may not coexist is two types that would *contradict* each other over the two
  things a cohort actually decides: **moving together**, and **grades and permissions**. So: at most one
  `Paced Program` type per binding, because two would advance the same student in two directions; and
  at most one type named by a given `Competency Framework`, because two would answer the grading and
  access question twice. Everything else may coexist freely. The point is not to restrain schools — it
  is to remove, at construction, any case where the system would have to guess.
- **7.10 A student in two programs at once** has two program cohorts. Program Enrollment, not student,
  is the key any resolution must use.

**Automation's own edges.**

- **7.13 Automation is forward-only**, and that is the answer to more than one question. It runs on
  submit of a new Program Enrollment or Course Enrollment Individual and at no other time. Turning
  `automation_rule` on does not backfill students already enrolled; equally, a member the school
  removed is never quietly reinstated, because nothing revisits anyone.
- **7.15 Which types a new student enters.** On a new Program Enrollment: find the active Cohort Types
  of the two program-bound categories, for that Program or Program Level, carrying an
  `automation_rule`, and place the student in one cohort of **each**. There may legitimately be several
  — an academic grouping and a formation grouping — and 7.9 guarantees none of them contradict.

  **A Cohort Type named in another type's `graduates_to` may not carry an `automation_rule`** —
  graduation is already its automation, and a second one would place students into a stage they have
  not reached. Validated on `Cohort Type`, with a message naming the type that already graduates into
  it so the chair can see what happened rather than guess.

  Not covered: a school deliberately mixing senior and junior students in one cohort. That stays manual
  until a rule exists that can express it.

## Consequences

- Mentor rotation, peer leadership, co-mentoring, external (non-staff) mentors and site- or
  program-scoped grouping are all expressible without a new grouping doctype and without giving anyone
  an `Instructor` record they have not earned.
- Mentoring stops being competency-only. [ADR 065](065-competency-based-education.md) §5 reduces to
  "competency-based programs draw their evaluators from this", and a non-CBE seminary gets cohorts.
- `Student Group` keeps its course-scoped grading role and its member lifecycle fields, which are
  wanted regardless. `Competency Framework.program_cohort_source` is **removed** (§1) and program
  cohorts are Cohort-only.
- The one-leader validation added in [ADR 065](065-competency-based-education.md) Phase 8 — refusing a
  framework with more than one program-sourced evaluator — is no longer needed once the cohort's mentors
  are memberships rather than a derived key, and should be withdrawn with it.
- Nothing here automates assignment. The three axes in §2 and the direction fixed in §4 are what a
  later reassignment tool, a sabbatical handover, or an intake-rollover job would be written against.
- `Cohort Type.category`, `open_enrollment` and `graduates_to` are inert today, and `default_channels`
  ([ADR 064](064-discipleship-cohorts-and-channels.md) §2) was never added. This ADR gives the first
  three behaviour; the fourth stays outstanding against 064.
- `Seminary Settings.cohorts_persist_across_courses` moves to `Cohort Type.persists_across_courses`.
  `discipleship.enrollment.cohorts_persist()` becomes type-scoped and its one caller with it.
- **No site is live on any of this.** Every field this ADR moves, removes or repurposes —
  `program_cohort_source`, `cohorts_persist_across_courses`, `Cohort Type.category`, `graduates_to`,
  `is_active` — can be changed outright rather than migrated behind a compatibility path. That is the
  reason to settle the shape now: the same decisions cost a patch and a deprecation window a term from
  now, and the cost only ever grows.

## Phasing

**A. Unwind ADR 065 Phase 8.** `cohorting.py` deleted; `sync_program_cohort` removed from both
`Program Enrollment` arms (submit *and* update-after-submit — the second was the one a mentor handover
actually reached); `Competency Framework.program_cohort_source` and the one-leader validation gone;
the `Student Group` cohort fields reverted. `Student Group Members`' `status` / `joined_on` / `left_on`
stay — a grading roster wants them too.

**B. `Cohort Type` becomes the policy record.** The three axes of §2 as fields, with `category`
rewritten to the four lifecycle values, `program_level` alongside `program`, `persists_across_courses`,
`remove_on_withdrawal` (7.3), `leader_eligibility`, `automation_rule` and `automation_max_size`.
Validation covers §2's bindings, 7.9 and 7.15. A patch resets every existing type to `Unrestricted`:
the retired values described *who was in* a cohort and were never wired, and no honest mapping exists
to values that describe what *ends* one.

**C. `Cohort Membership` enforces it.** `leader_eligibility` checked when `is_leader` is set on an open
row — `Instructor` against an active Instructor record, `Staff` against `auth.STAFF_ROLES`, `Alumnus`
against an enabled Alumni Profile for the bound program or level (any program, where the type is
unbound). Because `Cohort.after_insert` creates the leader's own membership, the rule reaches cohort
*creation* too: a cohort cannot be made under a leader its type does not allow. Closed rows are never
re-checked — history records who led at the time, and re-testing it against today's policy would refuse
to save the past. The `default_max_size` throw becomes a warning (7.4), dropped entirely from
`accept_invite`: the seating decision was the inviter's, and warning the invitee tells them nothing
they can act on.

**D. Academic privilege composes.** `Competency Framework Evaluator.cohort_type` (mandatory on a
cohort-sourced row); `assignment_source`'s second option becomes `Program Cohort`. `cbe.cohort_mentors`
replaces `_program_mentors` and is what `evaluators_for`, `mentors_of_student` and `mentees_of` all
compose against, so the two halves are required identically from every direction. The
one-type-per-framework half of 7.9 lands on `Competency Framework.validate`. A patch moves existing
mentor-sourced rows across **without** a cohort type, leaving them inert: guessing one would hand
someone grading rights and a student's development notes on an inference, and narrowing is the only
safe direction for a rule whose purpose is to stop access being granted by accident.

**E. `Program Enrollment Mentor` becomes derived** where a cohort supplies it, authored where none does
(§4). `cbe.mentors_for_enrollment` returns both origins with a `source`, and derived rows are resolved
live and **never written down** — storing them would put a copy of the cohort on every enrollment and
need a sync engine to keep it true, which is the engine Phase A withdrew. An authored row that
duplicates a derived one is suppressed rather than shown beside it: the cohort is the live answer, and
two rows would read as two mentorships. A read-only panel on the enrollment shows the derived mentors
with the cohort each came from; the child table's description now says it is for mentors no cohort
supplies. The mentor report gains **Source** and **Cohort** columns and resolves through the same
function as the grading engine, so the coverage check and the thing it checks cannot drift apart.

**F. `persists_across_courses` moves** off `Seminary Settings`; `discipleship.enrollment.cohorts_persist()`
takes a cohort type and its one caller passes one. The default is on, so a school's behaviour is
unchanged and no patch is needed. `Seminary Settings`' now-empty "Community / Discipleship" section is
relabelled Integrations, its only remaining member being the billing-bridge flag.

**G. Edge cases.** 7.6: archiving now *does* something — an archived cohort refuses invites, splits,
removals and leader changes, and leaves its leader's moderation scope, while staying visible to its
members, because archiving a group should not erase anyone's account of having been in it.
Reactivating is deliberately unguarded; it is the way back. 7.7: `Cohort Type.is_active` gates
*creation* only — retiring a type stops new cohorts and leaves the students already in one
mid-relationship alone. 7.3: `remove_on_withdrawal` fires from `set_program_status`'s terminal branch,
on `Withdrawn` and `Transferred` only — graduation is `graduates_to`, a move rather than a removal — and
never releases a leader (the cohort still needs someone; who replaces them is a decision) or a member of
a level-bound cohort who is still enrolled elsewhere at that level (7.10).

7.1 and 7.2 are answered with **visibility, not automation**. Nothing is auto-closed: a membership
closed by a job cannot be told from one closed on purpose, and who takes a group over is a pastoral
decision. `Instructor` gains an **Open Commitments** panel — open course schedules, cohorts led (with
member counts and whether they are co-led), culminating projects advised — and marking someone inactive
warns with that summary rather than refusing. A **Cohorts Needing Attention** report carries three
issues: no active leader, leader no longer an active instructor (the sabbatical case, which looks fine
from every other listing), and member on leave of absence. A peer-led cohort is flagged by none of them.

Automation itself — the engine `automation_rule` describes — is deliberately *not* a phase here. These
are the blocks it will be written against.

## Open questions

- Leave of absence and re-entry into a later cohort uses the same movement machinery as the failure
  policy; both wait on [ADR 065](065-competency-based-education.md) Phase 9.
