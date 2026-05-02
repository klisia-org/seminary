# Graduation Request

The **Graduation Request** is the formal application a student files to graduate. It's the moment the registrar's office stops asking *"could this student graduate?"* and starts processing *"this student wants to graduate this term."* It carries an optional fee, runs through academic and financial review, and ends — after both reviews — at `Approved`.

This module is **opt-in per program**. Schools that handle graduation entirely registrar-side (no student-initiated request) leave it disabled and use the [Program Audit](graduation-requirements.md) page as a passive eligibility view.

## Overview

Two questions live side-by-side on the Program Audit page:

| Question | Answered by |
| --- | --- |
| *Has this student met every requirement to graduate?* | The audit eligibility banner (`Eligible` / `Conditionally Eligible` / `Not Yet Eligible`) |
| *Has this student formally applied to graduate this term?* | The Graduation Request CTA below the banner |

The first is automatic. The second is an explicit student action that books a fee, surfaces in the registrar's queue, and goes through review.

## Enable it on a program

On the **Program** doctype, two new fields — both hidden for ongoing programs — switch the flow on:

- **Students Can Request Graduation** (Check) — the master switch. When off, no CTA, no candidacy is computed, no Graduation Request can be filed for this program. Use this for programs handled entirely registrar-side.
- **Graduation Request Trigger** (Select, mandatory when the Check is on) — *when* the student becomes eligible to file:
  - **Enrolled in final courses** — the student becomes a candidate the moment their currently-enrolled courses, *if all passed*, would close out the program. Use when you want early visibility (start preparing the diploma, line up the ceremony) and trust the student not to file until they're confident.
  - **Passed final courses** — the student becomes a candidate only after final grades are in and the eligibility math is satisfied. Use when "no walk if you might fail your last class" is the policy.

> **Tip.** The two trigger modes use the same eligibility math. The difference is whether **in-progress** courses count toward the final tally. If you're not sure which to pick, **Passed final courses** is the conservative choice.

## How the student gets to the CTA

The system maintains a system-managed flag on each Program Enrollment called `grad_candidate`. It re-evaluates automatically whenever PE state changes — course enrollment, withdrawal, grade entry, or any registrar edit. The student does nothing to "activate" their CTA; it just appears once they meet the conditions.

`grad_candidate = 1` requires **all** of:

- The program's **Students Can Request Graduation** flag is on and **Graduation Request Trigger** is set.
- All mandatory program courses are at least *In Progress* (or *Completed*, depending on trigger mode).
- All mandatory courses on the student's active emphasis tracks are at least *In Progress* (or *Completed*).
- The credit total — completed plus in-progress (or just completed, depending on trigger mode) — meets the program's required credits.
- Every mandatory graduation requirement marked **Blocks Graduation Request** is `Fulfilled` or `Waived`.

If any blocker is outstanding, the candidacy stays at 0 even when the credit/course math would otherwise be true. This is by design — the school explicitly tagged that requirement as a hard prerequisite.

## What the student sees

On the **Program Audit** page (`/program-audit/<enrollment>`):

1. The eligibility banner now has three states:
   - **Eligible for Graduation** (green) — passed everything.
   - **Conditionally Eligible for Graduation** (blue) — enrolled in their final courses; will be eligible when those grades come in.
   - **Not Yet Eligible for Graduation** (amber) — the default starting state.

2. Below the banner, when the student is a candidate, the **Graduation Request CTA**:
   - **Eligible** path: *"You meet the program's graduation request criteria. File a request to begin the approval process."*
   - **Conditionally Eligible** path: *"You may file a request to begin the graduation process. You must pass the courses you are currently in for it to be accepted."*

3. Below the CTA, a **Pending Payments** table groups every unpaid Sales Invoice for this enrollment by payer. This includes the student's own invoices *and* invoices owed by other payers (sponsoring church, scholarship donors, denominational fund). The student can only pay their own on the Fees page; this table tells everyone the full picture.

   Most schools require all balances to be cleared before graduation. The financial-review step (below) is the gate, but seeing it surfaced here lets the student chase down their other payers early.

## What happens when they file

Clicking **Request Graduation** does three things atomically:

1. Creates the **Graduation Request** record bound to this Program Enrollment.
2. Submits it via the workflow.
3. Generates a **Sales Invoice** for the program's Graduation Request fee, addressed to whichever payer is configured on the enrollment for the `Graduation Request` event. (Multiple payers split the fee proportionally, exactly like Course Enrollment fees.)

The student lands back on the audit page; the CTA card now shows **Awaiting Payment** with the paid percentage and a link to the invoice.

If the program is marked **Free**, no invoice is generated and the request lands directly in `Academic Review`.

## The workflow

