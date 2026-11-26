# 119 — Final grades: incompletes, changes, repeats and transcripts

**Date:** 2026-11-25
**Status:** Accepted 2026-11-25; implemented 2026-11-25
**Delivers:** SIS-GRD-01 (Yes), SIS-GRD-02 (Yes), SIS-GRD-03 (Yes)
**Amended:** 2026-11-26, §1 (the lapse rule is the scale's, not a setting; see Amendment)
**Amends:** 013 (Send Grades no longer waits for every student)
**Related:** 013 (course lifecycle), 033 (holds), 063 (financial backend), 072 (descriptive scales), 081 (fail for absences),
082 (individual due dates), 084 (term advancement), 114 (equivalent courses)

## Context

Send Grades is all or nothing. One student who hasn't finished blocks the whole class, because
there is no Incomplete. After grades are sent, the gradebook is read-only, but only in the browser.
A Desk or API write still changes a roster that no longer matches the transcript row. There is no
other way to correct a sent grade. A retaken course counts every attempt toward GPA and credits.
The only transcript is the student's own portal page. There is no official copy, no request and no
hold check. These are one lifecycle, from the course grade to the transcript, so they are decided
together.

## Decision

1. **Incomplete at Send Grades.** Before sending, the instructor can mark a student Incomplete,
   with a reason and a completion date. Seminary Settings sets the default date and the longest
   date an instructor may grant (`incomplete_instructor_max_days`, counted from the course end).
   A student marked Incomplete doesn't count as ungraded, so Send Grades goes through for the rest
   of the class and the course closes.
   - Past that limit, the student files an **Incomplete Extension Request** from the portal, with
     a reason and the date they ask for. The instructor gives an opinion and the Registrar
     decides. Approval moves the completion date and the individual due dates.
   - The student's transcript row gets the scale's new **Incomplete code**, with no credits and
     not counted in GPA. Their roster stays active.
   - The gradebook stays open for that student only. Their assessments get an individual due date
     (082) set to the completion date.
   - The instructor finishes with **Send Grade** for that student, using the same finalize step as
     the class.
   - Seminary Settings sets `incomplete_reminder_days` (default 2). That many days before the
     date, if work is still unsubmitted, the student and the instructor each get an email.
   - When the date passes, a daily job finalizes the student by the `incomplete_lapse_rule` in
     Seminary Settings: either *Grade unfinished work as 0*, or *Assign the scale's lapse code*
     (a new code on Grading Scale, such as F). It notifies the student, the instructor and the
     Registrar.
   - Term advancement (084) waits until the student's last Incomplete is resolved.
2. **Sent grades are frozen on the server.** Once a roster is finalized, its assessment results
   and roster are refused on save, whatever the path. The only exceptions are an open Incomplete
   (1) and an approved grade change (3). The browser lock stays.
3. **Grade change request.** The instructor or the Registrar raises a request on a finalized
   roster: the assessment cells to change, the new values and a reason. The Registrar approves it.
   Approval writes the cells, recomputes the final grade, and updates the transcript row, credits,
   GPA and standing. The request is the audit record, and a rejected request changes nothing.
   Seminary Settings can require a second approver: a role (`grade_change_second_approver_role`)
   and a number of days after the grade was sent (`grade_change_second_approval_days`). Past that
   number, both the Registrar and someone in that role must approve. Leave either field empty and
   the Registrar decides alone.
   Fail-for-Absence undo (081) stays as it is.
4. **Repeats are derived.** A second final grade for the same course, or an equivalent one (114),
   in the same Program Enrollment is a repeat. Nobody enters it. Program gets a `repeat_policy`:
   *Most recent* (default) or *Highest*. The attempt that doesn't count stays on the transcript,
   marked Repeated, with `count_in_gpa` off and no credits. Program also gets an optional
   `max_attempts`. Enrolling past it needs the Registrar.
5. **Transcripts.** There is one render, used in two ways:
   - **Unofficial:** the student, or the Registrar for any student, opens it any time from the
     portal or Desk, watermarked Unofficial.
   - **Official:** a **Transcript Request** from the student, an alumnus or the Registrar. Its
     recipient is the student, an email address, or a printed copy. An active Financial or
     Administrative hold blocks it, but not the unofficial copy. On issue, the system renders a PDF
     with the Registrar's signature image and a verification code, and stores the PDF's SHA-256.
     A public page takes the code and shows the student's name, the date issued and the hash. A
     recipient can upload the PDF to check that it matches. The page never shows the grades. The
     request records who issued what and when.
   - The transcript lists every attempt by term: transfer credit, Withdrawn, Fail-for-Absence,
     Incomplete and Repeated codes, GPA, and the degree conferred. It shows each scale's own value,
     never a percentage for a Descriptive or CBE course (072).

6. **Optional fees, set in the financial backend (063).** Seminary names two charge events and
   holds no prices. A school that sets up no fee, or runs with no financial app, pays nothing.
   - **Incomplete Extension Request:** `charge_incomplete_extension(request)` runs on approval. A
     declined request is never charged.
   - **Transcript Request:** `charge_transcript_request(request)` runs on submit. It passes the
     delivery method and the number of copies, so the price can vary by them. The request waits
     in *Awaiting Payment* and is issued once `payment_status_for_transcript_request` reports it
     paid, the same way a Graduation Request is held. The Registrar can waive the fee on the
     request, with a reason. Unofficial copies are never charged.

Rejected: cryptographic PDF signatures for v1. They need a certificate the school would have to buy
and renew, while a verification page proves the same thing to a recipient. Parchment and the
National Student Clearinghouse are integrations for later, built on the Transcript Request.

## Consequences

- A teacher can close a course on time without failing a student who has an approved reason to
  finish late.
- An open Incomplete has a deadline that lapses on its own, so it never stays open indefinitely.
- What the transcript says can only change through a reviewed request, so an accreditor can trace
  every change.
- GPA changes for students who already have repeats. Recomputing GPA must run once on deploy, and
  be checked on a production-shaped site.
- An Incomplete past the instructor's limit, and an old grade change, both reach the Registrar,
  so the school's exceptions come from people who see them all.
- A verification page that only checks a hash proves the PDF is authentic, but not that a printed
  copy is. A printed copy still needs the code typed in and a visual check.

## Amendment (2026-11-26)

§1's lapse rule moves from Seminary Settings to the grading scale. `incomplete_lapse_rule` is
dropped: a scale's **Code When an Incomplete Lapses**, when set, is the final grade; blank means
unfinished work counts as 0. The code must be one of the scale's grades, and the Incomplete code
must not be. The gradebook offers **Incomplete** only where the scale has an Incomplete code and the
student has unfinished work, so an instructor never meets an error they can't fix.

