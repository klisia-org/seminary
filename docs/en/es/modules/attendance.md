# Attendance

Seminaries care about presence — many programs require students to actually be
in the room, and accreditation often hinges on it. The **Attendance** module
covers the whole arc: **recording** who was Present, Tardy, or Absent at each
class meeting (by the instructor, or by students themselves with a check-in
code), turning that into a **standing** against a per-course absence limit,
**warning** everyone before a student is in trouble, and — when a seminary's
policy calls for it — letting the registrar **fail a student for absences** even
when their scores would otherwise pass. Like the rest of the system, nothing
fails a student automatically: the limit raises flags and sends warnings, and a
human makes the call.

## Overview

Attendance has **four layers**, each building on the one before:

```
1. Capture     — mark Present / Tardy / Absent per meeting (instructor or self check-in)
2. Policy      — how many absences are allowed (Program % → per-course limit)
3. Standing    — each student's running tally vs. their limit, with warnings
4. Consequence — the registrar's "Fail for Absence" (FA), a deliberate human step
```

- **Capture** happens on the course's attendance page, on a printed sheet, or
  through student **self check-in** with a rotating-per-meeting code.
- **Policy** is set once at the Program level as a percentage and resolves to a
  concrete number of allowed absences on each Course Schedule.
- **Standing** is computed for every student and shown to them (on their course
  status), to instructors (on the attendance page), and to the registrar (in a
  cross-course report), with notifications when a student nears or crosses the
  limit.
- **Consequence** — failing for absences — is never automatic. It's a registrar
  action that stamps a special **FA** grade.

## Capturing attendance

