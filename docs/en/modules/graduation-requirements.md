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

Every library item picks **one** of three types:

- **Event Attendance** — fulfilled by a student attending a specific
  [Event](../modules/academic-calendar.md). Example: *"Spiritual Formation
  Retreat 2027"*. Choose **Event per Student** if every student must show up
  individually; leave it unchecked if a single occurrence (a one-time chapel
  service everyone attends together) satisfies the cohort.
- **Manual Verification** — fulfilled by staff confirming the student did
  the thing, optionally with file evidence from the student, the staff, or
  both. Example: *"Doctrinal Statement Signed"*, *"Chapel Attendance"* (8
  total).
- **Linked Document** — fulfilled when another document in the system
  reaches a specific status. Example: a *Recommendation Letter* moves to
  `Approved`, or a *Culminating Project* moves to `Completed`.

Two flags govern evidence on Manual Verification items:

- **Evidence Submitted by Student** — gives the student an upload button on
  their audit page. Use this for things like a signed acknowledgement form
  the student themselves attaches.
- **Evidence Required by Staff** — staff must attach a file when marking the
  item Fulfilled. Use this for things you must keep on file (a signed
  doctrinal statement, scanned ordination council minutes).

These two flags are independent. A doctrinal statement might require *both*
(student uploads the signed PDF, staff uploads their identity-verification
note). Chapel attendance typically requires *neither* — the staff just
ticks Fulfilled.

> **Why two flags?** Some items, like chapel attendance, are simple — staff
> ticks a box. Others, like a doctrinal statement, need a written document from
> the student *and* a staff verification of identity. One pair of fields
> can model both.

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
- **Quantity Required** — only meaningful for Manual Verification (e.g.
  "8 chapel attendances"). The other two types always count as 1.

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
Verification items.

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

### Example 1 — Chapel attendance (8 services per term)

**Goal:** every student must attend 8 chapel services across the program.

1. **Create the library item.** Desk → Graduation Requirement Item → New.
   - Requirement: `Chapel Attendance`
   - Type: `Manual Verification`
   - Default Quantity: `8`
   - Mandatory: ✓
   - Evidence Submitted by Student: ✗
   - Evidence Required by Staff: ✗ (a tick-the-box record is enough)
   - Instructions: *"Students are expected to attend at least 8 chapel
     services. The chaplain's office signs students in at the door."*

2. **Add it to the program policy.** Desk → Program Graduation Requirement
   → open *MDiv 2026 Catalog* → add a row pointing at `Chapel Attendance`.
   - Activation Mode: `Always Active`
   - Quantity Required: `8` (or override per program — e.g. 4 for a
     part-time MA)

3. **At enrollment**, the system materializes 8 SGR rows for each student,
   labeled *"Chapel Attendance — Slot 1 of 8"* through *"8 of 8"*.

4. **Day to day**, the chaplain's office opens the student's Program
   Enrollment, finds the next *Not Started* slot, and ticks it to
   `Fulfilled`. The Program Audit page updates immediately.

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
project yourself — it ships with the system, including its own reviewer
table and a 9-state workflow.

To wire it into a program:

1. Create a library item *Senior Project*.
   - Type: `Linked Document`
   - Linked Document: `Culminating Project`
2. Add it to the policy with **Activation Mode = Time Offset**, anchor
   `Last Term Starts`, value `0`, unit `Days` — i.e., due once the final
   term begins.
3. At enrollment, the SGR row appears in the snapshot. The student initiates
   the project from the audit page (a *Start Senior Project* button); when
   the project's workflow reaches `Completed`, the SGR row flips to
   Fulfilled automatically.

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

For Linked Document requirements, you usually do **not** mark the SGR row
manually — the linked document's own workflow flips it for you when it
reaches the configured status.

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

### Adding a new linked-document type without code

If your seminary later wants a *new* type of linked document (say,
*Internship Report* — a doctype your IT team builds with its own workflow),
you do **not** need to edit any code. Once the doctype exists with a
`workflow_state` field:

1. Create a library item with `Type = Linked Document` and pick *Internship
   Report* in `Linked Document`.
2. Add it to the relevant program policies with the activation mode you
   want.
3. On each library item with `Activation Mode = On Document Status`,
   specify the status that signals fulfillment (e.g. `Approved`,
   `Completed`).

The system reflects status changes onto SGR rows automatically.

> **Heads-up — bespoke doctypes.** Two requirement types ship with their
> own complete doctypes because the generic "Linked Document" path is too
> thin for them: **Recommendation Letter** (with the external recommender
> portal) and **Culminating Project** (with reviewer rounds). For these,
> use the dedicated doctypes; the system already wires them into the
> graduation audit.

## How this connects back to the Program Audit

The **Program Audit page** (`/program-audit/<enrollment>`) renders a single
consolidated view:

- The **Academics** section, fed from the Program → Courses table, shows
  credit progress and required-course status. *(unchanged)*
- The **Graduation Requirements** section, fed from the SGR snapshot, shows
  every active requirement, grouped by status, with per-row instructions
  and any evidence already on file.

A student is shown `Eligible to graduate` only when both sections are
clear of unfulfilled mandatory items.

## Quick reference

| If you want to... | Do this |
| --- | --- |
| Add a new requirement category for the whole seminary | Create a Graduation Requirement Item (library) |
| Apply a requirement to a specific program | Add a row to that program's Program Graduation Requirement (policy) |
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
- [User Roles](../administration/user-roles.md) — which roles can author
  policies, mark requirements Fulfilled, and waive.