```
Draft  →  Awaiting Payment  →  Academic Review  →  Financial Review  →  Approved
            (free skips →                ↗)                                    ↓
                                                                         Cancelled  (any state)
```

| State | Doc status | Who can edit | What it means |
| --- | --- | --- | --- |
| **Draft** | 0 | Academics User | Being prepared; usually transient (the system creates and submits in one step from the audit page). |
| **Awaiting Payment** | 1 | Academics User | Invoice generated; student needs to pay. Auto-advances on full payment. |
| **Academic Review** | 1 | Academics User | Payment in (or program is free). Academics confirm grades posted, blockers cleared, graduation requirements satisfied. |
| **Financial Review** | 1 | Accounts User | Bursar verifies no other outstanding balances on the enrollment. |
| **Approved** | 1 | Seminary Manager | Final stamp. Student is cleared for graduation. |
| **Cancelled** | 2 | Seminary Manager | Withdrawn from the process. |

### Awaiting Payment → Academic Review (auto)

When a Payment Entry posts against the GR's invoice and `paid_percent ≥ 100`, the system advances the workflow automatically. No manual step required for the common case.

If a school operates with partial-payment policies, an Academics User can manually click **Mark as Paid** to advance the request before full payment posts.

### Academic Review → Financial Review (manual)

Academics User clicks **Send for Financial Review** when satisfied that:
- Final grades are posted on every course on the enrollment.
- Every mandatory active graduation requirement is `Fulfilled` or `Waived`.
- No outstanding academic decisions (incomplete grades, pending appeals).

The Graduation Request desk form shows two HTML snapshot tables to make this review fast:

- **Graduation Requirements** — every SGR row with status, mandatory flag, *Blocks Request* flag, due date, and a link to the linked document (Recommendation Letter, Culminating Project, etc.). Open any one with a click.
- **Pending Payments** — every unpaid invoice on the enrollment, grouped by payer, with desk links to each Sales Invoice.

### Financial Review → Approved (manual)

Accounts User clicks **Approve Financially** when satisfied that:
- The graduation fee is paid in full.
- No other outstanding balances on the enrollment (or the school has explicitly accepted them).
- Refunds, scholarship reconciliations, and any holds are cleared.

This is the final approval. The Graduation Request lands at `Approved`.

> **Heads up — `Approved` does not stamp the PE as "graduated".** That's a separate registrar action (in a future release, a workflow on the PE itself). `Approved` means the request is complete; the registrar then runs the actual graduation processing (transcript stamping, alumni record creation) outside this module.

## Cancellation

Two paths:

