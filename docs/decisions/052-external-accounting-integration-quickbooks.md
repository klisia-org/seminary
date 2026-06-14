# 052 — External accounting integration (QuickBooks Online)

**Date:** 2026-06-13
**Status:** Accepted — implementation deferred

## Context

A seminary director may want to run invoices, banking, and accounting in a separate system
(QuickBooks), keeping only prices in ERPNext. But Seminary is **not** a thin pricing layer on top of
ERPNext. Invoices are generated automatically from enrollment events (`billing.py`, `api.py`);
student progression gates on payment — Sales Invoice / Payment Entry hooks advance Course Enrollment
Individuals and the graduation-request lifecycle (`hooks.py`); `Student Balance` powers the portal
"Pay" button; and **multi-payer splits per fee** (`payers_fee_category_pe/`), **scholarship
forgiveness invoices**, two-phase credit/cash allocation, and cost-center accounting have no native
QuickBooks equivalent. `required_apps = ["erpnext"]`. So "invoices live only in QuickBooks, ERPNext
just holds prices" would require re-architecting invoice generation and syncing payment status back
to drive gating — losing those features. This ADR fixes our posture for when a school raises it.

## Decision

A three-step posture.

1. **Persuade first.** The default answer is to show that ERPNext already does most of what a school
   would pay QuickBooks Online (QBO) to do: AR, invoicing, multi-payer billing, scholarships, payment
   terms, cost centers, statements, and payroll (HRMS). This system is rarely changed once chosen, so
   most schools do not actually need QBO once they see this.

2. **If still wanted, build a *native* integration** (not an iPaaS) — matching the existing
   `seminary/seminary/integrations/` adapter pattern (`client.py`, `frappe.enqueue`, Integration
   Request logging). ERPNext stays the **source of truth and billing engine** (AR sub-ledger); QBO
   becomes the **book of record**. One-way push ERPNext → QBO: Customer→Customer, Fee Category
   Item→Item, Sales Invoice→Invoice, Payment Entry→Payment, return SI / scholarship forgiveness→Credit
   Memo, Income Account / Cost Center→Account / Class. Payments are captured in ERPNext first (portal +
   registrar), then pushed; the accountant reconciles the bank feed against synced records — preserving
   gating. Idempotent upserts via a stored `quickbooks_id` on each pushed doc (mirrors the
   `seminary_trigger` idempotency design).

3. **QuickBooks Online only — never QuickBooks Desktop.** QBO has a clean REST API (v3, OAuth2);
   Desktop integrates only via the Web Connector (qbXML/SOAP) or a paid bridge. Migrating a school
   from QB Desktop to QBO is easier and is *the school's* responsibility — we will not absorb
   Desktop's integration cost. Not to be confused with ERPNext's built-in "QuickBooks Migrator,"
   which is a one-time import *from* QBO *into* ERPNext (wrong direction), not a sync.

## Consequences

Easier: ERPNext keeps all billing logic and domain features; a clean OAuth2 REST integration when
needed; the persuade-first posture means we rarely build it. Harder: each pushed doctype needs a
`quickbooks_id` custom field and an enqueue-on-submit path, and a nightly job should flag any doc
lacking one; account/class mapping is configured per install. Constraint: Desktop is explicitly
unsupported. Open: detail level (per-invoice mirror vs periodic GL-summary journal push) is decided
per engagement; whether to also stamp QBO ids on Customer/Item for full upsert.
