# 002 — Program Emphasis & Track Credit Architecture

**Date:** 2026-04-07
**Status:** Accepted

## Context

The original Program model used a single `emphasis_program_track` Link field on Program Enrollment, hard-coding one emphasis per student. Track credits (`addcredits` on Program Track) had an ambiguous relationship with the program total — unclear if included or additional. Several real-world scenarios were unaddressed: schools that allow multiple emphases, late declaration, auto-granting based on coursework, fallback emphases (e.g. "General Studies"), and credit ceilings that cap how many track credits count toward the degree. No tooling existed for students to see remaining requirements or for advisors to monitor progress at scale.

## Decision

1. **Multiple emphases via child table.** Replace the single Link field with a `Program Enrollment Emphasis` child table on Program Enrollment. Each row carries `emphasis_track`, `status` (Active/Completed/Dropped), `declared_date`, and `trackcredits`. This supports one or many emphases per student, controlled by `allow_multiple_emphases` on Program.

2. **Track credits are included in the program total.** Double-counting is allowed: a course satisfying both a core requirement and an emphasis requirement counts toward both. This matches the most common seminary model and avoids forcing students into extra coursework for a single degree.

3. **Credit ceiling per track.** New `max_credits` field on Program Track caps how many track credits count toward the degree. A student may take 35 credits in Counseling courses, but if the ceiling is 30, only 30 count.

4. **Overlap policy for multiple emphases.** Program-level `emphasis_overlap_policy` controls whether a second emphasis shares the same credit pool ("Shared Credit Pool", default) or requires additional credits on top of the program total ("Additional Credits Required").

5. **Emphasis lifecycle flexibility.** Each Program Track declares `emphasis_declaration`: "At Enrollment" (default, must choose before PE submission), "Anytime" (declare after enrollment when `min_credits_to_declare` is met), or "Auto-grant" (system awards when all mandatory track courses are passed and credit floor is met). A `fallback_emphasis` on Program designates a default track for students who never declare.

6. **New APIs for progress tracking.** `get_program_audit(program_enrollment)` returns credits earned/required, emphasis progress with ceiling, mandatory course status, and graduation eligibility. `get_available_courses_categorized(program_enrollment)` wraps the existing course availability query and tags each course as Program Mandatory, Track Mandatory, or Elective — with courses potentially appearing in multiple categories (intentional, since the same course can serve multiple tracks).

7. **Auto-grant and credit recalculation after grading.** `send_grades()` now triggers per-PE emphasis credit recalculation (respecting ceilings) and checks whether any auto-grant emphases should be awarded.

## Consequences

- Schools with single-emphasis programs set `allow_multiple_emphases = 0` and get the same behavior as before, just via a child table row instead of a Link field.
- The old `emphasis_program_track` and `trackcredits` fields on Program Enrollment are removed. No migration patch — no production data exists yet.
- The `credits_pe_track()` batch function and `courses_for_student()` SQL now JOIN against the child table instead of reading a single field. Performance is equivalent since the join is bounded by the small number of emphases per enrollment.
- Double-counting simplifies credit accounting but means a program designer must set `credits_complete` knowing that core and track courses overlap. This is documented in field descriptions.
- Deferred for future work: transfer credit interaction with emphasis requirements, non-credit milestone tracking (thesis/capstone as 0-credit courses is the interim workaround), and the student portal pages (Phase 3) and advisor desk reports (Phase 4) that consume these APIs.
- The "Courses to Offer" Script Report (Phase 4) will use mandatory-course-not-yet-taken data from `get_program_audit()` to help registrars plan which courses to schedule each term.
- Unaddressed feature: Emphasis Overlap feature does not contemplate Partial Shared Credit Pool: All emphases share the same credit pool but the student or academic advisor may choose which emphasis a course counts towards, so it can only satisfy one emphasis.