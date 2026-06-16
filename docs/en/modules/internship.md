# Internships

Many programs ask students to serve a supervised placement before they
graduate — a worship internship in a local church, a chaplaincy term in a
hospital, a pastoral residency. An internship is part *job* (an organization
posts it and accepts students), part *project* (it has deliverables, a faculty
advisor, and a final evaluation), and part *graduation requirement* (it must be
finished, with hours logged, to count toward the degree). The **Internships**
module captures all three in one place: partner organizations post positions,
eligible students apply, the seminary tracks placements, hours, and
requirements, and completion flows straight into the
[Graduation Requirements](graduation-requirements.md) audit.

## Overview

An internship moves through a short, predictable life:

```
Internship Type        (define once: hours, tracking, template, advisors)
        │  organization posts
Internship Position    (a slot, with a weekly commitment and schedule)
        │  eligible student applies
Internship Application (one per student per position; gated by a requirement)
        │  accepted (auto or after review)
Internship Placement   (the site, supervisor, dates — one or more)
        │  the term is served
Hours + Requirements   (logged and signed off)
        │  completed
Graduation Requirement (turns green on the student's audit)
```
<LifecycleDiagram type="internship" />

Everything is configured from Desk. A seminary that does not run internships
simply never creates a type, and nothing changes elsewhere.

## Internship types

An **Internship Type** (Desk → Internship Type) describes *a kind of internship
a student can pursue* — Worship, Chaplaincy, Pastoral — and is reused across many
positions and students. You set it up once. It carries:

- **Default hours required** — the hours a student must log to finish, *unless*
  a program overrides it. Required hours are really a *program* concern, so a
  program's graduation requirement can set its own **Internship Hours Required**
  (Program Graduation Requirement → the internship requirement row). That lets a
  single type (e.g. *Worship*) require 300 hours in one program and 150 in
  another, without cloning the type. The type's value is the fallback when a
  program doesn't set one.
