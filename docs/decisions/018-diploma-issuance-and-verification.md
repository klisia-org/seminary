# 018 — Diploma Issuance and Verification

**Date:** 2026-05-04
**Status:** Accepted

## Context

ADR 017 ended the Graduation Request flow at the **Approved** state. A request that's been academically and financially cleared is *the school's decision to graduate the student*, but it isn't the credential — it's the paperwork that authorizes the credential. Real seminaries hand the student something printable: a diploma, with a serial, a date, and ideally a way for a third party (employer, another school, a denominational body) to confirm authenticity.

Three concerns shaped the design:

1. **Name at graduation can drift from the Student record.** Students who marry between filing and approval want the new legal name on the diploma. Students who never told us about a legal-name change want the registrar to correct it. The Student record may be wrong, or right but stale, or right but irrelevant if the student's preferred legal name diverges from the system-of-record. The diploma must capture *the name at the moment of issuance* and not silently track the Student record afterward.
2. **Pronunciation matters at ceremonies.** Whoever reads names at commencement needs phonetic spelling. This is student-level data — the pronunciation of "Hyacinthe N'Diaye" doesn't change because she enrolled in a second program — but the snapshot on the diploma should still be taken at issuance.
3. **Verification is a future-page concern, but the URL identifier has to be designed up front.** A diploma serial like `DIP-2026-0001` is great for humans and terrible for verification URLs: anyone with one diploma can enumerate the rest. Whatever opaque ID the future verification page reads needs to exist on day one, queryable and indexed, so we never have to migrate it in.

A first proposal was to print the Graduation Request directly with a custom format. We rejected it: the request is the *application*, the diploma is the *credential*. They have different audiences (registrar vs. student / outside world), different lifecycles (you cancel a request; you revoke a diploma), different identifiers (a GR name leaks queue position; a diploma needs an opaque public ID). Conflating them locks us out of the verification page and produces awkward UX where a printed "diploma" carries language like "this graduation request has been approved."

## Decision

### Separate `Diploma` doctype, auto-issued on Approved

A new submittable=No doctype `Diploma`, one-to-one with Graduation Request via a `unique` Link field. Issuance is automatic: when the Graduation Request workflow reaches **Approved**, [`GraduationRequest.on_update_after_submit`](../../seminary/seminary/doctype/graduation_request/graduation_request.py) calls `_issue_diploma` which inserts the row.

Idempotency has two layers:

- A `frappe.db.exists("Diploma", {"graduation_request": self.name})` short-circuit before insert.
- The unique constraint on `Diploma.graduation_request` itself, which catches any race the short-circuit misses.

This depends on the GR workflow transitioning into Approved via `apply_workflow` so `on_update_after_submit` actually fires. ADR 013 covers the system-driven exception (`db.set_value` on `workflow_state` skips controller hooks) — the GR flow's Approved transition is a user-clicked button, so the standard path is in effect.

### Two identifiers: opaque hash `name`, human serial `diploma_serial`

```
name             autoname=hash         opaque, unguessable, becomes the verification URL slug
diploma_serial   DIP-YYYY-####        human-readable, printed and used in correspondence
verification_hash                      mirror of name, indexed, queryable
```

`name` is what the future public verification page will read against — `/diploma/<hash>` resolves cleanly because hashes don't collide and don't leak position. `diploma_serial` is what registrars and students actually quote ("my diploma is DIP-2026-0042"). `verification_hash` exists because `name` is awkward to filter on with indexed lookups and we want the verification page to do `frappe.db.get_value("Diploma", {"verification_hash": hash})` against a real index, not against `tabDiploma.name`.

The serial increments per-year (`_next_serial`); year boundary resets to `0001`. Concurrent issuance racing for the same serial number is a non-concern at seminary scale (low single-digit issuances per minute at peak).

### Name capture at request time, locked at review

Two new `allow_on_submit=1` fields on Graduation Request:

- `legal_name_at_graduation` (Data, **required**) — collected up front from the student via the audit-page dialog. Defaults to `Student.student_name` but is editable.
- `phonetic_name_snapshot` (Data, optional) — `fetch_from=student.phonetic_name`, `fetch_if_empty=1`. Editable.

Editing rules: the student can revise both names freely while the GR is in Draft / Awaiting Payment. Once the workflow enters **Academic Review** (and through Financial Review and Approved), the fields lock for the student — only Academics User / Seminary Manager / System Manager can edit, for typo correction. The validator `_guard_name_edits_after_review` enforces this; it short-circuits when `is_new()` and only fires when one of the two fields actually changed.

