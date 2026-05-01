# Enrollment

Enrollment manages how students register for programs and courses within an academic term.

## Overview

Students can self-enroll through the LMS portal during configured enrollment windows, or administrators can enroll students directly through the Frappe Desk.

## Key concepts

- **Enrollment Window** — the date range during which self-enrollment is open
- **Course Enrollment** — the record (Course Enrollment Individual, "CEI") linking a student to a course schedule for a specific term
- **Enrollment Capacity** — optional limit on students per course section

## Course Enrollment lifecycle

A Course Enrollment Individual moves through a four-state workflow:

```
Draft  →  Awaiting Payment  →  Submitted  →  Withdrawn
   ↘─────────────────────────────↗
```

- **Draft** — created but not yet submitted; nothing has happened beyond saving the row
- **Awaiting Payment** — submitted, Sales Invoices generated, but the student has not been added to the course roster yet (no LMS access)
- **Submitted** — the student is fully enrolled: on the course roster, on the Program Enrollment's course list, eligible to receive grades
- **Withdrawn** — automatically set when a Course Withdrawal Request reaches Academic Approval; visible in the CEI list view as a list-state pill

Which path the CEI takes from Draft depends on the **Program** the course belongs to:

| Program flags | Draft submits to | Why |
| --- | --- | --- |
| Free Program (`is_free`) | Submitted | No invoicing, no payment to gate on |
| Paid + Require Payment Before Enrollment | Awaiting Payment | Hold the seat until the student pays |
| Paid + payment not required | Submitted | Invoice the student but enroll them anyway |

For programs configured as *Require Payment Before Enrollment*, the CEI auto-advances from **Awaiting Payment** to **Submitted** when the student's cumulative payments cross the program's *Minimum Payment %* threshold (default 100%). For mixed-payer scenarios (student + scholarship + third party), the threshold is computed against the *total* invoiced amount across all linked Sales Invoices.

### Manual override

If a payment arrives off-platform (cash at the registrar's office, wire transfer reconciled later, special exception), an Academics User can use the **Mark as Paid** workflow button on an Awaiting Payment CEI to advance it to Submitted without recording a Payment Entry first.

### Refunds and credit notes

If a credit note posts after the CEI reached Submitted and the recomputed paid percentage falls below the threshold, the CEI **stays at Submitted** — the student isn't silently un-enrolled mid-term. Instead, a ToDo is created and an email is sent to all Academics Users so the registrar can decide whether to file a Course Withdrawal Request, follow up for collection, or accept the new reality.

### Payment Status section on the CEI

The CEI form exposes a *Payment Status* section showing the live state:

- **Total Invoiced** — sum of all linked Sales Invoices
- **Total Paid** — sum of `(grand_total − outstanding_amount)` across those invoices
- **Paid %** — derived; shown in the list view
- **Threshold Met On** — datetime stamped by the system when the auto-advance fired (empty for manual overrides and free programs)

## Free and Ongoing programs

Two Program-level flags shape the enrollment experience for non-traditional offerings:

- **Is Ongoing** (mirrored from Program Level) — programs with no graduation: continuous education, free auditing, devotional courses. CEIs in ongoing programs skip GPA calculation, never trigger graduation audit checks, and have free withdrawal (no Academic Review).
- **Free Program** (per-Program toggle) — bypasses Sales Invoice generation entirely and skips Financial Review on withdrawal. Often combined with *Is Ongoing*, but the two are independent: a paid one-off seminar in an ongoing track leaves *Free Program* off; a free degree program leaves *Is Ongoing* off so graduation logic still runs.

See [Withdrawal → Fast-paths for Ongoing and Free programs](withdrawal.md#fast-paths-for-ongoing-and-free-programs) for how the same flags shape the withdrawal flow.

## Maximum enrollment duration

Programs that bound how long a student may stay enrolled (e.g., "MDiv must finish in 7 years") set **Max Years to Graduate** on the Program (fractional years supported). On enrollment submission, the student's *Max Graduation Date* is auto-set to *enrollment date + Max Years to Graduate*. Registrars can edit *Max Graduation Date* afterward to grant extensions.

The **Time-to-Graduate Risk** report (under Reports → Seminary) lists every active enrollment whose Program has a max enrollment duration, computes remaining credits and remaining time, and ranks students by the credits-per-year pace they need to make their cap. Most-at-risk students appear at the top.
