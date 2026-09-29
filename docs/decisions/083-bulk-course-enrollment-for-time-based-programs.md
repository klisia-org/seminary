# 083 — Bulk course enrollment for Time-based programs

**Date:** 2026-09-28
**Status:** Accepted 2026-09-28

## Context

A Time-based program (CBE included, 065) says which courses each term needs through
`Program Course.course_term`. To put students in those courses, the registrar either creates CEIs
one by one or waits for students to enroll themselves. New students, who don't know the portal
yet, are the ones who wait longest. `petb_enroll`, run by Advance Students when `advancetb` is on,
tries to do this automatically. It looks in the *current* term, not the one being enrolled for.
It takes the first open section it finds, ignores track courses, and shows no fees. Its failures
end up as ToDos. The `time_based_enrollment_gaps` report shows gaps against the current term only,
and it has no way to fix them.

## Decision

1. **Bulk Course Enrollment is a new doctype, and one document is one run.** The registrar sets up
   the run on one Desk page and keeps it as the record of what was done. It has these parts:
   - **Target:** an Academic Term and one or more Time-based programs.
   - **Students:** filters for the student's term index (`current_std_term`) and the intake term
     (`Program Enrollment.academic_term`). "New students this term" is intake = target. Only
     active enrollments are listed. **Get Students** fills a table with an include checkbox.
     The table flags students who have a Student Hold, so the registrar can untick them.
   - **Courses:** **Get Courses** fills one row per expected course. Expected courses are the
     Program Course rows (and active-emphasis track rows) whose term is each student's term
     index. Each row shows the open Course Schedules for that course in the target term, with
     seats left against the number of students. The registrar picks one section, or splits the
     students between several sections. A row can be unticked.
   - **Charges:** shown only when the backend has financials (063). For each course, the page
     shows what one student would be charged, using a new optional backend method
     `preview_enrollment_charges(pe, course_schedule, credits, audit)`. oikonomos answers from
     payer rows and the Item Price, tamias from the Payer Split and the Fee's Price Tier, and
     the null backend returns nothing. Program Fees and Fees stay the only place prices are
     set.
2. **Enrolling uses `course_enroll`, and the run is queued.** **Enroll** runs on the long
   queue. It enrolls one student at a time, each with its own savepoint. Each student×course
   result goes into a results table: Enrolled, Awaiting Payment, Waitlisted, Skipped (already
   covered) or Failed, with the reason. Prerequisites, duplicates, capacity (as the waitlist,
   038) and billing on submit (016, 063) work as they do for one enrollment. The registrar is
   the one enrolling, so the run submits the CEIs even where the program has
   `registrar_block_cei` set. Payment gating still follows the program's rules. Running it again
   retries only the Failed and not-yet-run rows. No ToDos are created, because the run itself
   records the failures.
3. **`petb_enroll` and the `advancetb` setting are retired.** Advance Students only advances
   students. Its message then offers a Bulk Course Enrollment for the new term.
4. **Students advance one step at a time, and only after that step's grades are in.** A
   *step* is one program's students moving from term index N to N+1 out of one Academic Term
   (e.g. "MACL, term 1 → 2").
   - **Ready:** every Course Schedule where those students hold a CEI in that Academic Term is
     Closed. Only Send Grades can close a section (013). Cancelled sections are ignored, and
     so are open-ended self-paced sections (065), because they don't follow the term. A
     section shared by two programs blocks both.
   - **Blocked:** one or more of those sections is not Closed yet. The step lists them.
   - **Done:** the students were already advanced out of that Academic Term. A new Program
     Enrollment field, `advanced_from_term`, records the last Academic Term each student was
     advanced out of. A student can leave a given Academic Term only once. Students who were
     just moved from 1 to 2 are therefore never picked up again by the 2 → 3 step.
   - **Final:** students on the program's last term (`terms_complete`). These are shown but
     can't be advanced; they graduate instead.

   Advance Students opens a dialog. At the top the registrar picks the closing Academic Term
   (by default the latest one that has ended) and a program (All Programs, or one). The dialog
   then shows one row per step:

   | Program | Step | Students | Status |
   |---|---|---|---|
   | MACL | Term 1 → 2 | 12 | 🔴 Waiting for grades: CS A, CS B |
   | MACL | Term 2 → 3 | 9 | 🟢 Ready |
   | MDiv | Term 1 → 2 | 20 | ⚪ Done on 12 Dec 2026 |
   | MDiv | Term 6 | 7 | ⚪ Final term |

   Ready rows have a checkbox and start ticked; the others can't be ticked. Each blocked section
   is a link to its Course Schedule. **Advance selected** first shows a confirmation, such as
   "Advance 9 students: MACL term 2 → 3. This can't be undone." It then reports what happened
   for every row, not only the ticked ones: "Advanced 9 MACL students from term 2 to 3. MACL
   students in term 1 were not advanced: grades for CS A and CS B haven't been received." A
   **Bulk Course Enrollment** button opens a run filled with the students just advanced.

   The server checks each step again and skips any step that is no longer Ready, giving the
   reason. A stale dialog, a double click or an API call therefore can't advance a student twice
   or before their grades are sent.
5. **The gaps report becomes the check.** `time_based_enrollment_gaps` takes a required
   Academic Term and adds track courses. For each active enrollment × expected course, it gives
   the CEI and its state: Enrolled, Awaiting Payment, Waitlisted or Draft. Where there is no CEI
   it gives a reason, now including "Offering closed". A "Gaps only" filter is on by default. An
   **Enroll missing** button creates a Bulk Course Enrollment already filled with the ticked
   gaps.

**Rejected: flag every term-1 course as required on enrollment (035).** New students would get
their first courses without any extra tool. But it only runs when the enrollment is submitted or
a section opens. It lets no one choose a section, does nothing for returning students and shows
no fees.

**Rejected: prices or waivers set on the run.** They would go around the fee catalogue, payer
splits and scholarships. A one-off discount stays in the bridge.

## Consequences

Registrars can seat a whole intake or cohort in one step, choose sections and see the charges
before committing. The run and the report both use `current_std_term`, so students must be
advanced before a run. Because of §4, that happens only after the previous term's grades are
sent. A late section holds back only the steps whose students it holds, and the registrar
chases it or cancels it. Advance Students still can't be undone. Credits-based programs have no
expected courses per term, so they are out of scope. Adding them later would need course rows
chosen by hand. Whether an active
Student Hold should block a CEI (today it blocks only re-enrollment, 033) is still open. For now
the run only flags it.
