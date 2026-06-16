# Graduation Requirements

The Program Audit has always answered the question *"has this student earned
enough credits and passed the required courses?"* But many seminaries graduate
students against a longer list: chapel attendances, ordination interviews,
recommendation letters, doctrinal statements, internship hours, a thesis or
capstone. The **Graduation Requirements** module captures everything that is
*not* a course, lets registrars author it from Desk without code, and feeds
the result into the same Program Audit page students and advisors already
use.

## Overview

Think of graduation as having **two parallel tracks**:

| Track | Where it is configured | What it answers |
| --- | --- | --- |
| **Academics** — credit hours and required courses | Program → Courses table | Has the student passed the right courses and accumulated enough credits? |
| **Graduation Requirements** — everything else | Program Graduation Requirement (this module) | Has the student also fulfilled the non-course evidence (letters, attendance, projects, signed statements)? |

Both tracks roll up into the **Program Audit** page. A student is
`graduation_eligible` only when **all currently-active mandatory** items on
**both** tracks are green. The two tracks are evaluated independently — a
student missing one chapel attendance is not blocked from registering for
courses, and a student who has not yet finished their last course is not
blocked from submitting their recommendation letters.

## The three layers

The module is built in three layers. You will spend most of your time in the
first two.

```
1. Library         — Graduation Requirement Item        (define once, reuse anywhere)
                    │
2. Policy          — Program Graduation Requirement     (bind to a program, with dates)
                    │
3. Instance        — Student Graduation Requirement     (one row per student, frozen at enrollment)
```

### Layer 1 — The Library

A **Graduation Requirement Item** declares *what kind of thing exists in the
seminary*. You author it once, with instructions to students, and reuse it
across as many programs as you like.

Every library item picks **one** of four types:

- **Event Attendance** — fulfilled by a student attending a specific
  [Event](../modules/academic-calendar.md). Example: *"Spiritual Formation
  Retreat 2027"*. Choose **Event per Student** if every student must show up
  individually; leave it unchecked if a single occurrence (a one-time event
  everyone attends together) satisfies the cohort.
