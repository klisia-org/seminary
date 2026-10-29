# 094 — Migrating a school's history from another system

**Date:** 2026-10-29
**Status:** Accepted 2026-10-29; implemented 2026-10-29
**Delivers:** SIS-IMP-01 (Partial)
**Related:** 005 (partner seminaries and legacy data); aretenic 048 (bulk dataset import),
aretenic 050 (people import)

## Context

A school leaving Populi, CAMS, Jenzabar or spreadsheets wants its history to come across, not only
its people. We import people (aretenic 050), opening balances (tamias), and past coursework through
an Internal Legacy partner (005). Aretenic 048 plans the rest: programs, courses, terms and prior
enrolments, in dependency order with keyed re-runs. Three things are still undecided:
- what the past looks like once it is in seminary;
- how to stop it acting like the present;
- what to do with attendance and documents.

## Decision

1. **Imported history does not act.** Seminary skips its side effects while
   `frappe.flags.in_import` is set:
   - fee triggers;
   - notices and welcome emails;
   - cohort seeding;
   - at-risk and stall alerts.

   Frappe's Data Import already sets this flag, and our importers set it too. An importer may still
   ask for one side effect on purpose, as Person Import does for welcome emails.
2. **Past enrolments arrive finished.** A Program Enrollment is imported with its final status and
   dates, such as Graduated with the conferral date or Withdrawn with the withdrawal date. The
   status is set directly, without running the status transitions, and graduation is not
   recomputed.
3. **Attendance history comes as a summary per course:** sessions attended out of sessions held,
   on the course row. Per-session rows are not imported.
4. **Documents come by reference** (048 §5) and are stored on the student record, each with a
   document type.
5. **Source profiles stay outside seminary.** A Populi, CAMS or Jenzabar export is mapped onto
   048's columns by a named profile in aretenic. Seminary keeps only the targets. The first school
   to migrate from a system decides which profile is built first.

## Consequences

Migration becomes a matter of loading files, not scripts. Our answer to SIS-IMP-01 can be Yes once
048 and this record are built. Every side effect we add later has to check the flag.
