# 098 — Course substitutions and waivers with approval

**Date:** 2026-11-01
**Status:** Accepted 2026-11-01; implemented 2026-11-01 (ac6a1583)
**Delivers:** SIS-AUD-02 (Yes)
**Related:** 012 (graduation requirements), 056 (emphasis-scoped requirements), 058 (leveling and
advanced standing)

## Context

A registrar can waive a graduation requirement (012) and a placement exam can exempt a course
(058), but nothing lets course B count for required course A. The only workaround is to waive A,
and then the audit shows a hole where B belongs. Waivers are also set directly: no request, no
decision, and `waive_sgr` checks only that the caller can save the Program Enrollment. Accreditors
and RFPs ask to see a live audit with a substitution in it, and who approved it.

## Decision

1. **One record for every exception.** `Requirement Exception`, a new doctype linked to a Program
   Enrollment: `kind` (`Substitution` · `Course Waiver` · `Requirement Waiver`),
   `required_course` (Link Course), `substitute_course` (Link Course, Substitution only),
   `student_graduation_requirement` (the SGR row, Requirement Waiver only), `reason` (required),
   `supporting_document` (Attach), `status`, `requested_by`, `decided_by`, `decided_on`,
   `decision_note`. Student and program are fetched from the enrollment.
2. **Status moves only through actions.** `Requested` → `Approved` or `Denied`; the requester can
   move `Requested` → `Withdrawn`, and the registrar can revoke an `Approved` one (`Revoked`, with
   a note). `status` is read-only on Desk; whitelisted `request`, `decide`, `withdraw` and
   `revoke` set it.
3. **Who asks and who decides.** The student (from the program audit) and their mentor can
   request. Registrar and Seminary Manager (and System Manager) decide for any program; a Program
   Chair decides only for programs whose `program_director` they are. The requester may also be
   the approver: when the registrar or a Seminary Manager creates one, it is recorded as approved
   by them in the same step, so the quick path still leaves the record.
4. **What an approved exception does.**
   - *Substitution:* A counts as satisfied once B is passed, including B arriving as transfer
     credit. Approving ahead ("take B instead") is allowed; until B is passed, A shows as "To be
     satisfied by B". B can stand in for only one requirement and cannot itself be a required
     course of the program or the student's emphases.
   - *Course Waiver:* A counts as satisfied with no course in its place.
   - *Requirement Waiver:* approving it runs today's SGR waiver, and the SGR row links back to the
     exception. `waive_sgr` gains `require_registrar()` and creates an approved exception, so
     every waiver has one trail.
   - Credits are not moved. B's credits count as B's own; a program credit floor still has to be
     reached. When B carries fewer credits than A, the decide dialog warns.
5. **One function says what is satisfied.** `seminary.seminary.exceptions.satisfied_courses(pe)`
   returns completed, 058-exempted, waived and substituted courses together.
   `graduation_candidate` and `_program_audit` both call it, so the student's audit and the
   graduation check can no longer disagree (today the audit does not read 058 exemptions).
6. **Survives rebuilds.** Exceptions belong to the enrollment, not the policy snapshot. When
   requirements are re-materialized (012) or an emphasis changes (056), an exception whose
   required course no longer applies shows in the Orphan Graduation Requirements report instead
   of disappearing.
7. **Where it shows.**
   - **Program audit (student portal):** a required course not yet satisfied gets *Request
     substitution or waiver*; satisfied rows say "Satisfied by B (substitution)" or "Waived", with
     the reason.
   - **Registrar:** a *Requirement Exceptions* list with a Requested filter, and the decide dialog;
     the Program Enrollment form lists the student's exceptions.
   - Requesters and the registrar get the usual email notice on request and decision.
   - The transcript does not change: it shows courses taken, not how they were counted.

**Rejected: substitution rows on the Program Enrollment,** beside 058's leveling rows. 058's rows
are recomputed from a placement score; a request with a decision is a document with its own
history and permissions.

## Consequences

Substitutions finally appear in the audit, and every waiver records who asked, who decided and
why. The cost is one more doctype and a shared satisfaction function that both the audit and the
graduation check must use. Separation of duties is not enforced: the registrar can ask and approve
in one step, and the record shows it.
