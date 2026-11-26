# 117 — Degree audit and registration against the student's catalog year

**Date:** 2026-11-25
**Status:** Accepted 2026-11-25
**Delivers:** SIS-AUD-01 (Yes), SIS-REG-01 (Yes), SIS-REC-02 (Yes)
**Amends:** 115 §5 (the course picker reads the student's catalog)
**Related:** 005 (partner transcripts), 038 (seats and waitlist), 057 (GPA floor, transfer cap), 058
(leveling), 098 (substitutions and waivers), 114 (prerequisites)

## Context

The audit reads the student's catalog (115), but the student can't see which catalog that is. It
also disagrees with the graduation check. Required leveling courses (058) block a graduation
request, but the audit doesn't show them, so it can say "Eligible" while the Request button is
missing. The GPA floor makes a student ineligible without showing any line for it, and the time
limit and the transfer cap aren't shown at all. A course met by transfer credit looks like any
other pass. Registration still offers the live Program's courses, so a course the student's
catalog requires, but that was later dropped from the Program, can't be registered for.

## Decision

1. **The catalog is shown.** The portal and Desk audits open with the program and the catalog year,
   and the disclaimer names both the catalog and the declared emphases. Catalog Year is added to the
   Program Enrollment list view and filters.
2. **One answer to "eligible".** The audit returns `blocking`, a list of labelled unmet conditions,
   and its eligibility is true only when the list is empty. The banner lists them. The audit gets a
   Leveling section (058): each leveling row with its status. A Required leveling course not yet
   passed blocks, as it does in the graduation check.
3. **Floors and limits are lines.** A Limits card shows each limit that is set:
   - the current GPA against the catalog's minimum (this one blocks);
   - transfer credits used against the cap;
   - the "graduate by" date (`max_graduation_date`), amber in the last term before it and red once
     it has passed.

   The transfer cap and the time limit are shown, not added as new blocks.
4. **Transfer credit is marked.** A requirement met by a transfer row (`is_transfer`) shows
   "Transfer", with the partner school, the source course code and the source term. The credits
   card shows how many of the earned credits are transfer credits.
5. **Other courses.** A table lists the passed and in-progress courses that don't appear under the
   program or track requirements, with their credits. Leveling courses are marked "doesn't count
   toward the degree". These rows make up the elective count.
6. **Registration reads the catalog.** 115 §5 is amended. The portal course picker offers an open
   section when its course is in the student's catalog (its courses, or the track courses of an
   active emphasis) or in the live Program. For time-based programs, a catalog course's term limit
   comes from the catalog. A course dropped from the Program stays registrable for students whose
   catalog has it, as long as a section is open. Prerequisites (114), seats and waitlist (038), and
   the self-enrollment requirements (091) are unchanged.
7. **The catalog binding is fixed.** An enrollment keeps the catalog it was bound to on submit.
   Every graduating program needs a submitted catalog before anyone enrolls (115 §7). A catalog
   later added for an earlier term therefore moves no one. Resnapshot moves a student. Enrollments
   on demo and test sites bound outside their entry term's window are test data, and are left as
   they are.

## Consequences

- A student or registrar can run a live audit that shows substitutions, waivers, transfer credit,
  leveling and limits, and reaches the same verdict as the graduation check.
- A student on an older catalog can register for what that catalog requires, even after the
  Program drops it.
- The picker can offer a course that no longer appears on the public program page. The page shows
  the current offering, not every student's catalog.

**Rejected:**
- A "what-if" audit against another program or catalog. It is useful for advising, but it isn't
  needed for the feature, and it can come later as a separate decision.
- Rebinding enrolled students when a catalog is submitted for a term that has already started. It
  changes students' requirements silently, which is what 115 exists to prevent.