- **Chapel Attendance** — *count-based* attendance at recurring chapel
  services, fulfilled automatically as students **check themselves in** from
  the portal. You set how many services are required (e.g. 30); the
  requirement turns green the moment a student's check-in count reaches that
  number. Unlike Event Attendance you do **not** create one record per
  service — the chaplain schedules each chapel once, students self check-in,
  and the system keeps the running tally. See
  [Worked example 1](#example-1-chapel-attendance-self-check-in) for the full
  setup.
- **Manual Verification** — fulfilled by staff confirming the student did
  the thing, optionally with file evidence from the student, the staff, or
  both. Example: *"Doctrinal Statement Signed"*, *"Ordination Interview"*.
- **Linked Document** — fulfilled when another document in the system
  reaches a specific status. You pick the document from a curated list (see
  [Allowed documents](#allowed-documents)). Example: a *Recommendation Letter*
  moves to `Approved`, a *Culminating Project* moves to `Completed`, or an
  *Internship* moves to `Completed`.

Two flags govern evidence on Manual Verification items:

- **Evidence Submitted by Student** — gives the student an upload button on
  their audit page. Use this for things like a signed acknowledgement form
  the student themselves attaches.
- **Evidence Required by Staff** — staff must attach a file when marking the
  item Fulfilled. Use this for things you must keep on file (a signed
  doctrinal statement, scanned ordination council minutes).

These two flags are independent. A doctrinal statement might require *both*
(student uploads the signed PDF, staff uploads their identity-verification
note). A new-student orientation typically requires *neither* — the staff
just ticks Fulfilled.

> **Why two flags?** Some items, like a new-student orientation, are simple —
> staff ticks a box. Others, like a doctrinal statement, need a written
> document from the student *and* a staff verification of identity. One pair of
> fields can model both.

#### Blocks Graduation Request

If your seminary uses the [Graduation Request](graduation-request.md) flow,
each library item has one more flag — **Blocks Graduation Request**
(visible only when `Mandatory` is checked). When set, the student cannot
even *file* a Graduation Request until this requirement is `Fulfilled` or
`Waived`. Use it for hard prerequisites the registrar's office wants
verified up-front: recommendation letters, theses, doctrinal statements.
Items without the flag are still tracked toward graduation eligibility,
but the student can file the request and the academic review step will
catch any leftovers.

### Layer 2 — The Policy

A **Program Graduation Requirement** binds library items to a Program with
effective dates. This is the registrar's main authoring surface.

Fields on the policy header:

- **Program** — which program this policy applies to.
- **Active from / Active until** — the catalog-year window. A student
  enrolling on 2026-09-01 picks up the policy whose window contains that
  date.
- **Is Active** — gate to mark a draft (or superseded) vs. a published policy.

Inside the policy you list **Program Requirement Items** (the policy rows).
Each row picks a library item and adds program-specific binding metadata:

- **Activation Mode** — *when* the requirement becomes "due" for an
  enrolled student. See below.
- **Is Mandatory** — does failing this row block graduation, or is it
  optional/informational?
- **Quantity Required** — the count the student must reach. For **Chapel
  Attendance** it is the number of services to check in to (e.g. 30); for
  **Manual Verification** it is the number of instances (e.g. 8 service-hour
  logs). Event Attendance and Linked Document always count as 1.

#### Activation modes

A requirement might be due *the day a student enrolls* — or only after some
trigger. The four modes:

- **Always Active** — due from day one. Use this for anything the student
  can start at any time (chapel attendance, doctrinal statement).
- **After Requirement** — due only after one or more *other* requirements in
  this same policy have been fulfilled or waived. Use this for prerequisite
  chains: *"Ordination Interview"* becomes due only after *"Pastoral
  Recommendation Letter"* and *"Doctrinal Statement"* are both fulfilled.
- **On Document Status** — due only after a related document reaches a
  given status. The library item's `link_doctype` and the chosen
  `linked_doc_status` together define the gate.
- **Time Offset** — due relative to a date anchor. Choose an anchor
  (Expected Graduation Date, Last Term Starts, Program Starts), an offset
  value, and a unit (Days or Academic Term). *"Senior Recital — due 60 days
  before Expected Graduation Date"* is offset = -60, unit = Days, anchor =
  Expected Graduation Date.

A row whose activation has not yet been triggered shows on the audit as
*Not Yet Active*, and even if mandatory does **not** block graduation
eligibility — it is "not yet your problem." Once active, an unfulfilled
mandatory row blocks graduation.

### Layer 3 — The Instance (snapshot)

When a Program Enrollment is submitted, the system **snapshots** the active
policy into per-student rows called **Student Graduation Requirements**
(SGRs). One SGR row per policy row, multiplied by the quantity for Manual
Verification items. **Chapel Attendance** is the exception — it stays a
*single* row carrying the required count and a live "attended" tally (e.g.
*22 / 30*) rather than splitting into one slot per service.

This snapshot is **frozen for that student.** A registrar publishing a new
policy in 2027 does **not** retroactively change the requirements of a
student who enrolled in 2025. This is the catalog-year contract — it is the
rule seminaries traditionally honor and it is enforced by construction.

The **Program Enrollment** also stores the policy it picked
(`graduation_policy`) so anyone reviewing the file can trace exactly which
catalog year the student is on.

If a registrar genuinely needs to migrate a student to the current policy
(e.g. the student requested it, or a regulator required it), there is a
whitelisted **Resnapshot** action on the Program Enrollment. By default it
preserves any rows that were already waived; the action is logged.

## Worked examples

### Example 1 — Chapel attendance (self check-in)

**Goal:** every student must attend 30 chapel services across the program,
recorded by students checking themselves in.

1. **Create the library item.** Desk → Graduation Requirement Item → New.
   - Requirement: `Chapel Attendance`
   - Type: `Chapel Attendance`
   - Default Quantity: `30`
   - Mandatory: ✓
   - Instructions: *"Attend at least 30 chapel services. Open the Program
     Audit page during the service and tap **Check in**."*

2. **Add it to the program policy.** Desk → Program Graduation Requirement
   → open *MDiv 2026 Catalog* → add a row pointing at `Chapel Attendance`.
   - Activation Mode: `Always Active`
   - Quantity Required: `30` (or override per program — e.g. 15 for a
     part-time MA)

3. **At enrollment**, the system materializes a **single** SGR row per
   student that starts at *0 / 30*.

4. **Day to day**, there is nothing for staff to tick. As each student checks
   in to a chapel service, their tally climbs (*1 / 30*, *2 / 30*, …) and the
   row turns green automatically the moment it reaches 30. The Program Audit
   page reflects it immediately.

#### Scheduling chapels and how check-in works

Chapel services live in their own **Chapel** record (Desk → Chapel → New). A
chapel is a public event — all students and instructors are invited, and it is
open to the public.

- **Topic, date/time, room** — what students see, and when check-in is
  allowed.
- **Chapel Team** — the table where the chaplain assigns the preacher,
  worship leader, host, etc., and tracks each person's invitation status.
- **Confirmed** — students can only check in to a chapel once it is
  **Confirmed**. Leave it unchecked while you are still planning the service.

**The check-in window** is governed by two settings under *Seminary Settings →
Chapel & Official Events*: how many minutes **before** the start and **after**
the end check-in stays open. Set **both to 0** to remove the time limit
entirely (students may check in any time the chapel is Confirmed).

**Optional check-in code.** If *Require check-in code* is enabled in Seminary
Settings, each chapel gets a short human-readable code (shown on the Chapel
record). Display it on screen during the service; students must type it to
check in, which keeps people from checking in while away.

**Optional Google Calendar sync.** If *Sync chapels with Google Calendar* is
enabled and an *Official Google Calendar* is selected in Seminary Settings,
each confirmed chapel is published to that shared calendar (with the chapel
team added), so students and the public can see the schedule. The toggle is
off by default — seminaries that don't use Google Calendar can ignore it, and
individual chapels can still opt out via their own *Sync with Google Calendar*
checkbox.

### Example 2 — Three recommendation letters (with named slots)

**Goal:** every applicant for graduation submits three recommendation
letters — *Pastoral*, *Academic*, *Character* — each from a different kind
of recommender, each with its own instructions.

The instinct is to use one library item with `quantity_required = 3`.
**Don't.** Each letter has a different audience and different instructions.
Create **three separate library items** instead:

- *Pastoral Reference Letter* — Linked Document, target `Recommendation
  Letter`. Instructions: *"Solicit from your home-church pastor."*
- *Academic Reference Letter* — same. Instructions: *"Solicit from a
  professor in your major."*
- *Character Reference Letter* — same. Instructions: *"Solicit from
  someone who has known you for at least 5 years and is not a relative."*

The student sees three distinct entries on the audit, each with its own
guidance. The Recommendation Letter doctype handles the rest: a tokenized
guest-portal link sent to the recommender, multi-channel delivery
(portal / email / manual upload), and a workflow that ends in `Approved`.
When the letter is approved, the SGR row flips to Fulfilled automatically.

### Example 3 — Ordination Interview (after letters)

**Goal:** an ordination interview can only be scheduled *after* both
recommendation letters are in.

1. Create a Manual Verification library item *Ordination Interview*
   (Mandatory, Staff Evidence Required = ✓ with label *"Interview minutes"*).
2. On the policy, add a row for it with **Activation Mode = After
   Requirement** and pick the policy rows for *Pastoral Reference* and
   *Academic Reference* as prerequisites.
3. Until both letters are Fulfilled, the audit shows *"Ordination Interview
   — Not Yet Active"* and does not block graduation. The moment the second
   letter is approved, the row activates and starts counting against
   eligibility.

### Example 4 — Senior Project (a complex linked doctype)

**Goal:** every MDiv student writes a Senior Project, defended over up to
three rounds with reviewers.

This is the **Culminating Project** doctype. You don't need to model the
project yourself — it ships with the system, including reviewer roles, a
staged milestone plan, and its own workflow. The configurable pieces (project
types, milestones, defenses) are described in
[Culminating Projects: types, milestones, and defenses](#culminating-projects-types-milestones-and-defenses)
below.

To wire it into a program:

1. Create a library item *Senior Project*.
   - Type: `Linked Document`
   - Linked Document: `Culminating Project`
   - **Culminating Project Types Allowed**: list the project type(s) a student
     may pick (e.g. *Thesis*, *Summative Paper*).
2. Add it to the policy with **Activation Mode = Time Offset**, anchor
   `Last Term Starts`, value `0`, unit `Days` — i.e., due once the final
   term begins.
3. At enrollment, the SGR row appears in the snapshot. The student initiates
   the project from the audit page (a *Start Project* button, choosing a type
   if more than one is allowed); when the project reaches `Completed`, the SGR
   row flips to Fulfilled automatically.

### Example 5 — Doctrinal Statement (signed by both sides)

**Goal:** the student signs a doctrinal statement; the registrar's office
verifies the signature and files a copy.

1. Create a library item *Doctrinal Statement*.
   - Type: `Manual Verification`
   - Mandatory: ✓
   - Evidence Submitted by Student: ✓, label *"Signed statement (PDF)"*
   - Evidence Required by Staff: ✓, label *"Identity-verification note"*
2. The student uploads the signed PDF on the portal. Their slot moves to
   `Submitted`.
3. The registrar opens the SGR row, attaches the verification note, and
   clicks Fulfilled.

## Culminating Projects: types, milestones, and defenses

A *Senior Project* / *Thesis* / *Capstone* is wired in as a **Linked Document**
requirement pointing at the **Culminating Project** doctype (Example 4). Behind
that one requirement sits a small framework you configure once.

### Project Types

A **Culminating Project Type** (Desk → Culminating Project Type) is a reusable
template for one *kind* of project — e.g. *Thesis*, *Capstone*, *Summative
Paper*. Each type defines:

- **Course** — a culminating project is also a real course enrollment, so it
  earns credit and a grade like any other course. The type names which Course
  backs it.
- **Milestones** — the staged plan every project of this type follows (below).

On the requirement's library item you list the **Culminating Project Types
Allowed**. If you allow exactly one, the student is auto-assigned it; if you
allow several (e.g. Thesis *or* Summative Paper), the student chooses one on the
Program Audit page when they start.

### Milestones

Each Project Type carries a **milestone template** — an ordered list of steps.
For each step you set:

- **Kind** — *Standard*, *Proposal*, *Defense*, or *Final Submission*.
- **Due date** — computed from an **anchor** (Project Start, Enrollment Date,
  Expected Graduation, Term Start, or the Previous Milestone) plus an **offset**
  in days or academic terms. So "Proposal — 30 days after project start" or
  "Defense — one term before expected graduation" are just anchor + offset.
- **Requires Submission** — whether the student must upload work for this step.
- **Sign-offs** — which roles must approve: **Advisor**, **Second Reader**,
  **Third Reader**, **Committee**. A milestone reaches *Approved* only once
  every required role has signed, and the project can be marked *Completed* only
  when all mandatory milestones are approved.

When a student starts a project, the template milestones are **snapshotted**
onto their project — the same frozen-at-start contract as graduation
requirements. Each snapshot row tracks its own status, due date, sign-offs, and
submission round, and overdue milestones are flagged automatically.

### Defenses (and their calendar event)

A milestone of kind **Defense** can carry a calendar event. On the milestone
template, tick **Creates Event** and pick an **Event Category** (see the next
section). Then, from the project workbench, the **advisor** clicks **Schedule
Defense**, picks a date/time and optional location, and the system creates a
calendar Event with the student, readers, and committee as participants.

The defense event is *calendar-only* — it exists so everyone shows up at the
right time. It does **not** auto-fulfil anything; the defense is recorded by the
readers signing off the Defense milestone, exactly like any other milestone.

Students, advisors, and readers do all of this from the **Culminating Project
workbench** (a portal page) where they see milestones and due dates, upload
submissions, and record sign-offs.

## How attendance events are handled

The **Event Attendance** requirement type is backed by two pieces: a reusable
*category* and the dated *events* created from it.

### Event Categories (the type)

An **Event Custom Category** (Desk → Event Custom Category) describes a *kind* of
event students attend — e.g. *Convocation*, *Spiritual Formation Retreat*, *Exit
Interview*. It carries:

- **Per Student** — if ticked, every student needs their *own* occurrence (a
  one-on-one such as an exit interview); if unticked, a *single* occurrence
  satisfies the whole cohort (a convocation everyone attends together).
- **Visibility** — Public (appears on the shared calendar) or Private.
- **Instructions** — copied into each event's description (dress code, what to
  bring, location notes).

Your Event Attendance library item points at the **category**, not at a specific
date — because the same category is reused every year.

### Creating the actual events

There are two ways staff turn a category into a dated event students get credit
for:

- **Cohort event** (*Per Student* off) — from the **Event Custom Category** list,
  click **Create Event** on the category's row, pick a date (and optional
  location). The system creates one Event covering every enrolled student who
  still owes this requirement; marking that Event **Completed** flips all of
  their requirement rows to Fulfilled at once.
- **Per-student event** (*Per Student* on) — from a student's **Program
  Enrollment**, click **Schedule Required Event**, pick the requirement and a
  date. This creates one Event for that student, fulfilled when they are marked
  as attending.

Either way the event is a normal calendar Event — it can be synced to Google
Calendar like any other — and the matching graduation requirement updates
automatically, with no separate "tick Fulfilled" step.

> **Chapel is different.** Chapel attendance is recurring and count-based, so it
> uses its own **Chapel Attendance** type with student self check-in
> ([Example 1](#example-1-chapel-attendance-self-check-in)), not the Event
> Attendance flow described here.

## Day-to-day for staff

### Where to look

- **Per-student status** — open the student's *Program Enrollment* and
  scroll to the *Student Graduation Requirements* table, or open the
  *Program Audit* page from the student portal (staff can also reach it
  through the Backoffice).
- **Per-program policy** — Desk → Program Graduation Requirement → pick the
  active policy for the program.
- **Cohort overview** — a list view of *Student Graduation Requirement*
  filtered by `status = Not Started` and grouped by `requirement_name` shows
  you who still owes what.

### Marking something Fulfilled

Open the SGR row (either from the parent Program Enrollment or directly).
Set `status` to `Fulfilled`, attach Staff Evidence if the requirement asks
for it, and save. The system stamps `verified_by` and `verified_on`
automatically.

For Linked Document and Chapel Attendance requirements, you usually do **not**
mark the SGR row manually — the linked document's workflow (or the student's
own check-ins) flips it for you. You can still waive them, or tick Fulfilled
as an override.

### Waiving a requirement

Sometimes a requirement genuinely should not apply to a particular student
(e.g. the requirement was added for new students and an in-flight student
formally requested an exception). On the SGR row:

1. Tick **Waived**.
2. Enter a **Waiver Reason** (a short paragraph — this is your audit trail).
3. Save. The system records `waived_by` (you) and `waived_on` (now).

A waived row counts as satisfied for graduation eligibility but is clearly
distinguished from `Fulfilled` in reports.

### Publishing a new catalog year

When the seminary changes its requirements, you publish a new policy
**alongside** the old one — you do *not* edit the old one in place.

1. Duplicate the existing Program Graduation Requirement (or create a
   new one).
2. Set `Active from` to the date the new catalog kicks in (e.g.
   `2027-09-01`).
3. Set the previous policy's `Active until` to the day before
   (e.g. `2027-08-31`).
4. Tick `Is Active` on the new one. 
5. Adjust the rows.

Students enrolling **after** the new `Active from` will snapshot against the
new policy. Students already enrolled keep the old one. If a student
explicitly asks to be moved to the new catalog, use **Resnapshot** on their
Program Enrollment.

### Allowed documents

A *"Linked Document"* requirement points at a real document in the system. To
keep that choice friendly, the document types that may fulfil a requirement are
curated in a small list — **Allowed Graduation Document** (Desk → Allowed
Graduation Document). Each entry pairs a document type with a plain-language
**label** and the **fulfilling status** that marks it done. The seminary ships
with the built-in options:

| Label | Document | Fulfilling status |
| --- | --- | --- |
| Thesis / Culminating Project | Culminating Project | `Completed` |
| Recommendation Letter | Recommendation Letter | `Approved` |
| Internship | Internship Application | `Completed` |

When you author a library item with `Type = Linked Document`, you simply pick
from this list under **Fulfilling Document** — the underlying doctype and the
status that fulfils it are filled in for you, so you never type a raw doctype
name or guess a status.

Most seminaries never touch the list itself. If your IT team builds a *new* kind
of linked document (say an *Internship Report* doctype with its own workflow),
an **advanced user** adds one Allowed Graduation Document row for it — no code —
and it becomes available to every program policy. The system reflects status
changes onto SGR rows automatically.

> **Heads-up — bespoke doctypes.** Three requirement types ship with their own
> complete doctypes because the generic "Linked Document" path is too thin for
> them: **Recommendation Letter** (with the external recommender portal),
> **Culminating Project** (with reviewer rounds and milestones), and
> **Internships** (with org-posted positions, placements, hours, and supervisor
> evaluations — see [Internships](internship.md)). For these, use the dedicated
> doctypes; the system already wires them into the graduation audit.

## How this connects back to the Program Audit

The **Program Audit page** (`/program-audit/<enrollment>`) renders a single
consolidated view:

- The **Academics** section, fed from the Program → Courses table, shows
  credit progress and required-course status. *(unchanged)*
- The **Graduation Requirements** section, fed from the SGR snapshot, shows
  every active requirement, grouped by status, with per-row instructions
  and any evidence already on file. Chapel Attendance rows show a live count
  (*22 / 30*) and a **Check in** button whenever a confirmed chapel is open.

A student is shown `Eligible to graduate` only when both sections are
clear of unfulfilled mandatory items.

## Quick reference

| If you want to... | Do this |
| --- | --- |
| Add a new requirement category for the whole seminary | Create a Graduation Requirement Item (library) |
| Apply a requirement to a specific program | Add a row to that program's Program Graduation Requirement (policy) |
| Require students to attend N chapel services | Library item Type = Chapel Attendance, set Default Quantity; schedule Chapel records and mark them Confirmed |
| Require a thesis / capstone | Library item Type = Linked Document → Culminating Project; list the allowed project type(s) |
| Define a project's stages and defense | Add milestones to the Culminating Project Type (anchor + offset, sign-off roles, Creates Event for the defense) |
| Require attendance at a one-off event | Create an Event Custom Category, then Create Event (cohort) or Schedule Required Event (per student) |
| Make a requirement due only after another | Activation Mode = After Requirement, pick prerequisites |
| Make a requirement due X days before graduation | Activation Mode = Time Offset, anchor = Expected Graduation Date |
| Confirm a student satisfied something | Open the SGR row, set status = Fulfilled |
| Excuse a student from a requirement | Open the SGR row, tick Waived, give a reason |
| Update the seminary catalog | Publish a new Program Graduation Requirement with a new Active from date — do not edit old one |
| Move a student onto the new catalog | Resnapshot action on their Program Enrollment |

## Related

- [Enrollment](enrollment.md) — Program Enrollment is where the snapshot
  lives.
- [Academic Calendar](academic-calendar.md) — Events used by Event
  Attendance requirements.
- [Internships](internship.md) — the bespoke linked-document path for
  supervised placements, hours, and supervisor evaluations.
- [User Roles](../administration/user-roles.md) — which roles can author
  policies, mark requirements Fulfilled, and waive.
