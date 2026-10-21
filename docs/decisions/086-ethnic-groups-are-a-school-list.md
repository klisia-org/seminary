# 086 — Ethnic groups are a list each school keeps

**Date:** 2026-10-02
**Status:** Accepted 2026-10-02
**Related:** 042 (Person is the spine), 068 (shared attribute registry)

## Context

Person and Student Applicant record an ethnic group from a fixed list (Black, Hispanic, White Non
Hispanic, Native American, Pacific Islander, Other). It is a United States list. A school in Brazil,
Kenya or Korea cannot record anything meaningful with it, and a school reporting to its government
needs that government's categories. A global catalogue such as Joshua Project's 16,000 people groups
is far too fine for reporting and would expose individuals in small groups.

## Decision

1. **Ethnic Group** becomes a doctype each school curates on Desk: name, active, display order. It
   is seeded with the current six values, so nothing changes until a school edits it.
2. `Person.ethnicity` and `Student Applicant.ethnic` become Links to it, still sensitive and
   permission-level 1 as today. The applicant web form offers the active groups.
3. A patch keeps every existing value: each one already stored becomes a group if it is missing.
4. Seminary ships no other list. A school replaces the seed with the categories it reports.

## Consequences

- Schools outside the United States can record ethnicity in their own terms.
- Reports group by whatever list the school keeps, so totals follow the school's own categories.
- The field stays optional and sensitive; nothing new is asked of applicants.
