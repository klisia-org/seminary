# 063 — Financial-backend boundary & bridge apps (oikonomos, future QBO)

**Date:** 2026-06-26
**Status:** Implemented 2026-06-26 (seminary decoupled from ERPNext; `oikonomos` is the first backend)

## Context

Seminary started life requiring **ERPNext** (`required_apps = ["erpnext"]`): billing, payments,
scholarships and the Customer/Company/Holiday plumbing were woven straight into academic controllers,
`api.py`, the scheduler, and fixtures. A director asked for **Frappe-only deployability** — a seminary
that installs and runs with no accounting engine — and, looking ahead, the option to back billing with
something other than ERPNext (e.g. a **QuickBooks Online** bridge with its *own* pricing doctypes).

The only viable direction is to **invert the dependency**: `required_apps` / install order is one-way,
so seminary importing a billing app would be a cycle. Seminary must become a pure academic core that
*defines* extension points; a separate bridge app *requires* seminary + the accounting engine and
*consumes* those points. This ADR records the boundary so the next bridge can be built quickly.

## Decision

### 1. The seam — `FinancialBackend` (seminary owns the interface)

`seminary/seminary/financial/backend.py` defines an ABC `FinancialBackend`, a `NullFinancialBackend`
(every method returns *free / empty / None*), and a resolver:

```python
def get_financial_backend() -> FinancialBackend:
    paths = frappe.get_hooks("seminary_financial_backend")
    return frappe.get_attr(paths[-1])() if paths else NullFinancialBackend()
```

A bridge registers `seminary_financial_backend = ["<app>.backend.MyBackend"]` in its hooks. Seminary
asks the backend for every financial fact ("how much of this CEI is paid?") and every financial side
effect ("raise the enrollment invoice", "payer snapshot active?"). With no bridge installed, the null
backend makes academic flows behave as if everything is free and fully paid — **that is the supported
Frappe-only deployment, not a degraded mode.** The interface deliberately passes plain data (no ERPNext
doctypes leak across it), so it could later be promoted to an HTTP/cross-site API unchanged.

Current methods (grow the interface as new call sites appear): `has_financials`,
`payment_status_for_cei` / `_for_graduation`, `generate_enrollment_invoice`,
`generate_program_enrollment_invoices`, `process_withdrawal_refunds`, `charge_readmission`,
`sync_enrollment_payers`, `set_enrollment_payers_active`, `student_scholarships`,
`available_scholarships`, `apply_for_scholarship`, `student_invoices`, `pe_unpaid_invoices`,
`unpaid_invoice_for_cei`, `graduation_request_invoices`, `application/invoice/student_balance/
partial_balance` payment-URL builders, `cei_invoices`, `company_country`, `company_holiday_dates`.

### 2. The bridge — `oikonomos` (the ERPNext implementation)

`oikonomos` declares `required_apps = ["seminary", "erpnext"]` (GPL v3; seminary is MIT). It **owns
every ERPNext-touching doctype, field, handler, report, page, scheduler task and fixture.** It calls
*into* seminary (legal — it requires it); seminary never imports it. Relocated doctypes: Fee Category,
Payers Fee Category PE (+ `pgm_enroll_payers`), the Scholarships family, Student Balance (+ child),
Instructor Log Payment, Trigger Fee Events, and **Program Fees** (inverted from the old
`Program.pgm_pgmfees` child table into a standalone doctype with a `program` Link back). ERPNext-linked
Seminary Settings fields, `Student.customer`/`customer_group`, and Sales Invoice custom fields are
oikonomos **custom fields** (re-injected on install/migrate; values survive). `seminary/seminary/
holidays.py` vendors public holidays (the `holidays` PyPI package) so attendance/leave never need
ERPNext's Holiday List.

### 3. The three integration patterns (how each coupling was cut)

1. **Emit** — billing reacts to academic docs via `doc_events` registered in the *bridge's* hooks.py.
   Seminary just `doc.submit()`s. Payment-driven advancement is the subtle case: oikonomos owns the
   **Sales Invoice / Payment Entry** handlers (`financial/cei_payment.py`, `financial/graduation.py`),
   traces a billing document back to its CEI / Graduation Request, and calls seminary's academic
   entrypoint (`cei_lifecycle.react_to_cei_payment`, `graduation_request_lifecycle.react_to_gr_payment`).
   **Seminary registers no Sales Invoice or Payment Entry doc_events.**
