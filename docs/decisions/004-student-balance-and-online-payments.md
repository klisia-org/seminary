# 004 — Student Balance and Online Payments

**Date:** 2026-04-17
**Status:** Accepted

## Context

Students enroll in 3-4 courses per term, each auto-generating a Sales Invoice (one per payer per fee category via Course Enrollment Individual). Requiring students to pay each invoice individually is poor UX and may trigger fraud detection at payment gateways. Course withdrawals generate credit notes against individual invoices, and the financial picture must remain coherent across enrollments, payments, and refunds.

ERPNext's Payment Request is 1:1 with a reference document, so it cannot natively aggregate multiple invoices into a single gateway transaction. Payment Entry, however, supports multiple invoice references in its child table.

## Decision

### Student Balance doctype (wrapper/aggregator)

A regular (non-submittable) doctype with Open/Closed status. One open Student Balance exists per student at all times:

- **Created** on Student creation via `after_insert` hook; pre-populated with company/currency from Seminary Settings.
- **Auto-populated** via `Sales Invoice.on_submit` hook — every invoice (and credit note) for the student is appended to the open balance's child table.
- **Credit note cascade** via `Sales Invoice.on_update_after_submit` — when a withdrawal credit note reduces an invoice's outstanding, the balance refreshes automatically.
- **Closes on every payment** (full or partial). A new open balance is created carrying forward any rows with remaining outstanding. This preserves the 1:1 Payment Request relationship and creates an audit trail via a `previous_balance` link chain.
- **Payment allocation** follows due date order (earliest first) for v1.

### Payment flow

- **Online (portal):** Student clicks "Pay Full Balance" or "Pay Partial" on Fees.vue. Backend creates a Payment Request against the Student Balance, student is redirected to the gateway (Stripe). On success, `on_payment_authorized` creates a Payment Entry with one reference row per allocated Sales Invoice.
- **Desk:** Registrar clicks "Record Full/Partial Payment" on the Student Balance form, selects Mode of Payment, and a Payment Entry is created directly — same allocation logic, no gateway involved.

### Payment Request override

`SeminaryPaymentRequest` (via `override_doctype_class` in hooks) handles `reference_doctype == "Student Balance"` for three methods: `get_payment_url`, `on_payment_authorized`, and `create_payment_entry`. All other reference types fall through to default ERPNext behavior.

### Seminary Settings integration

`portal_payment_enable` (Check) and `payment_gateway` (Link to Payment Gateway) control whether online payments are available. When enabled, the gateway field is mandatory. A whitelisted `check_payments_app()` validates that the Frappe Payments app is installed on the site (not just the bench) before exposing gateway configuration.

### Permission model

Students can only see their own Student Balance (permission query on `student` field, same pattern as Sales Invoice). Payment Entry creation bypasses permission checks by pre-populating account currency/type fields on the PE — avoiding both the need for student users to have Payment Entry read access and the security risk of elevating user privileges mid-request.

## Alternatives considered

- **Consolidated invoice** (one invoice per term instead of per course): Rejected because the withdrawal credit note system depends on per-course invoices (finds them via remarks), multi-payer splits create multiple invoices regardless, and enrollment timing is asynchronous.
- **One Payment Request per invoice** (pay individually or chain them): Rejected because multiple small charges trigger gateway fraud detection and the UX is poor.
- **Submittable doctype with Draft/Submitted/Cancelled workflow:** Rejected because adding child rows (new invoices) to a submitted doc requires `ignore_validate_update_after_submit` flags, and the Open/Closed status model is simpler for a living document.

## Consequences

- Per-course invoices and the existing withdrawal/credit note flow are untouched.
- Registrar sees all open balances at a glance; students see a single financial summary on Fees.vue.
- Every payment creates a closed Student Balance with a `previous_balance` chain — full audit trail.
- The Stripe integration uses Frappe Payments' synchronous charge model (no webhooks needed); other gateways supported by the Payments app can be configured without code changes.
- Existing students require a one-time migration script (`seminary.seminary.patches.create_student_balances`) to create their initial Student Balance and populate it with outstanding invoices.
