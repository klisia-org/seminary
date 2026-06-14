# Scholarships

Seminaries fund students from donations, endowments, and staff-tuition benefits,
and they need that generosity to be **traceable** — every dollar forgiven should
be tied to a named fund, stay within a budget, and be reviewable each term. The
**Scholarships** module separates the _policy_ (a reusable scholarship you
offer) from the _grant_ (one student's award on one enrollment), computes the
discount at billing time rather than baking it into payer splits, and keeps a
running check that recipients still meet the conditions they were given the money
under.

## Overview

There are **two layers**, much like graduation requirements:

```
Scholarships         — the template: type, program, discounts per fee,
   (the policy)         funding, granting & retention criteria
        │  grant to a student's enrollment
        ▼
Scholarship Award    — one student's award on one Program Enrollment, with a
   (the grant)          snapshot of the terms and its own approval lifecycle
        │  at invoice time
        ▼
Discount applied on the student's tuition invoices, booked to the fund
```

- A **Scholarship** is the reusable offer — "Merit Award for the MDiv, 50% off
  tuition, funded from the Scholarship Fund." You define it once.
- A **Scholarship Award** grants that offer to one student's enrollment. It
  **snapshots** the discount terms at the moment of granting, so later edits to
  the template never silently change awards already given.
- The discount is **computed when invoices are raised**, not stored on payer
  rows. The student always owns 100% of their own share; the forgiven portion is
  invoiced to the seminary's scholarship customer and booked against the fund.

## The scholarship template

Create a **Scholarship** for each distinct offer. Its fields fall into four
groups:

- **Identity** — a name, a **Type** (Merit, Need, Work-Study, Staff, or Other),
  and the **Program** it applies to. **Active** controls whether it can be
  granted at all; **Show on Portal** lets students see and apply for it
  themselves.
- **Discounts per fee** — one row per fee category, each either a **Percent** of
  that fee or a **Flat** amount. This is what determines how much is forgiven.
- **Funding** — the **Cost Center** the forgiveness is booked against, and
  **Budget Slots**, the maximum number of awards that may be active at once.
- **Granting criteria** — the **minimum GPA** and **minimum total credits** a
  student must have to qualify, plus free-text **requirements / notes**.
- **Retention criteria** — the **minimum credits per term** and **minimum GPA to
  retain** the award once granted (see [Retention review](#retention-review)).

## The scholarship award

A **Scholarship Award** is one grant to one **Program Enrollment**. When you
pick the scholarship, its discount rows are copied onto the award's **Award
Terms** — this snapshot is what billing reads, so the award is insulated from
later template changes. The award also carries an **effective window**
(_Effective From_ / _Effective To_); the discount only applies while today falls
inside it.

**One award per enrollment.** While an award for an enrollment is active or still
in progress, you cannot create a second one for the same enrollment — only a
rejected or ended award frees the slot.

### The approval lifecycle

Awards move through a workflow:

```
Draft ──Submit──► Submitted ──Send for Review──► Under Review
  │                   │  └──Approve──► Active        │
  │                   └──Reject──► Rejected          ├──Approve──► Active
  └──Grant Directly──► Active                        └──Reject──► Rejected

Active ──Suspend──► Suspended ──Reactivate──► Active
Active / Suspended ──End──► Ended
```

- **Students** can **Submit** a request (from the portal); **Registrars** drive
  every approval step.
- A registrar can skip the queue with **Grant Directly** (Draft → Active).
- An award only ever bills while it is **Active** and inside its effective
  window. **Suspended**, **Ended**, and **Rejected** awards never discount an
  invoice.

## How the discount reaches the invoice

When tuition is billed, the system looks for the enrollment's single **Active**
award (within its window). For each fee on the invoice it then applies the
matching Award Term:

- **Percent** — that percentage of the student's share of the fee.
- **Flat** — the fixed amount, **capped across the term** so several course
  invoices in one term never forgive more than the flat value once.

The forgiven amount is never more than the student actually owes. The student's
own payer percentage is untouched; the discount is a separate, fully-discounted
invoice to the scholarship customer, booked to the fund's cost center so it can
be reported on.

## Budget and availability

Funding is governed by the cost center and **Budget Slots**:

- Set an **ERPNext Budget** against the scholarship's cost center for the fiscal
  year to cap total forgiveness. No budget configured means unlimited.
- **Budget Slots** caps how many awards can be active at once.
- A scholarship is "open" only while it has budget and slots left — this is what
  gates whether students may apply for it on the portal.

## Portal applications

If the global **Seminary Settings → allow portal scholarships** toggle is on
_and_ a scholarship's **Show on Portal** is ticked, an eligible student sees it
on the portal and can apply with a short comment. A student may apply only when
they have an active enrollment in the scholarship's program, the scholarship is
still open, and they don't already hold or await an award on that enrollment.
Applying creates a **Submitted** award for a registrar to review.

## Retention review

Scholarships usually come with strings attached, and the system checks them for
you. A **daily review** compares each active award against its template's
retention criteria (minimum credits per term, minimum GPA to retain). Awards
that fall short are flagged — **At Risk** or **Under Review** — and the
registrars are notified, so a human decides whether to suspend or continue the
award. Nothing is suspended automatically.

## Reports

- **Scholarship Budget vs Given** — how much of each fund's budget has been
  committed this fiscal year.
- **Students at Scholarship Risk** — recipients currently failing their
  retention criteria.
- **Active Scholarships** lists — who currently holds what.

## Day-to-day for staff

| Task                            | Where                                                                            |
| ------------------------------- | -------------------------------------------------------------------------------- |
| Offer a new scholarship         | New **Scholarship** (template) with its discounts and funding |
| Let students apply themselves   | Tick **Show on Portal** + Seminary Settings → allow portal scholarships          |
| Grant an award directly         | New **Scholarship Award** → **Grant Directly**                                   |
| Review a student request        | Open the **Submitted** award → Approve / Send for Review / Reject                |
| Pause an award                  | **Suspend** it (it stops discounting immediately)             |
| Close out an award              | **End** it                                                                       |
| Check a fund's remaining budget | **Scholarship Budget vs Given** report                                           |
| Find recipients who slipped     | **Students at Scholarship Risk** report                                          |

## Related

- [Enrollment](enrollment.md) — how tuition is billed, where the discount lands.
- [Programs](program.md) — scholarships are scoped to a program and its fees.
- [Initial Setup](../getting-started/initial-setup.html#_8-fee-category) — the
  Fee Categories a scholarship discounts.
- [User Roles](../administration/user-roles.md) — who may grant and approve
  awards.