1. **Manual** — Academics or Seminary Manager clicks Cancel on the GR form. Any **fully unpaid** linked Sales Invoices are cancelled too. **Partially paid** invoices are left in place — the registrar handles refund decisions explicitly (use ERPNext's standard Credit Note flow if needed).

2. **Cascade from PE withdrawal** — when a registrar deactivates a Program Enrollment (`pgmenrol_active = 0`), every active GR on that PE is automatically cancelled. **The fee is non-refundable** in this path — invoices are left intact. This is the default policy because most schools treat the graduation fee as a non-refundable service fee, and a withdrawing student isn't graduating anyway.

## Day-to-day for staff

### Where to look

- **Per-student** — open the Program Enrollment in Desk; the GR (if any) is visible in the Connections sidebar.
- **Queue** — the **Graduation Request** list view, filtered to `workflow_state` in `("Academic Review", "Financial Review")`, is the registrar's daily queue.
- **Cohort** — same list filtered by `expected_graduation_date` within a term gives you the graduating cohort for ceremony planning.

### Reviewing a request

1. Open the Graduation Request from the list view.
2. Scan the **Graduation Requirements** snapshot — anything not `Fulfilled` or `Waived`?
3. Scan the **Pending Payments** snapshot — total unpaid is the bursar's concern.
4. Click **Send for Financial Review** (if Academics) or **Approve Financially** (if Accounts), or **Cancel** if the request needs to come back to the student.

### When the student doesn't see the CTA

If a student tells you they "should be able to graduate" but don't see the button, walk through the candidacy checks:

1. Is `Students Can Request Graduation` checked on the Program?
2. Is `Graduation Request Trigger` set?
3. Are all mandatory program + emphasis courses at least In Progress (Enrolled-mode) or Completed (Passed-mode)?
4. Do the credit totals add up?
5. Are there any **mandatory** graduation requirements with `Blocks Graduation Request` checked that are still `Not Started`, `In Progress`, or `Submitted`?

The fifth is the most common silent blocker. Open the Program Enrollment and look at the Student Graduation Requirements table — anything with the **Blocks Request** flag set must be `Fulfilled` or `Waived` first.

> **Tip — bench helper.** If you change a program's trigger or fix a hard-to-debug case for one student, the system re-evaluates candidacy automatically on the next PE-related save. To force a recompute across an entire program, run:
>
> ```
> bench --site <site> execute seminary.seminary.graduation_candidate.recompute_for_program --kwargs "{'program': 'MDiv'}"
> ```

## Worked examples

### Example 1 — Standard for-fee MDiv graduation

1. **Configure the program.** Open the *MDiv* program. Tick **Students Can Request Graduation**. Set **Graduation Request Trigger** to *Passed final courses* (the conservative default).
2. **Configure the fee payer.** On each Program Enrollment, open the *Payers Fee Category PE* table and add a row with `Event = Graduation Request`, the appropriate Fee Category, payer, and percentage.
3. The student finishes their last term. Once final grades are posted, the system flips `grad_candidate` to 1.
4. The student sees **Eligible for Graduation** + **Request Graduation** button on the audit page. They click it.
5. The system creates the GR + Sales Invoice. The student pays. GR auto-advances to **Academic Review**.
6. Academics opens the GR, reviews the snapshot tables, clicks **Send for Financial Review**.
7. The Bursar verifies no other unpaid balances, clicks **Approve Financially**. GR lands at **Approved**.

### Example 2 — Free program, request as soon as enrolled in final courses

1. Configure the *Online Certificate* program: tick **Free Program**, tick **Students Can Request Graduation**, set trigger to *Enrolled in final courses*.
2. The student enrolls in their last courses for the term.
3. The audit page shows **Conditionally Eligible** banner + the CTA with the "you must pass" caveat.
4. The student files. The GR skips Awaiting Payment and lands directly in **Academic Review**.
5. Academics waits until grades come in. If everything passed, **Send for Financial Review**. If a course was failed, **Cancel** — the student can re-file once they make up the requirement.

### Example 3 — Hard prerequisite: thesis must be approved first

1. Open the **Senior Project** Library item (Linked Document, target *Culminating Project*). Tick **Mandatory**, tick **Blocks Graduation Request**.
2. The student finishes coursework but the thesis is still in revision. Even though the credit math is satisfied, `grad_candidate` stays at 0 — the audit page shows **Conditionally Eligible** but no CTA appears.
3. The student's advisor approves the thesis. The Culminating Project workflow lands on `Completed`. The SGR row flips to `Fulfilled`. The candidacy evaluator runs, sees the blocker is now satisfied, and flips `grad_candidate` to 1.
4. The student refreshes the audit page. The CTA is now visible. They file.

### Example 4 — Sponsoring church behind on payments

1. The student finishes coursework. They file the Graduation Request and pay the graduation fee. GR advances to Academic Review.
2. Academics reviews requirements; everything is in order. Sends to Financial Review.
3. The Bursar opens the GR, scans the **Pending Payments** snapshot. Sees that the sponsoring church owes $4,200 across three monthly invoices.
4. The Bursar holds Approval, contacts the church. Once paid, **Approve Financially**. (Alternatively, if the school has a written agreement with the church, the Bursar may approve and chase the balance separately — that's an institutional policy decision the system doesn't enforce.)

## Quick reference

| If you want to... | Do this |
| --- | --- |
| Enable Graduation Requests on a program | Program → tick *Students Can Request Graduation* + pick a trigger |
| Disable Graduation Requests for a specific program | Untick *Students Can Request Graduation* on that Program |
| Make a graduation requirement a hard prerequisite to even filing | Library → tick *Blocks Graduation Request* (only visible if Mandatory) |
| Force a candidacy recompute for one student | Save the Program Enrollment (any field) — recompute fires on `on_update_after_submit` |
| Force a recompute for an entire program | `bench execute seminary.seminary.graduation_candidate.recompute_for_program --kwargs "{'program': 'XYZ'}"` |
| See the registrar review queue | Graduation Request list, filter `workflow_state in ("Academic Review", "Financial Review")` |
| Cancel a request without refunding | Click Cancel on the GR (partially paid invoices are left in place) |
| Confirm graduation finished | Lands at `Approved` workflow state — actual graduation processing (transcript, alumni record) is a separate registrar step |

## Related

- [Graduation Requirements](graduation-requirements.md) — the policy + Library + SGR layers that the candidacy evaluator reads from.
- [Enrollment](enrollment.md) — Program Enrollment is where `grad_candidate`, the policy snapshot, and the fee payer config live.
- [Withdrawal](withdrawal.md) — withdrawing a PE auto-cancels any active Graduation Request.
- [User Roles](../administration/user-roles.md) — Academics User vs Accounts User vs Seminary Manager (review steps).