Snapshotting to the *Graduation Request* and then again to the *Diploma* (the diploma stores `legal_name` and `phonetic_name` directly) is deliberate: a Student record updated post-graduation must not retroactively rewrite the diploma. The diploma is frozen at issuance.

### `Student.phonetic_name`

New optional `Data` field on Student. Student-level because:

- Pronunciation doesn't change between programs. A student who graduates a Bachelor's and later a Master's should not re-enter their phonetic spelling on each request.
- Audit-page dialog pre-fills from this field; if the student edits it in the dialog, [`create_graduation_request`](../../seminary/seminary/api.py) writes the corrected value back to the Student record.

The diploma's `phonetic_name` is still its own column — same snapshot rationale as legal name.

### Revoke, don't delete

When a Graduation Request is cancelled (registrar-driven or PE-withdrawal cascade per ADR 017), the linked Diploma is **not deleted**. Instead, [`_revoke_diploma_if_issued`](../../seminary/seminary/doctype/graduation_request/graduation_request.py) flips:

```
revoked = 1
revoked_on = today()
revocation_reason = "Graduation Request cancelled" [+ " (cascade from PE withdrawal)"]
```

The verification hash stays addressable. The future verification page should report `REVOKED: <reason>`, not 404. A 404 looks like a typo or transient outage; the truthful answer is "this credential was issued and later revoked." Deletion also loses the audit trail of *who was once issued what, when, and why it was reversed*.

The print format renders a red **REVOKED** banner if `doc.revoked` is set, so a stale printed diploma carries the truth too if it gets reprinted.

### Permission model

```
System Manager / Seminary Manager   full
Academics User                      create + read + write (no delete — see below)
Student                             read-only, scoped to own diplomas
```

Student scoping uses `permission_query_conditions` + `has_permission` (registered in [`hooks.py`](../../seminary/hooks.py)) keyed off `Student.student_email_id == frappe.session.user`. A user with no Student record gets `1=0` — strict deny.

Academics User keeps `create=1` as an emergency-override path: if auto-issuance ever fails (corrupted state, partial fixture migration, manual recovery), the registrar can hand-write a Diploma. The supported path is auto-issue; manual creation is the safety valve.

Delete is restricted to System Manager / Seminary Manager only. The revoke-don't-delete decision means delete is essentially never the right action; we keep the capability for genuine administrative cleanup (test data, duplicate from a botched migration), gated to roles that already have schema-level powers.

### Print format

A standard Jinja print format `Seminary Diploma`, registered as a fixture and wired in as `Diploma.default_print_format` at the DocType level so the Desk Print dialog auto-selects it. The default format is intentionally generic — school name pulled from `Seminary Settings.company`, "President" / "Registrar" signature lines without baked-in names, Garamond-family serif, double border, landscape orientation via embedded `@page { size: letter landscape; }`. Per-installation override: a school creates a custom Print Format scoped to Diploma and either edits `Diploma.default_print_format` or installs a Property Setter for it.

A per-row print-format Link field on Diploma was considered and rejected. Frappe's print preview reads `DocType.default_print_format` (or the user's last-used format), not arbitrary doc fields — so a per-row Link would be inert decoration that misleads about its effect. The DocType-level default is the supported override surface, and per-row overrides are not a use case any school has asked for.

The fixture filter in [`hooks.py`](../../seminary/hooks.py) was expanded from a single-name match (`Seminary Sales Invoice`) to an `in` clause (`["Seminary Sales Invoice", "Seminary Diploma"]`) so future scoped print formats just append to the list.

## Why not put printing on the Graduation Request?

The GR is the application; the diploma is the credential. Printing the GR would either (a) leak request-flow language onto the credential ("approved on…", "fee paid…"), or (b) require a print format that omits enough of the GR to look diploma-shaped, in which case the GR fields are doing double-duty as a poorly-modeled Diploma. Separating them lets each doctype carry exactly the fields its audience needs and gives the diploma its own lifecycle (revocation, re-issuance, future verification) without dragging the GR's workflow state into it.

## Why not generate the verification page now?

A public-facing endpoint has its own concerns: rate limiting, abuse mitigation, possibly captcha for high-volume scrapers, content-policy decisions about what the page displays (just "issued" / "revoked", or full program/date detail?). None of those are blocking the diploma issuance itself. By committing now to:

- opaque-hash `name`,
- a `verification_hash` field that is the canonical lookup key,
- a revocation block (`revoked` / `revoked_on` / `revocation_reason`),

…we lock in the schema the future page will read against. Building the page later is a route + template + rate-limit decision, not a migration.

## Why student-level phonetic name (and not GR-only)?

