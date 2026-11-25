# 112 — Applicant review and admission decisions

**Date:** 2026-11-24
**Status:** Accepted 2026-11-24
**Delivers:** SIS-ADM-04 (Partial)
**Related:** 019 (term admissions), 058 (requirement review), 091 (agreements and documents),
095 (rubrics), 111 (application questions)

## Context

An application is decided by one click. *Approve* or *Reject* on the Desk form sets
`application_status`, and nothing records who decided, why, or what the reviewer thought.
Reviewers ask for scored reviews and a recorded decision, not just a status field. In a small
school one person decides. A devotional course admits everyone who completes the form. A
seminary that admits by committee votes in a governing body, which another app may provide.
Seminary therefore owns the review and the outcome, and lets another app decide.

## Decision

1. **`Program.admission_mode`** is *Reviewed* (the default) or *Automatic*. A Reviewed program is
   reviewed by the active members of its admissions unit (§1a). Without one, its
   `program_director` reviews, or the Registrars when no director is set.

   **1a. Admissions unit.** Academic Unit gains the type *Program Admissions*. A Reviewed program
   names one in `Program.admissions_unit`, which is shown only for Reviewed programs and accepts
   only active Program Admissions units. Several programs may share one, for example a unit per
   Program Level. `Program.academic_unit` stays the Program Committee that oversees the program and
   has no part in admissions. The unit's chair decides (§5), so the chair reviews too, whether or
   not they are a member. A member without an enabled user is skipped. If the unit has no
   such member, the director or the Registrars review as above.
2. **Complete, then In Review.** An application is complete when its required answers (111), its
   documents and agreements asked on the application (091), and any application fee are in. When
   it is complete, its status becomes *In Review* and each reviewer gets an Application Review and
   a ToDo. 111's answers lock at this point. An Automatic program skips review, and the system
   records an *Admit* decision at once.
3. **Application Review** is one per reviewer per applicant. It records a due date, a
   recommendation (*Admit*, *Admit with conditions*, *Waitlist*, *Decline*), comments, and rubric
   scores. A reviewer can *Recuse*, with a note on the conflict, and the note is kept. A reviewer
   sees the others' reviews only after submitting their own. Reviewers can read the applications
   they review.
4. **Scoring reuses 095.** A Rubric may belong to a Program, using the school's Rubric Scale.
   Rubric Score accepts Application Review as its submission, with the student left blank. Each
   review shows its overall percent. A program with no rubric is reviewed by recommendation alone.
5. **Admission Decision** is submittable: applicant, decision (same four options), conditions,
   rationale, decided by, and `decided_through` (a Dynamic Link to the record that produced it).
   On a Reviewed program the admissions unit's chair, the director, a Registrar or a Seminary
   Manager submits it. A decision
   that differs from the majority of submitted recommendations needs a rationale. Reconsideration
   cancels and amends it, and the history is kept.
6. **Another app may decide.** A `seminary_admission_deciders` hook is asked about each Reviewed
   program. An app that decides by committee routes through the program's admissions unit, never
   through `academic_unit`. An app that claims the program supplies its reviewers and due date, and records the
   outcome through `admissions.record_decision(applicant, decision, conditions, rationale,
   decided_through)`. Seminary then hides its own *Decide* action for that program.
7. **Status is derived.** `application_status` becomes read-only and follows the latest submitted
   decision: Applied → In Review → Approved | Waitlisted | Rejected, then Admitted on *Enroll*, or
   Withdrawn if the applicant withdraws. The *Approve* and *Reject* buttons are removed.
8. **Conditions travel.** *Admit with conditions* copies the conditions to the Program Enrollment
   on *Enroll*. When the conditions name leveling, the 058 requirement-review ToDo is raised too.
9. **The applicant is told** through `comms.send_message`, with one message template per decision.
   The applicant's portal shows the status and the conditions, never the reviews.

## Consequences

- Every admission has a record of who reviewed, how they scored, what was decided and why.
- On its own, Seminary gives a program a panel of reviewers through its admissions unit, and one
  person decides. A vote with quorum and recusals needs an app that claims the program (§6).
- A program's oversight committee and its admissions panel are separate units, so a school can
  give admissions to a smaller group, or share one panel across a Program Level.
- Status can no longer be set by hand. A stuck application has to be fixed through its decision.
- Interviews aren't modelled. A reviewer notes one in the comments.
- Conditions are recorded, not enforced. Tracking whether they are met is left for later.

**Rejected:**
- A Frappe Workflow on Student Applicant. It moves the status, but it holds no reviews, scores or
  rationale.
- A committee doctype in Seminary. Academic Unit already holds the members, and a vote with quorum
  and conflicts belongs to a governance record, not to admissions.
