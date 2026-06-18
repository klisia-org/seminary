# Academic Units & Faculty

Academic Units are the seminary's organisational spine — the departments, committees, and boards that *own* courses and programs and that work is **routed** through. Faculty are wired to a unit once, with a list of **capabilities** (what they're allowed to do), and every subsystem that needs to ask "who can do this?" reads the same answer.

## Overview

Before Academic Units, each subsystem kept its own ad-hoc list of faculty — an advisor pool on each internship type, free-text readers on each project, nothing at all for verifications. That meant the same fact (who advises, who verifies, who examines) had to be maintained in several places. Academic Units replace those scattered lists with **one place per person**: their membership in a unit, carrying the capabilities they hold.

A staff member sets this up on the Desk; the routing, portal worklists, and pickers across the app then all draw from it.

## Key concepts

- **Academic Unit** — a typed organisational unit (a department, committee, or board). Owns courses and/or programs and is the home work routes to.
- **Faculty Capability** — a kind of academic work a person can be wired to perform (advising, verifying, examining, teaching…). A small catalog, seeded with sensible defaults.
- **Academic Unit Membership** — a person's participation in a unit, carrying the list of capabilities they hold there (with optional capacity caps).
- **Capacity** — for capability that tracks it (advising, examining), a per-person *Max Students* and a live *Current Students* count, so assignment can spread load fairly.

## Unit types

Every Academic Unit has a **type** that declares what it owns or does:

| Type | Owns / does |
| --- | --- |
| **Academic Department** | Owns **courses**. Its **Code** (e.g. `ST`) is the source of the course prefix. |
| **Academic Interdepartment** | A neutral home for a course two departments genuinely **co-own**. Lists its member departments; its faculty are the union of theirs (see below). |
| **Program Committee** | Owns **programs** (optional — degree programs span departments, so academic ownership usually flows through courses, not the program). |
| **Board** / **Other Committee** | Governance and faculty groupings (rosters, future web pages). |

Other fields: **Code**, **Description**, **Publish on Web** (for a future public roster), **Is Active** (uncheck to retire a unit without deleting it), and **Chair** — descriptive only. *The chair field grants no permissions*; who can do what stays role-based.

Courses and programs point at their unit through the **Academic Unit** field (formerly the hidden ERPNext "Department" stub). A course belongs to one Academic Department or Interdepartment; a program optionally to a Program Committee.

## Faculty Capabilities

The **Faculty Capability** catalog (Desk → Faculty Capability) lists the kinds of work faculty can be wired to. It ships seeded with:

| Capability | Used by |
| --- | --- |
| Course Instructor | Teaching (the Course Schedule remains the source of truth for who teaches) |
| Thesis/CP Advisor | Culminating-project advising |
| Internship Advisor | Internship advising |
| Placement Examiner | Grading leveling placement exams |
| Manual-Verification Verifier | Verifying manual graduation requirements |
| Mentor | Student-group mentoring |
| Committee/Board Member | Board / committee service |

Each capability carries a **Routes To** machine key (so routing code matches on meaning, not the editable name) and a **Tracks Capacity** flag. When *Tracks Capacity* is on (advising, examining, verifying), memberships holding that capability show **Max Students** / **Current Students**; when off (Course Instructor, Mentor, Board), those capacity fields are hidden — cleaner forms.

## Memberships: wiring faculty to a unit

An **Academic Unit Membership** (Desk → Academic Unit Membership) joins one **Person** to one **Academic Unit**, with a child table of **capabilities**.

- It is keyed on **Person** — the shared human record — so a **board member who is not an instructor** belongs too.
- **Instructor** is derived, read-only: when the Person has an Instructor record it fills automatically, and a *Faculty* / *Non-instructor* badge shows on the form. You never type it.
- Any **academic-routing capability** (advising, verifying, examining, teaching) requires the Person to be an instructor; only **Committee/Board Member** is valid for a non-instructor.
- Each capability row carries its own **Max Students** cap (0 = unlimited) and a read-only **Current Students** count maintained by the assignment logic.

A faculty member who does none of this simply has no active membership.

## How work is routed

When a subsystem needs an advisor/examiner/verifier, it asks the unit's capability pool — picking the person with the **most remaining capacity** (a fair round-robin) and incrementing their count; releasing it when an assignment is withdrawn or reassigned. **Manual entry always wins**: if a human has already chosen the person, auto-assignment stands aside.

This one mechanism backs internship advisors, the verification and placement-exam worklists, and culminating-project advisor assignment. (See [Internships](./internship.md) and [Graduation Requirements](./graduation-requirements.md).)

### Interdepartments resolve faculty transitively

An **Academic Interdepartment** lists its **member units** but does **not** copy their faculty in. When the app asks an interdepartment "who can do X?", it unions the memberships of its member departments **at query time** — so adding a professor to the Theology department automatically makes them available to the joint Theology–Pastoral unit, with nothing to re-sync.

### See Member Roster

On any Academic Unit form, the **See Member Roster** button shows everyone wired to the unit and the capabilities they hold (with capacity). For an interdepartment it shows the transitive roster — the combined faculty of its member departments. It is **read-only**: it displays the roster live and stores nothing, so there is no copy to drift.

## The Faculty Worklist (portal)

Faculty wired with the **Manual-Verification Verifier** or **Placement Examiner** capability get a **Faculty Worklist** entry in the portal sidebar. It lists the open work routed to them in their unit(s):

- **Verifications** — pending manual-verification graduation requirements; *Mark Verified* acts in place.
- **Placement Exams** — placement assessments awaiting a score; *Record Score* enters the result, which immediately resolves the student's leveling plan.

A Program Chair, Seminary Manager, or System Manager sees every unit's work; a plain instructor sees only work in the units they're wired to.

## Reports

**Academic Unit Faculty Audit** (Desk → reports) lists memberships, capabilities, and capacity grouped by unit, flagging gaps a manager should fix:

- **No chair** — a unit with no chair set.
- **No capability** — a member wired to a unit but holding no capability.
- **Over capacity** — a capability whose Current Students has reached its Max.

Tick **Only Issues** to see just the flagged rows, or filter to one unit.

## Day-to-day for staff

- **Set up the spine once.** Create your Academic Departments (with codes), any Program Committees, and boards. Point courses and programs at their unit.
- **Wire each faculty member** with a membership and the capabilities they hold; set Max Students where capacity matters.
- **Let routing do the rest.** Internship/advisor/examiner/verifier assignment then draws from these pools automatically, and faculty see their work in the portal worklist.
- **Audit periodically** with the Academic Unit Faculty Audit report.

## Configuration vs. desk edits

The Faculty Capability and Academic Unit catalogs are seeded **create-only-if-missing** on install and migrate, so your edits to them survive upgrades — they are never overwritten.

## Related

- [Internships](./internship.md) — advisor pools now draw from the unit's Internship Advisor capability.
- [Graduation Requirements](./graduation-requirements.md) — manual-verification routing, culminating-project advisor assignment and reader policy, External Examiners, and leveling placement assessments.