Pronunciation is a property of the person, not the program. A student who later enrolls in a second program shouldn't re-tell us how to say their name. The student-level field is the place this lives; the GR snapshot exists only so the diploma stays frozen if the student updates the field after graduating.

## Why auto-issue rather than manual registrar action?

Approval already represents the registrar's affirmative decision: the academic checks passed, the financial review cleared. Requiring a separate "now click to issue diploma" step adds a queue (approved-but-no-diploma) with no semantic meaning beyond what Approved already carries. Auto-issuance keeps the workflow honest: Approved means the credential exists.

The emergency-override `create` permission for Academics User exists for the case where the auto-issuance itself fails. Wiring is `on_update_after_submit`-driven (per the user-confirmed working state) and depends on the workflow transition firing via `apply_workflow`.

## Consequences

- New doctype: `Diploma` (non-submittable, autoname=hash, unique on `graduation_request`).
- New helper module: [`diploma.py`](../../seminary/seminary/doctype/diploma/diploma.py) — `_next_serial`, `get_permission_query_conditions`, `has_permission`.
- Two new `Graduation Request` fields: `legal_name_at_graduation` (required), `phonetic_name_snapshot`.
- New `Student` field: `phonetic_name`.
- New Print Format: `Seminary Diploma` (Jinja, fixture-managed).
- Print Format fixture filter expanded from single-name match to `in` clause.
- New permission registrations in `hooks.py`: `permission_query_conditions["Diploma"]`, `has_permission["Diploma"]`.
- New GR controller methods: `_issue_diploma`, `_revoke_diploma_if_issued`, `_guard_name_edits_after_review`, plus `on_update_after_submit`.
- New API surface on `create_graduation_request`: `legal_name_at_graduation` (required), `phonetic_name` (optional, also persisted to Student).
- New audit-page dialog (replacing the previous `window.confirm`) capturing both names.
- ADR 017 unchanged — the diploma is a downstream artefact of the same Approved state, not a modification of the request flow.
- ADR 013 unchanged — the diploma issuance relies on `apply_workflow` firing `on_update_after_submit`, which is exactly the contract ADR 013 codifies.

## Notes

- **Concurrent issuance.** Two simultaneous transitions to Approved on the same GR (registrar double-clicks the workflow button while a hook-driven transition is also in flight) are guarded by the `frappe.db.exists` check + the unique constraint. The second insert raises and is logged; the first wins. Acceptable.
- **Year-boundary serials.** `_next_serial` reads the most recent serial matching the year prefix. A diploma issued at 2026-12-31 23:59 and the next at 2027-01-01 00:00 will correctly produce `DIP-2026-####` and `DIP-2027-0001`. No carryover.
- **`verification_hash` is set in `after_insert`.** It mirrors `name`. We don't compute it earlier because `name` isn't assigned until the row is persisted (autoname=hash). The two-step (insert, then `db_set` the mirror) is acceptable; readers either see both or neither (the row isn't visible until the transaction commits).
- **Re-issuance is not modeled.** A diploma lost in the mail today gets reprinted from the same Diploma row — the print format is deterministic. If a school later wants distinct *physical-issuance* events (re-prints with a "Reissued on" annotation), that's a child table on Diploma; defer until asked.
- **No QR / digital signature today.** Both are common asks (QR linking to the verification page, cryptographic signature embedded as PDF metadata). Both are additive to the print format and the doctype as it stands; no schema change required to add them later.

## References

- [`diploma.py`](../../seminary/seminary/doctype/diploma/diploma.py) — controller, serial generation, permission helpers
- [`diploma.json`](../../seminary/seminary/doctype/diploma/diploma.json) — schema, including the two-identifier model and revocation block
- [`graduation_request.py`](../../seminary/seminary/doctype/graduation_request/graduation_request.py) — `_issue_diploma`, `_revoke_diploma_if_issued`, `_guard_name_edits_after_review`, `on_update_after_submit`
- [`api.py`](../../seminary/seminary/api.py) — `create_graduation_request` (extended args), `get_program_audit` (returns `student_phonetic_name`)
- [`ProgramAudit.vue`](../../frontend/src/pages/ProgramAudit.vue) — the new dialog replacing `window.confirm`
- [`print_format/seminary_diploma/`](../../seminary/seminary/print_format/seminary_diploma/) — Jinja template, double border, signatures, REVOKED banner
- [`hooks.py`](../../seminary/seminary/hooks.py) — Diploma permission entries, Print Format fixture filter
- ADR 013 — system-driven `db.set_value` workflow pattern (cited as the *exception* this flow does not take)
- ADR 017 — Graduation Request fee-bearing approval flow (this ADR's upstream)
