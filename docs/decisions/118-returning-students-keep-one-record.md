# 118 — Returning and second-degree students keep one Student record

**Date:** 2026-11-25
**Status:** Accepted 2026-11-25; implemented 2026-11-25
**Delivers:** SIS-REC-01 (Yes)
**Amends:** 033 (an admitting decision lifts the holds it answers)
**Related:** 033 (holds and standing), 042 and 068 (Person spine), 111 (application form), 112 (admission decisions)

## Context

The portal application form is anonymous and matches a Person by email. A returning or
second-degree student who applies with their old email reaches their existing Person. Enroll
Student then always creates a new Student, and fails with a duplicate-entry error, because a
Person holds only one Student. A student who applies with a new email becomes a second Person,
whose history only a merge could join to the first. Staff who add a Program Enrollment to an
existing Student in Desk aren't affected.

## Decision

1. **Returning students sign in to apply.** The application page asks "Have you studied with us
   before?" and offers two ways forward:
   - **Sign in.** A signed-in applicant's application is filed under their own Person. The email
     comes from their account and can't be edited, and the personal details are filled in from the
     Person. The form accepts a new application from a signed-in user. An earlier application isn't
     reopened.
   - **I can't use my old email.** A short Returning Student form asks for the name, the birth
     date, the email used before (if known), phone, the new email and the program of interest. It creates
     a ToDo for the registrar, who confirms the person's identity and changes the Person's email.
     The student then gets a sign-in link and applies signed in. This form doesn't create a Person.
2. **A returning applicant is flagged.** When the applicant's Person already holds a Student, the
   application records that Student (`returning_student`) and its standing at the time
   (`prior_standing`). Both are derived, and they stop changing once the applicant is admitted. A
   standing of Dismissed or Suspended sets `readmission_review`:
   - the application goes to review even on an Automatic program;
   - the reviewers' ToDo, the review form and the applicant form say so, and show the active holds
     with their reasons;
   - an admitting decision needs a rationale that says what has changed since.

   A committee that decides for the program (112) records its reasoning in its own record.
3. **Standing changes only when the application is accepted.** Standing stays derived (033), so
   nothing changes before the decision. An admitting decision lifts the Student's active
   Disciplinary and Academic holds that block re-enrollment, and records the decision on each hold.
   Cancelling the decision restores those holds. Standing becomes Good Standing once the new
   enrollment exists. Financial and Administrative holds stay, and still block.
4. **Admission reuses the Student.** When the applicant's Person already holds a Student, Enroll
   Student uses that Student and creates the new Program Enrollment under it. If the Student is
   disabled, it is enabled.
5. **Each enrollment records its application.** Program Enrollment gains `student_applicant`
   (read-only), set by Enroll Student. `Student.student_applicant` stays the first application.
6. **Staff see a returning applicant.** The applicant form says "Already a student" or "Alumnus",
   with the programs, when the Person holds a Student or an Alumni Profile.

## Consequences

- A student has one record, one transcript and one portal login across programs and readmissions.
- A dismissed student can't be readmitted without someone deciding, in writing, that the reason
  for the dismissal has been dealt with.
- A readmitted student's old enrollments stay as they are. The new enrollment takes the catalog
  for its own entry term (115).
- A returning student who ignores the prompt and applies with a new email still becomes a second
  Person. The duplicate pass proposes the pair, and staff resolve it before admission.

**Rejected:**
- Merging two Students. Asking returning students to sign in keeps the duplicate from being created,
  which is simpler than joining two academic histories afterwards.
- One Student per application. That splits the transcript and the portal login, which is the
  problem this record solves.
- Matching applicants by name and birth date at intake. A wrong automatic match would attach a
  stranger's history.