- **Hours tracking** — how those hours count (see [Logging hours](#logging-hours)).
- **Allow multi-site / Max sites** — whether a student may split the internship
  across more than one placement, and how many.
- **Backing course** *(optional)* — when set, the internship is also a real
  course enrollment, so it carries the course's credits, grade, and fees, and
  its grade flows to the transcript. Leave blank for a non-credit internship.
- **Evaluation model** — *Inherited from Course* (when a backing course is set,
  the course's grading scale applies), or, without a course, *Pass/Fail* or
  *Graded* recorded by the faculty advisor.
- **Graduation Requirement Item** — the graduation requirement this internship
  fulfils. This is what gates eligibility and lets completion turn the
  student's audit green (see [Applications](#applications)).

### Requirement templates

A type's deliverables are defined by **Internship Requirement Template** rows
(Desk → Internship Requirement Template, one per deliverable, linked to the
type). Each template declares:

- **Scope** — *Application* (one copy per application, e.g. a learning covenant)
  or *Placement* (one copy per site, e.g. a final site evaluation).
- **Due date rule** — an anchor (Application Date, Placement Start/End,
  Previous Requirement, Expected Graduation, Term Start) plus an offset, so due
  dates are computed automatically for each student.
- **Three party sets** — for the **student**, the **seminary**, and the
  **partner organization**, independently: whether that party submits, what they
  submit (an attachment, text, a link, or just an acknowledgement), the label
  and instructions they see, and whether that party **signs the requirement
  complete**.
- **Submission form template** *(optional)* — a blank form (e.g. an evaluation
  PDF) the party downloads, fills, and re-uploads.

When a student is accepted, the type's templates are **snapshotted** into live
[requirements](#requirements) with their due dates filled in.

### Faculty assignment

A type can carry an **advisor pool**: turn on **Auto-Assign Faculty** and list
instructors with a per-instructor **Max Students** cap. When an application is
accepted, the advisor with the most remaining capacity is assigned automatically
(round-robin). Entering an advisor by hand always wins, and a withdrawal frees
the slot again.

## Positions

An **Internship Position** (Desk → Internship Position) is a slot a partner
organization offers for a given type. Besides the title and description it
carries:

- **Acceptance mode** — *Auto-Accept on Submission* (a submitted application is
  accepted at once and a placement is created) or *Evaluate Applications* (the
  organization reviews first).
- **Commitment & schedule** — a minimum weekly-hours expectation, optional
  preferred start/end dates, and an optional weekly schedule of day-and-time
  blocks.
- **Location** and **Default Site Supervisor** — both scoped to the position's
  organization, so you only pick that org's sites and contacts.
- **Planned placements** — how many students the position can take; it fills and
  closes automatically as students are accepted.

Like job postings, partner-created positions are reviewed by seminary staff
before they are published to students.

**Limiting an organization to certain types.** By default an organization that
*offers internships* may post any type. To restrict it — for example to let only
vetted hospitals offer Chaplaincy — list the approved types under the
organization's **Allowed Internship Types** (Partner Organization → Internships).
An empty list means any type; a non-empty list is enforced when a position is
saved.

## Applications

An **Internship Application** (Desk → Internship Application) is one student's
application to a position. A student may hold one live application per position.

**Eligibility is gated by graduation.** A student may apply only when their
active program enrollment has an **open requirement** of the position's type
(the type's *Graduation Requirement Item*). On submission the application
resolves and records that requirement row; if the student has no open
requirement of that kind, the application is refused. (When a type maps to no
graduation requirement item, the internship is ungated and anyone may apply.)

**Acceptance** is either automatic (auto-accept positions) or a staff/partner
action (evaluate positions). On acceptance the application assigns a faculty
advisor if the type opts in, snapshots its Application-scope requirements, and
creates a first placement.

**Status reflects onto the audit.** As the application advances, the linked
graduation requirement row mirrors it — *Completed* fulfils the requirement; a
rejection or withdrawal releases the row so the student can apply elsewhere.

## Placements

An **Internship Placement** (Desk → Internship Placement) is a single site
fulfilling an application — its organization, **site supervisor** (a contact of
that organization), actual start/end dates, allocated hours, and status. Most
internships have exactly one; a multi-site type may have several, up to its
**Max Sites** — but a *second* (or later) site requires the registrar to tick
**Multi-Site Approved** on the application first, so splitting an internship
across organizations is always a deliberate decision. Hours logged at a placement
roll up to the application, and the placement's own Placement-scope requirements
are snapshotted when it is created.

Only contacts marked **Can Supervise Interns** on the organization are offered as
site supervisors (every contact is eligible by default; uncheck the flag to block
a specific person). The placement also shows the **student's and supervisor's
gender** read-only, so the registrar can weigh a match during approval — this is
informational only and never enforced. Gender is recorded on each person's
**Person** record (the shared identity behind every role), so it is entered once
and reused everywhere.

## Requirements

An **Internship Requirement** is a live deliverable, snapshotted from a template
onto an application (Application-scope) or a placement (Placement-scope). It
shows each party their label, instructions, and any blank form to fill, and
collects their submission. It is **Completed** when every party that must sign
has signed; a waiver is available for exceptions. Mandatory requirements are
what the seminary expects finished before the internship is marked done.

## Logging hours

Hours are recorded as **Internship Hours Log** rows against a placement — a date,
a number of hours, and a short description. Whether a row counts toward the
total depends on the type's **Hours tracking** mode:

| Mode | A logged row counts… |
| --- | --- |
| **Portal Daily Log** | immediately |
| **Portal Daily Log with Supervisor Confirmation** | only once the site supervisor marks it **verified** |
| **Submittable Log** | once the placement's designated hour-log requirement is signed complete |

Counted hours roll up to the placement and then to the application, so a
student (and their advisor) always see progress toward the required total.

## Evaluations and feedback

Two structured forms close out a placement:

- **Internship Supervisor Evaluation** — the site supervisor rates the intern's
  ministry readiness, theological integration, relational skills, and
  initiative, adds comments, and may endorse the student for ministry.
- **Student Internship Feedback** — the student's confidential view of the
  placement: an overall rating, supervision quality, spiritual-formation value,
  workload, whether they would recommend it, and free-text highlights, concerns,
  and suggestions for the seminary.

## Working from Desk

Until the partner and student portals ship, staff run the whole flow from Desk.
To make that practical, turn on **Allow Staff to Submit/Sign on Behalf of Any
Party** under *Seminary Settings → Internships*: with it on, a registrar or
faculty member may fill and sign any party's requirement submission directly,
without a portal round-trip. The sign-off still records which staff member
acted.

*Seminary Settings → Internships* also controls:

- **Show Ungated Internships to All Students** — an internship type with no
  graduation requirement mapped is "ungated". Off (default), such internships
  are Desk-only and hidden from the student portal, so a *forgotten* requirement
  isn't silently exposed; on, they are shown to every student (an intentional
  open internship).
- **What partners see when evaluating** — by default a partner reviewing
  applicants sees only the applicant's name. Opt in per field to also share the
  applicant's **program**, **credit hours passed**, **GPA**, and/or **expected
  graduation**.

## Reports & notifications

- **Internship Placement Roster** (Desk → report) — every placement with its
  student, organization, supervisor, status, and hours progress (logged /
  allocated / % done), filterable by status, type, and organization. The
  registrar's at-a-glance view of who is interning where and how far along.
- **Notifications** — starter communication triggers ship for the key student
  moments: application **accepted**, **rejected**, and **completed**. Edit the
  wording, change the audience, or disable any of them under *Communication
  Trigger* on the desk; they send through the consent-aware, rate-limited
  communication ledger, so they never spam.

## Quick reference

| If you want to... | Do this |
| --- | --- |
| Offer a new kind of internship | Create an Internship Type (hours, tracking, graduation requirement, optional course) |
| Define its deliverables | Add Internship Requirement Templates to the type (scope, due rule, party sets) |
| Auto-assign advisors | Turn on Auto-Assign Faculty and list advisors with caps |
| Let an org offer a slot | Create an Internship Position (acceptance mode, commitment, schedule) |
| Let a student apply | Create an Internship Application — eligibility is checked against their open graduation requirement |
| Accept without review | Set the position's Acceptance Mode to Auto-Accept on Submission |
| Track a second site | Allow Multi-Site on the type, then add another Internship Placement |
| Record hours | Add Internship Hours Log rows to the placement; verify them if the type requires it |
| Make the internship count toward a degree | Map the type to a Graduation Requirement Item, and add a matching Linked Document requirement to the program ([Allowed documents](graduation-requirements.md#allowed-documents)) |
| Do it all from Desk | Turn on staff-proxy under Seminary Settings → Internships |

## Related

- [Graduation Requirements](graduation-requirements.md) — internships fulfil a
  Linked Document requirement and appear on the Program Audit.
- [Enrollment](enrollment.md) — the student's program enrollment is what an
  internship is gated against and reflected onto.
- [Grading](grading.md) — a course-backed internship carries its grade through
  the normal course-enrollment machinery.
