# 033 — Program leave financials and student holds

**Date:** 2026-06-01
**Status:** Accepted

## Context

Two gaps remained around leave and re-entry. (1) Financial: recurring charges
(Monthly / NAT / NAY) only bill active enrollments, so any leave that set
`pgmenrol_active=0` stopped *all* billing immediately — but seminaries want short
leaves to keep billing and only longer leaves to suspend, plus an optional
readmission fee. (2) Re-enrollment: the Student doctype had no standing/holds, so
a dismissed student could freely re-enroll.

## Decision

**Billing suspension is orthogonal to active-ness.** A separate
`billing_suspended` flag on Program Enrollment, driven by a **Program Level**
policy: `loa_billing_suspension_days` (threshold), and per-event `suspend_monthly`
/ `suspend_nat` / `suspend_nay`. The three generators in `api.py` switch their
gate from `pgmenrol_active=1` to *status-not-terminal* AND
`NOT (billing_suspended AND <per-event flag>)`. The flag is set when a leave's
known length exceeds the threshold, and a daily `reconcile_loa_billing` trips it
for open-ended/extended leaves. Default threshold `0` = never suspend, so
behavior is unchanged until configured.

**Readmission fee reuses the billing pipeline:** a new "Readmission" Trigger Fee
Event configured as a Program Fee; `return_from_leave` calls
`generate_readmission_invoice` when the Program Level enables it.

**Student holds = registration holds.** A `Student Hold` child table + derived
`student_standing`. A disciplinary dismissal writes an active Disciplinary hold;
`Program Enrollment.validate` blocks a *new* enrollment when an active
`blocks_reenrollment` hold exists, **overridable** by Registrar / Seminary
Manager (surfaced as a warning). Withdrawal/transfer set standing
informationally but do not block.

## Consequences

Easier: nuanced leave billing, readmission charging with no new invoice code,
enforced re-enrollment integrity. Harder: policy now lives on Program Level
(not alongside other fee config); the per-event gate is the load-bearing edit and
must be kept in sync across all three generators.