The instructor opens **Attendance** from a course and sees the class roster with
a three-way control for each student: **Present**, **Tardy**, or **Absent**.
Pick a meeting date on the left, mark everyone, and save. A running
**Absences (used / allowed)** column shows each student's standing at a glance,
coloured amber when they're at risk and red when they're over the limit (this
column only appears once an absence limit is in force — see
[Policy](#the-absence-policy)).

> **Tardy is a first-class status.** It isn't just a note — tardies can count
> toward the absence limit at a configurable rate (e.g. 3 tardies = 1 absence),
> so marking someone Tardy rather than Absent is meaningful.

### The printable sheet

For classrooms where taking attendance on a screen isn't practical, a **Print
blank sheet** button produces a clean roster — student names with empty
Present / Tardy / Absent boxes and a signature line. Print it, mark it by hand
during class, and key it in later. The sheet is generated from the live roster,
so it's always current.

## Student self check-in

Instead of (or alongside) the instructor marking everyone, students can record
their own attendance. The instructor projects a short **check-in code** (and/or
a QR code), students enter it from their phones, and a Present (or Tardy) record
is created for them.

### Showing the code

On the attendance page, **Show check-in code** generates a short, human-readable
code for the selected meeting (e.g. `9WBH5`) and displays it large on screen,
together with a **QR code**. The QR deep-links students straight to the check-in
page with the course, date, and code already filled in — so scanning it is the
fastest path; typing the code is the fallback. The code is generated on demand
and stays stable for that meeting.

### Checking in

Students check in from **Mark my attendance** on their course card, or by
scanning the QR (which opens the check-in page). What they see depends on the
seminary's **time-window** setting (below):

- **Time window enforced (recommended):** the system auto-selects the meeting
  happening _right now_ and either records attendance in one tap or asks for the
  code. A student who checks in after the grace period is marked **Tardy**
  automatically.
- **Time window not enforced (catch-up mode):** the student picks any past
  meeting they have no attendance for. No clock, no code — useful when you can't
  rely on the server clock matching local class times.

> **The clock matters.** Time-window check-in compares "now" against the
> meeting's scheduled time **in the site's time zone** (System Settings → Time
> Zone). If your site time zone doesn't match where classes actually happen, a
> live class can read as "closed." When in doubt, set the site time zone
> correctly, or turn the window off and use catch-up mode.

### Self check-in settings

All under **Seminary Settings → Course Attendance Self Check-in**:

| Setting                                             | What it does                                                                                                                                                                                     |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Enforce meeting time window**                     | On = time-based auto-select (window + code + Tardy apply). Off = catch-up mode (pick any past meeting; no clock, no code). |
| **Require check-in code**                           | Students must type the meeting's code to check in.                                                                                                                               |
| **Check-in Opens Before (mins)** | How early the window opens before the meeting start.                                                                                                                             |
| **Check-in Closes After (mins)** | How late the window stays open after the meeting end.                                                                                                                            |
| **Tardy After (mins)**           | Grace period after start; a check-in later than this is recorded **Tardy**. `0` = never auto-Tardy.                                                              |

Self check-ins only ever mark **Present** or **Tardy** — the instructor still
reviews the roster and finalizes any absences.

## The absence policy

A seminary expresses its rule as a **percentage of meetings a student may miss**,
and the system turns that into a concrete number for each course.

### Three places, one number

1. **Seminary-wide defaults — Seminary Settings → Attendance Policy:**
   - **Tardies per Absence** (default **3**) — how many tardies equal one
     absence toward the limit. `0` disables the conversion.
   - **Warn Within (absences of limit)** (default **1**) — how close to the limit
     a student must be before they're flagged "at risk."
2. **Program → Attendance Policy → Default Max Absence %** — the policy itself,
   e.g. **20%**. `0` means "no attendance limit by default for this program."
3. **Course Schedule → Attendance Policy** — where the percentage becomes a
   number. Editable **only by the registrar / Program Chair** (instructors see it
   read-only):
   - **Auto (from program)** — limit = round( the student's program % ×
     scheduled meetings ).
   - **Custom** — a fixed number of absences that applies to everyone in the
     course.
   - **Disabled** — no attendance limit for this course.

> **The limit is per-student, on purpose.** A course doesn't belong to a single
> program — different students in the same class can be in different programs
> with different percentages. So under **Auto**, each student's allowed number is
> computed from _their own_ program's percentage. A 14-meeting course with a 20%
> program rule gives those students a limit of **3** (20% × 14 = 2.8 → 3); a
> student from a 10% program in the same class gets **2**. **Custom** and
> **Disabled** apply uniformly to everyone.

> **Virtual courses are exempt by default.** When a course's **Modality** is
> _Virtual_ and the policy is _Auto_, the limit is automatically disabled —
> online courses often have only one or two listed meetings, which would make a
> percentage meaningless. _Presential_ and _Hybrid_ courses keep the limit.

### What counts as an absence

- **Effective absences** = recorded **Absent** records **+** (tardies ÷
  _Tardies per Absence_, rounded down). With the default of 3, a student with 4
  real absences and 6 tardies has an effective total of **4 + 2 = 6**.
- **Approved leave is excluded.** An Absent record linked to an approved
  (submitted) Student Leave Application does **not** count toward the limit.
- **Auditors are exempt.** Students auditing a course (not graded) are never
  flagged.
- The denominator is the course's **scheduled meetings**, so the allowed number
  is stable from the first day — even before all attendance has been taken. (The
  limit recomputes automatically when you add meeting dates later.)

## Standing, warnings & notifications

Once a limit is in force, every student gets a **standing** that updates as
attendance is recorded:

- **At risk** — within the warning band (e.g. with a limit of 3 and a buffer of
  1, a student reaches "at risk" at 2 effective absences).
- **Over limit** — past the allowed number.

Where the standing shows up:

- **Students** see an **Attendance** panel on their course status page —
  "_X of Y absences used_" — plus an amber banner when at risk and a red one when
  over the limit.
- **Instructors** see the per-student **Absences (X / Y)** column on the
  attendance page, coloured by standing.
- **Registrar / Program Chair** get the **Students At Attendance Risk** report
  (Desk) — every at-risk and over-limit student across all courses, with their
  count, limit, and status.

**Notifications fire once per crossing.** When a student first enters the warning
band, and again when they first cross the limit, a notification goes to the
**instructor(s)**, the **registrar / Program Chair**, and the **student**. Each
fires once — correcting attendance back down won't spam anyone, and the alert
won't repeat on the next nightly recompute.

## Failure for Absences (FA)

Some programs fail a student who misses too many classes **regardless of their
grades**. This is a deliberate, registrar-driven step — the absence limit only
_flags_; failing is a human decision.

### Setting up the FA grade code

On the **Grading Scale** (Desk → Grading Scale) two fields, beside the existing
withdraw-pass / withdraw-fail notations:

- **Code for Failure for Absences** (default **FA**) — the grade code stamped on
  the transcript when a student is failed for absences.
- **Consider FA in GPA** — whether the FA row counts toward GPA.

The default _Numeric Scale_ ships with `FA` already set, so the action works out
of the box.

### Failing a student

The **Fail for Absence** action is available to the **registrar / Program Chair**
in two places:

- On the **Scheduled Course Roster** (Desk), right next to **Grade Student**.
- On the **Students At Attendance Risk** report — tick the row(s) and choose
  **Fail for Absence**.

Applying it:

- Forces the student's final grade to the **FA** code with a **Fail** result,
  **regardless of their scores** — and it's _sticky_, so re-running grades (or
  the instructor's **Send Grades**) keeps the FA rather than recomputing a
  passing grade.
- Updates the **transcript** (Program Enrollment Course → status _Fail_, grade
  _FA_) and removes the course's credits from the student's total if they had
  been counted as passed.
- Is fully **reversible** — **Undo Fail for Absence** clears it and restores the
  real computed grade.

> **Passing scores, failing grade.** That's the whole point of FA: a student can
> have a B average and still receive an FA on the transcript because they missed
> too many classes. The numeric score is preserved for the record; the grade
> code and pass/fail are overridden.

### Reporting a disciplinary incident instead (or as well)

Attendance problems often belong in the [Discipline](discipline.md) module too.
When **Seminary Settings → Instructors create Disciplinary Incident** is on and
an **Attendance**-category Disciplinary Reason exists, a **Report Disciplinary
Incident** button appears:

- On the **instructor attendance page**, next to any student who is at risk or
  over the limit (only for reasons marked _Instructor Portal_).
- On the **Students At Attendance Risk** report, for the registrar — it opens a
  new incident pre-filled with the student and an Attendance reason.

Failing for absences and filing a disciplinary incident are independent: use one,
the other, or both.

## Worked examples

### Example 1 — A standard 20% rule with self check-in

**Goal:** in-person courses allow students to miss 20% of classes; students
check themselves in with a code.

1. **Program → Attendance Policy → Default Max Absence %** = `20`.
2. **Seminary Settings → Attendance Policy:** Tardies per Absence `3`, Warn
   Within `1`.
3. **Seminary Settings → Course Attendance Self Check-in:** Enforce meeting time
   window ✓, Require check-in code ✓, Tardy After `10`.
4. A Presential course with **14 meetings** (Auto policy) gives each 20%-program
   student a limit of **3** absences.
5. In class, the instructor clicks **Show check-in code**, projects the code +
   QR. Students scan/enter it; anyone checking in more than 10 minutes after the
   start is marked **Tardy**.
6. When a student reaches **2** effective absences they're flagged _at risk_
   (everyone is notified once); at **4** they're _over limit_ (notified again).

### Example 2 — Failing a student for absences

**Goal:** a student with a passing average has missed too many classes and the
program fails them.

1. The student shows **over limit** on the **Students At Attendance Risk** report.
2. The registrar ticks the row and clicks **Fail for Absence** (or opens the
   Scheduled Course Roster and uses the button next to _Grade Student_).
3. The student's grade becomes **FA / Fail**; their transcript records FA and the
   course's credits are not counted. If the instructor later runs **Send Grades**,
   the FA sticks.
4. If it was a mistake, the registrar clicks **Undo Fail for Absence** and the
   real grade returns.

### Example 3 — An online course with no attendance limit

**Goal:** a Virtual course with two listed meetings shouldn't be subject to the
percentage rule.

Nothing to do. With **Modality = Virtual** and policy **Auto**, the limit is
automatically disabled — students see no attendance panel, the instructor sees
no absences column, and no one is flagged. If a particular online course _does_
need a limit, the registrar sets its policy to **Custom** with an explicit
number.

## Day-to-day

- **Take attendance.** Open a course → Attendance → pick the date → mark
  Present / Tardy / Absent → save. Or print a blank sheet and enter it later.
- **Run self check-in.** Click **Show check-in code**, project it (and the QR),
  and have students check in from **Mark my attendance**.
- **See who's at risk.** Registrar: run **Students At Attendance Risk** (Desk).
  Instructors: the Absences column on the attendance page. Students: the
  Attendance panel on their course status.
- **Fail (or un-fail) for absences.** Registrar / Program Chair: **Fail for
  Absence** on the roster or the at-risk report; **Undo** to reverse.
- **Set the policy.** Program → Default Max Absence %; override per course on the
  Course Schedule (registrar only).

## Quick reference

| If you want to... | Do this                                                                                             |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Record attendance                                                 | Course → Attendance → mark Present / Tardy / Absent                                                 |
| Print a sheet to mark by hand                                     | Attendance page → **Print blank sheet**                                                             |
| Let students check themselves in                                  | **Show check-in code** (project code + QR); students use **Mark my attendance**  |
| Require a code / set the window                                   | Seminary Settings → Course Attendance Self Check-in                                                 |
| Make tardies count toward absences                                | Seminary Settings → **Tardies per Absence** (0 disables)                         |
| Set the absence rule for a program                                | Program → **Default Max Absence %**                                                                 |
| Override the limit for one course                                 | Course Schedule → Attendance Policy → **Custom** (registrar only)                |
| Turn the limit off for a course                                   | Course Schedule → Attendance Policy → **Disabled** (Virtual auto-disables)       |
| Exclude an absence (approved leave)            | Link the Absent record to an approved Student Leave Application                                     |
| See at-risk students across courses                               | Desk → **Students At Attendance Risk** report                                                       |
| Fail a student for absences                                       | **Fail for Absence** on the roster or at-risk report (registrar / Program Chair) |
| Reverse a Fail for Absence                                        | **Undo Fail for Absence**                                                                           |
| Choose the FA transcript code                                     | Grading Scale → **Code for Failure for Absences**                                                   |
| File an attendance disciplinary incident                          | **Report Disciplinary Incident** on the attendance page or at-risk report                           |

## Related

- [Discipline](discipline.md) — file attendance-related incidents; progressive
  sanctions for repeated absence.
- [Grading](grading.md) — how final grades and Send Grades work; FA overrides the
  computed grade.
- [Withdrawal & Separation](withdrawal.md) — approved leave that excuses
  absences.
- [User Roles](../administration/user-roles.md) — who can set policy, fail for
  absences, and adjudicate.
