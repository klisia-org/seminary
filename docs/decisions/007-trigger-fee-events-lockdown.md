# 007 — Trigger Fee Events Lockdown

**Date:** 2026-04-21
**Status:** Accepted

## Context

`Trigger Fee Events` is a system doctype whose six records (`New Academic Year`, `Monthly`, `Program Enrollment`, `Course Enrollment`, `New Academic Term`, `Course Withdrawal`) are referenced by **exact name** throughout the Fee Category → invoicing pipeline. Fee Category's `fc_event` Link field and downstream handlers (e.g. `if self.fc_event != "Course Enrollment":`) match on the literal string, so a rename, delete, or accidental edit silently breaks invoice generation — the scheduler just stops firing the affected trigger, with no error surfaced.

The records are managed as fixtures ([seminary/fixtures/trigger_fee_events.json](../../seminary/fixtures/trigger_fee_events.json), declared in [hooks.py](../../seminary/hooks.py) `fixtures`): `bench migrate` is the intended path for adding or changing triggers. Nothing in normal operation requires a human to edit these records at runtime.

## Decision

**Lock the doctype down purely via configuration — no Python lifecycle guards, no `has_permission` hook.** Two layers:

1. **Empty permissions** — `"permissions": []` in [trigger_fee_events.json](../../seminary/seminary/doctype/trigger_fee_events/trigger_fee_events.json). Frappe defaults to deny-all for every non-Administrator user across Desk UI, REST (`/api/resource/...`), RPC (`frappe.client.*`), Data Import, Bulk Update, and Report Builder export.
2. **Hidden from all workspaces.** The doctype does not appear in any workspace link, global search, or quick-create dropdown, so even users with `Administrator` have no UI discovery path.

Fee Category's `fc_event` Link field continues to work because link-picker search is read-only and goes through a separate code path that doesn't require full list permission.

### Tests performed (2026-04-21, logged in as `Administrator`)

| Attempt | Result |
|---|---|
| Desk search / workspace navigation | Doctype not discoverable |
| Direct URL `/app/trigger-fee-events` | "Page not found" |
| REST `PATCH /api/resource/Trigger Fee Events/Monthly` | Rejected |
| `bench --site <site> execute frappe.rename_doc --args "['Trigger Fee Events','Monthly','X']"` | "Trigger Fee Events not allowed to be renamed" |
| Fee Category save with `fc_event = "Monthly"` | Succeeds (link resolution unaffected) |

## Alternatives considered

- **Document-lifecycle guards** (`validate`/`on_trash`/`before_rename` raising `PermissionError` unless `frappe.flags.in_fixtures/in_migrate`): Rejected. Would block the literal `Administrator` user too, but this is an open-source project — making the doctype harder to inspect or repair for contributors/self-hosters is a poor tradeoff against an already-mitigated risk.
- **`read_only: 1` + explicit `allow_copy/allow_rename/allow_import: 0` in JSON**: Rejected as unnecessary noise given the empty permissions array already covers every user-facing path we tested.
- **Removing from fixtures and managing via patch only**: Rejected. Fixture sync is the ergonomic management path; patches add ceremony without adding safety.

## Consequences

**Easier:**
- No app code to maintain for the lockdown — it's declarative.
- Adding or renaming a trigger stays simple: edit the fixture JSON, run `bench migrate`, ship. Any code that matches on the string value must be updated in the same commit.
- Contributors and self-hosters can still inspect or repair the records via `bench console` or direct SQL when genuinely needed.

**Residual risks (accepted):**

- **`developer_mode = 1`** — In developer mode Frappe exposes DocType editing in the UI and relaxes some checks. A `System Manager` on a dev instance could re-open the doctype, add a permission row, migrate it back in, and then edit records. Mitigation: never enable `developer_mode` in production; this is a general Frappe invariant, not specific to this doctype.
- **The literal `Administrator` user bypasses `permissions: []`** by Frappe design. Our tests show the current UI/REST/RPC paths still reject writes because there is no way to reach the form or API endpoint without the permission row existing — but a future Frappe change that exposes a new generic write path could undo this. Mitigation: re-run the test matrix above after major Frappe upgrades.
- **Bench shell / raw SQL** (`frappe.db.set_value`, direct MariaDB) bypasses all Frappe permission logic. Out of scope: anyone with shell access on the server can edit any table in any app.
- **A malicious installed app** could add a Custom DocPerm fixture granting itself write access. Out of scope: standard app-install review.

## Open questions

- Should a test in CI assert that `frappe.get_meta("Trigger Fee Events").permissions == []`, to catch accidental restoration? Deferred — no CI infra for Frappe-level assertions yet.