2. **Shim** — whitelisted methods the SPA / desk forms call by `seminary.seminary.*` path
   (`Fees.vue`, `Enrollment.vue`, `ProgramAudit.vue`, the applicant web form, the PE form) must keep
   their *name* in seminary, as a thin wrapper that delegates to the backend (null → empty). The real
   body lives in oikonomos (`financial/{invoice_queries,payment_urls,scholarship,payers,invoicing}.py`).
   Where the *only* caller is an oikonomos doctype's own JS (e.g. `get_program_fees` from the
   Scholarships form), the method moves fully to oikonomos and the JS is repointed — no shim.
3. **Hook dispatch** — for whole flows: `seminary_demo_installer` + `seminary_demo_cleanup` let
   oikonomos own the billing demo (catalog, Sales Invoices, Customers); billing automation and
   scholarship-retention review run from oikonomos's *own* `scheduler_events`, not `seminary.tasks.daily`.

### 4. Client-side gates

`frappe.boot.versions.oikonomos` (truthy iff installed) gates cross-doctype `depends_on` and desk JS
buttons; `has_oikonomos` (a Seminary Settings Check) gates same-doctype `depends_on`. Workflows with
auto-routed financial states force the free branch when `not has_financials()` (CEI
`require_pay_submit`/`percent_to_pay` = 0; Withdrawal `refund_due` = 0; GR `is_free` = 1).

## Building the next bridge (e.g. QBO)

A QuickBooks-Online bridge is **a second `FinancialBackend`, not a rewrite of seminary**:

1. `bench new-app oikonomos_qbo` (never hand-scaffold — see
   [feedback_bench_app_registration]); `required_apps = ["seminary"]` (+ whatever QBO SDK/payments app).
2. Implement `FinancialBackend` with QBO's own pricing/invoice doctypes. **Define your own doctypes for
   pricing — seminary names none of them.** Register `seminary_financial_backend`.
3. Subscribe to the academic `doc_events` you need (the *emit* seam) to push invoices to QBO, and have
   your invoice/payment webhooks call seminary's academic entrypoints (`react_to_cei_payment`,
   `react_to_gr_payment`) — the same way oikonomos's Sales Invoice / Payment Entry handlers do.
4. Provide the *shim* answers: implement the `student_invoices` / `*_payment_url` / scholarship / payer
   methods so the existing SPA shims light up unchanged. Provide `company_country` /
   `company_holiday_dates` (or return None/`set()` if not applicable).
5. Re-implement the *hook dispatch* handlers (`seminary_demo_installer`, `seminary_demo_cleanup`,
   `scheduler_events`) if you want a billing demo / automation.

Only one backend should be installed at a time (the resolver takes the last-registered hook). Nothing in
seminary's academic core changes.

**Hard rule:** seminary must never `import erpnext`, `import oikonomos`, or name a billing doctype
(`Sales Invoice`, `Payment Request`, `Payers Fee Category PE`, `Fee Category`, `Program Fees`, …). Verify
with `grep -rn "import erpnext\|from erpnext\|import oikonomos\|from oikonomos" seminary/` (must be empty)
and a doctype-literal sweep. The sole tolerated exceptions are two guarded historical migration patches
(`stash_scholarship_links`, `migrate_scholarships_to_awards`) that name oikonomos tables only in SQL
strings behind a table-exists guard.

## Consequences

- **Frappe-only seminary is a real deployment** (null backend → free academic flows), continuously
  verified by testing every change on both an integrated site and a seminary-only site before commit.
- The accounting engine is now a **swappable plug-in**: a QBO (or any) bridge is additive work behind a
  documented interface, with zero edits to seminary's academic core.
- Cost: financial behaviour is spread across an interface + a bridge, so a billing change can touch two
  apps (a backend method + its implementation); and the interface will keep growing as new academic call
  sites need a financial fact — that growth is expected, not a smell.
- Open: the SPA still *calls* the financial shims even on a Frappe-only site (they just return empty) —
  gating the financial **pages** client-side on oikonomos presence would avoid the round-trips (frontend
  change, deferred). Restoring the `stabilize-pot` pre-commit hook is also still pending.
