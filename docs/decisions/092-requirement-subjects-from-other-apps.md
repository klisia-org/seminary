# 092 — Requirements owed for other apps' records

**Date:** 2026-10-23
**Status:** Accepted 2026-10-23
**Related:** 091 (agreements and required documents), 043 (channel adapters)

## Context

091 lets a Person owe agreements and documents for a Program Enrollment or an Instructor. Other
apps on the same site need the same thing for their own records, for example an outside author
signing a copyright notice and the doctrinal statement when they send in work. Today the two
subjects are hardcoded (`SUBJECTS`, `person_of`, `rules_for` in `requirements.py`). Adding another
app's doctype there would put its name in seminary, on sites that don't have it.

## Decision

1. **`requirement_subjects` hook.** `{doctype: "dotted.path"}`, the shape of
   `communication_channel_providers`. The path names an object with:
   - `person(name)`: the Person who owes;
   - `rules(name)`: the Requirement Rule rows that apply, usually from a Requirement Rule table on
     the app's own doctype;
   - `label(name)`: what the portal's *For* column shows;
   - optionally `active()`: the records the daily sweep keeps current, for renewals and for rules
     added later.

   A doctype that is not installed, or that seminary already handles, is skipped and logged.
2. **Seminary's two subjects stay as they are.** The hooked ones go through the same
   `ensure_requirements`, signing, review, notices and portal page.
3. **The other app decides when rows open and what blocking stops.** It calls
   `ensure_requirements` itself, and `overdue_blocking` where its own record should wait.
4. **Template fields come from the existing `agreement_context` hook** (091 §7). A hooked subject
   gets `person`, `school` and `today`. Its app adds the rest, including the doctrinal statement it
   wants, since Doctrinal Statement only marks one for admission and one for instructors.

Letting the other app insert Person Requirement rows directly was rejected: it would skip the
duplicate check, renewals and notices.

## Consequences

- An app adds its subject in its own `hooks.py`, with no change to seminary.
- A Person sees every requirement on one Requirements page, whichever app it is for.
- Uninstalling the app leaves its rows; they show the bare record name and are no longer swept.
