# 030 — Program enrollment status lifecycle spine

**Date:** 2026-06-01
**Status:** Accepted

## Context

`Program Enrollment` collapsed three distinct life events — voluntary
withdrawal, temporary leave of absence, and involuntary dismissal — onto a
single binary `pgmenrol_active` flag with no status vocabulary, no history, and
no reason. Program withdrawal was only a side-effect of a Course Withdrawal
Request with scope `Full Program Withdrawal`. We needed a first-class status
without the weight of a Frappe Workflow (the doctype is already submittable, and
a workflow would collide with submit/`allow_on_submit` semantics).

## Decision

A status **spine**: a `status` Select (Active / Leave of Absence / Withdrawn /
Dismissed / Graduated / Transferred) plus a `status_history` child table, with
**one mutation point** — `set_program_status()` in
`seminary/seminary/program_status.py`. It records history, sets `status`, and
keeps `pgmenrol_active` as a **derived mirror = 1 only while Active** so every
existing active-enrollment query and the CEI `program_ce` filter keep working.

Billing suspension is a **separate** `billing_suspended` flag (ADR 033), not an
overload of `pgmenrol_active`.

Because the spine writes via `db_set` (submitted-doc safe) it bypasses
`on_update_after_submit`; therefore `set_program_status` runs the
graduation-request cascade itself on terminal transitions. The controller hook
remains only as a manual-toggle fallback. Existing rows are backfilled
(`backfill_pe_status`).

## Consequences

Easier: uniform transitions, audit trail, LOA/dismissal as first-class states.
Harder: every status change must go through the spine — direct `pgmenrol_active`
writes are now an anti-pattern. Open: a future Graduated transition could be
wired from the alumni flow.
