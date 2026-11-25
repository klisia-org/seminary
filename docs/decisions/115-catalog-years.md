# 115 — Catalog years: program requirements versioned with the graduation policy

**Date:** 2026-11-25
**Status:** Accepted 2026-11-25; implemented 2026-11-25
**Delivers:** SIS-CUR-02 (Yes)
**Amends:** 012 (policy resolution by date), 024 §"Versioning by workflow" (Change Version)
**Amended by:** 117 §6 (the course picker reads the student's catalog)
**Related:** 058 (leveling), 098 (substitutions and waivers), 114 (course catalog)

## Context

Only half of a program's requirements are versioned. The Program Graduation Requirement (PGR) is
frozen per student (012, 024), but courses, credits per course, credits to graduate, minimum GPA,
the transfer cap, maximum time and emphasis courses are read live from the Program. A registrar
who makes a course required changes every current student's audit. A school can't show two catalog
years side by side, and can't prepare next year's curriculum without changing this year's. 024's
Change Version also leaves the program without an active policy until the successor is submitted.
The audit counts a disabled required course as required.

## Decision

1. **The PGR is the catalog year.** It gains an Academic Requirements tab: a `Catalog Course` table
   (course, required, credits, term), a `Catalog Track Course` table (track, course, mandatory,
   term), and credits to graduate, terms to complete, minimum GPA, transfer-credit cap, maximum
   time, emphasis overlap policy, each emphasis's added credits and the honors levels. Disabled
   program courses are
   not copied. The Program keeps the same fields as the live offering and stays where curriculum is
   edited day to day.
2. **Windows are academic terms.** `academic_term_from` is required. `academic_term_to` is
   read-only: the term before the successor's first term. `active_from` and `active_until` are
   removed. The catalog year label ("2027–28") comes from the first term's academic year.
   `resolve_policy` takes the enrollment's entry term (`academic_term`, else the term containing
   `enrollment_date`). It returns the submitted PGR whose window contains it, whether that PGR is
   Active or Superseded. Overlap is checked on term windows.
3. **One way to publish, so a next catalog can be drafted.** **New Catalog Year** on the Program
   creates a Draft PGR. Its academic section is copied from the Program, its other requirement rows
   from the current catalog, and its first term defaults to the next term without a catalog. The
   draft's academic section is editable. Courses can only be added from the Program's courses, and
   tracks only from its Program Tracks. The Program is untouched until the draft takes effect,
   which is the "draft next catalog" mode. To publish an edit already made on the Program, create
   the draft and submit it unchanged.
4. **Taking effect.** The workflow is Draft → Scheduled → Active → Superseded. Submitting makes the
   catalog Scheduled. A daily job activates it when its first term starts, or on submit if that
   term has already started. Activation (a) writes the catalog's academic section onto the Program:
   rows missing from the catalog become disabled, with "Not in the 2027–28 catalog" as the reason;
   and (b) supersedes the previous catalog. The previous catalog stays Active until then, so the
   gap 024 accepted is gone. While a draft or scheduled catalog exists, the Program form says so,
   and says that curriculum edits on the Program will be replaced when it takes effect. When no
   draft exists and the Program differs from the Active catalog, the form shows the differences.
   Courses-to-offer for a term reads the catalog whose window covers that term. Cancellation is
   still not part of the lifecycle.
5. **Requirement readers use the student's catalog.** A helper, `catalog.for_enrollment(pe)`, is
   read by:
   - the graduation check
   - the program audit
   - the GPA minimum and honors
   - the transfer cap
   - time-to-graduate risk
   - required auto-enrollment
   - culminating projects
   - partner transcript import
   - substitutions and waivers (098)

   Billing charges the credits in the student's catalog, and falls back to the Program for a course
   that isn't in it. Offering readers stay on the Program: the public program page, course
   schedules, the term plan, bulk enrollment and the course picker.
6. **Compare.** **Compare** on a PGR shows it beside another version of the same program, by
   default the one it supersedes:
   - courses added and removed
   - changes in required status, credits and term
   - changes in the other academic fields
   - requirement rows added, removed or changed

   The same comparison is a whitelisted method other apps can call.
7. **Every graduating program has a catalog.** A program that isn't ongoing can't be published,
   and an enrollment in it can't be submitted, until a catalog covers the enrollment's term. Setup
   Progress lists the step. Resnapshot moves a student to a chosen catalog, not only the current
   one, and logs the change.

## Consequences

- A requirement change reaches only students who enter in that catalog's terms, or who are moved
  there on purpose.
- Next year's curriculum can be prepared without touching this year's offering. Edits made
  directly on the Program still take effect at once, and are replaced when a scheduled catalog
  takes effect.
- Catalogs created before this change only hold today's Program, because earlier history isn't
  recorded. No school is live, so demo and test sites get one catalog per program from its
  earliest term.
- A student is billed for the credits a course carries in their catalog, so a course whose credits
  change costs a continuing student what it did when they entered.

**Rejected:**
- Versioning the Program record itself. Every record about the program as a whole (fees, cohorts,
  inquiries, announcements, reporting) would have to resolve a family of versions.
- Copying the requirements onto each enrollment. That gives no catalog year to compare, and
  Resnapshot already moves one student.
