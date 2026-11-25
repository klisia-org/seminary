# 113 — Application fee waivers and discounts

**Date:** 2026-11-24
**Status:** Accepted 2026-11-24
**Delivers:** SIS-ADM-02 (Yes)
**Related:** 019 (application fees), 112 (complete, then In Review)

## Context

The application fee is charged when someone applies, and the applicant can pay online (019). Schools
also waive it: early applicants, alumni, partner churches, hardship. Today a waiver means a staff
member crediting the charge by hand, or refunding after the applicant has paid. Nothing records
why. Reviewers check that a waiver needs no refund and leaves a record. Seminary owns admissions,
not billing, so it decides the discount and asks the installed financial app to apply it.

## Decision

1. **One discount, a percent.** Each application carries `fee_discount_percent` and
   `fee_discount_source` (*Window*, *Code* or *Request*), both read-only. 100 means no fee. When
   several sources apply, the largest discount wins. Discounts don't add up.
2. **Windows on the Program.** A child table `Application Fee Window` holds a label (for example
   *Early application*), from and to dates, and a discount percent. The application's creation
   date picks the window. Overlapping windows are rejected on save. The program page shows the
   active window next to Apply ("No application fee until 15 January").
3. **Codes.** `Application Fee Code` holds the code (unique, case-insensitive), a discount
   percent, the programs it covers (blank means all), valid from and to dates, an optional
   maximum number of uses, and Active. Uses are counted from the applications that carry the code,
   never typed in. The applicant enters the code on the form. An unknown, expired or used-up code
   fails validation with a plain message, so the applicant can fix it before applying.
4. **Discount at charge time.** `admissions.application_fee_discount(applicant)` returns the
   percent and source. The financial backend reads it when it raises the fee. At 100 it raises
   no charge.
5. **Requests.** A program accepts them only when `Program.allow_fee_waiver_requests` is set. It
   is off by default, so a school that doesn't waive fees gets no requests. When it is set, the
   form offers *Request a fee waiver* with a required reason. While the request
   is open, the application isn't complete (112 §2), and the payment page says the request is
   under review instead of showing the pay link. The chair of the program's admissions unit
   (112 §1a), a Registrar or a Seminary Manager approves (full, or a partial percent) or declines
   on the applicant record. The decision records who decided,
   when and why. On approval the backend's new `waive_application_fee(applicant, percent,
   reason)` credits the open charge. A fee that is already paid can't be waived, because that
   would be a refund. The applicant is told the outcome through `comms.send`. If the
   request is declined, the message includes the pay link.
6. **Settlement starts review.** When an applicant's charge is paid or credited, the financial
   app calls `admissions.on_fee_settled(applicant)`, so review starts at once. The daily sweep
   stays as the backstop.

## Consequences

- A waiver never needs a refund. A window or code removes the fee before it is charged, and an
  approved request credits it before it is paid.
- Every discount names its source, and approved requests name who approved them, so a school can
  report waivers by reason.
- Without a financial app there is no fee, so none of this shows.
- A fee paid before a waiver is approved is still refunded by hand, outside this flow.
- A code is a shared secret. Anyone who has it can use it until its uses run out.

**Rejected:**
- Scholarship grants for waivers. A grant belongs to a Program Enrollment, and an applicant has
  none yet.
- Adding discounts together. Window plus code plus request could reach more than 100, and the
  school couldn't tell which one it meant to give.
