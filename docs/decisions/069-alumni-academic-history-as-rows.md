# 069 — Alumni academic history as rows

**Date:** 2026-09-04
**Status:** Proposed

## Context

`Alumni Profile` recorded a person's academic history in three flat fields:
`program_completed`, `class_year`, `graduated_from_enrollment`. One profile per human
is right — the profile *is* the alumnus — but one **graduation** per human is not. A
graduate returns for a second degree, and the schema had nowhere to put it.

What actually happened on that second graduation was worse than an overwrite.
`alumni.api.mark_as_alumni` returned early on finding an existing profile:

```python
existing = frappe.db.get_value("Alumni Profile", {"user": student.user}, "name")
if existing:
    return {"name": existing, "already_existed": True}
```

That return sits **above** the `date_of_conclusion` stamp, so a second graduation left
no trace on the alumni record *and* left the second enrollment without its conclusion
date — while returning `already_existed: True`, which reads to the caller as success.

It was never only a display gap. `Cohort Membership._is_alumnus_of` filters
`program_completed` to decide who may **lead** a cohort scoped to a program (ADR 066),
so a graduate whose second degree went unrecorded silently lost a permission the policy
grants them. And `graduated_from_enrollment` was written by exactly one line and read
nowhere — a write-only field.

Separately, `class_year` was an `Int` derived as `getdate(date_of_conclusion).year`,
while the rest of the app identifies a year through `Academic Year`, whose name is
free-form `Data` (`2017-2018`, and on a demo site `DEMO-2025-26`). The two could not be
reconciled, and the derivation was wrong on its own terms: a student concluding in
December of 2017-2018 was recorded as **Class of 2017** when the school calls them Class
of 2018. Every autumn graduate was labelled a year early.

This predates ADR 068. Making one-profile-per-person explicit is only what made it
visible.

## Decision

**Completed programs become rows.** A new child table `Alumni Graduation` on
`Alumni Profile` holds `program`, `academic_year`, `class_year`, `conclusion_date` and
`program_enrollment`. `mark_as_alumni` appends a row instead of returning early, keyed
on the enrollment so re-running is idempotent — and keyed on the *enrollment* rather
than the program, because completing the same program twice under different enrollments
is a real career, not a duplicate.

**The three flat fields are deleted, not kept as derived summaries.** A derived "most
recent" field would be the second home for data that ADR 068 spent five phases removing,
and "most recent" is a guess about which degree matters to a given reader. The five
consumers move to the rows: the alumni home page and directory render a list, the
cohort-leader eligibility check queries the child table, the importer seeds a first row
from its `program_completed` / `class_year` CSV columns, and two test fixtures follow.

**`academic_year` is a Link, `class_year` stays a number, and they answer different
questions.** The Link is the school's own identifier, consistent with every other date
context in the app. The number is the alumni convention — "Class of 1998" — which has to
sort and filter, so it cannot be the free-form year name. It is now derived from the
academic year's `year_end_date`, falling back to the conclusion date only for an alumnus
imported without an academic year at all. Deriving it from the year's *end* is what
fixes the autumn graduate.

**The directory no longer sorts by class year.** A person can hold several graduations,
so "their class year" is not a single sortable value; ordering by one of them would
silently pick a row. It orders by name, and filtering by program or class year reaches
through the child table, where a graduate with two degrees now matches on either.

## Consequences

**Easier.** A second degree is recorded, and so is its conclusion date. A graduate of two
programs is an alumnus of both for cohort-leadership purposes, which is what ADR 066
always intended. Autumn graduates get the right class year. An alumnus imported from
before this system, with no enrollment behind them, is expressible — the row simply has
no `program_enrollment`.

**Harder.** "The alumnus's program" is no longer a single value, so any future feature
wanting one has to say which — most recent, highest, or all. That is a real cost, and it
is the honest one: the singular answer was always a guess.

**Not decided here.** What else belongs on a graduation row — honours, emphasis, the
credential awarded, a GPA — is left open. The row exists now; adding a column to it is
cheap, which was the point.

**Migration.** A patch moves each existing profile's flat values into a first row,
recomputing `class_year` from the academic year rather than carrying the stored integer
across, since that integer is exactly the value this ADR calls wrong. Frappe leaves the
dropped columns in the table, so the patch reads them directly rather than through the
meta.
