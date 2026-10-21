# 084 — Term advancement at Send Grades, and staff-enrolled programs

**Date:** 2026-09-29
**Status:** Accepted 2026-09-29
**Supersedes:** 083 §3 (Advance Students message) and §4 (Advance Students by program step);
narrows 083 §1 to staff-enrolled programs.

## Context

083 kept the registrar's Advance Students button and gated it on grades. The button exists only
because 008 split billing away from term rollover. Nobody decided that advancing needs a person, and
the grades already say whether a student moved on. `Program Enrollment.current_std_term` also has
no stated meaning. Every reader uses it as the curriculum stage: which term's planned courses a
student may take (`courses_for_student`, the bulk run, the gaps report), and the Time-based
graduation check. Terms since intake and terms attended are not used anywhere. Both can be worked
out from records. Finally, programs differ in who enrolls students. Some schools want every
student enrolled by staff.

## Decision

1. **`current_std_term` is the curriculum stage**, and it means only that. Terms elapsed and
   terms attended are worked out from records when something needs them, never stored.
2. **Send Grades advances the student.** When a student's last grade in an Academic Term is sent,
   the program's rule decides whether they move to the next stage. "Last" means the student
   has no other live, ungraded enrollment in a dated section of that term. An open-ended
   section (065) never holds this back; a course shared with a self-paced program can put one
   on a Time-based student's schedule. The stage only moves forward, stops at
   `terms_complete`, and moves at most once per Academic Term (`advanced_from_term`, from 083).
   A student with no grades in a term, such as one on leave, stays where they are.
3. **Program → "Advance to next term when"** (Select, Time-based only, in the program-type
   section):
   - *At least one course is passed* (default). A student who failed everything they took
     that term stays.
   - *Every course is passed.*
   - *The registrar advances*: never automatic.
4. **The registrar can change one student's term.** A **Change Term** action on the Program
   Enrollment moves the stage up or down and needs a reason, which goes in the timeline. It
   covers held-back students the school lets continue, advanced standing (058), and the
   *registrar advances* rule. The Advance Students dialog and its workspace block are retired.
5. **Program → "Staff enroll students in courses"** (Check). When it is on:
   - `registrar_block_cei` is cleared and hidden, since it adds nothing here;
   - students of this program cannot enroll themselves on the portal, even when
     `allow_portal_enroll` is on. The server refuses, and the portal says the school enrolls
     them;
   - Bulk Course Enrollment (083 §1) accepts only Time-based programs with this check on.
6. **Program → "Enroll students in their next term's courses when they advance"** (Check,
   shown only with §5 on). When §2 advances a student, they are enrolled in the new stage's
   courses in the next Academic Term. The section is chosen the way 035 chooses one. A section
   not open yet enrolls them when it opens (035's backfill). Anything that can't be done shows
   in the gaps report.
7. **`cohort_failure_policy` becomes "When a student is held back"** (Time-based only; no code
   reads it today):
   - *Stay in the current cohort* (default): nothing happens.
   - *Remove from the current program cohort*: when §2 holds the student back, their active
     membership in the program's `Paced Program` cohort (066) is set to Removed. Staff place
     them by hand or with the Cohort Planner (067).

   Existing values are mapped to the default.
8. **Self-paced is for Credits-based programs only.** A Time-based program moves by terms, which a
   self-paced student doesn't. Program refuses `pacing_mode = Self-paced` with
   `program_type = Time-based`. An existing program with that combination is listed in the
   Error Log by the patch and is not changed.

**Rejected: work the stage out from grades every time, never storing it.** Nothing would need to
advance at all. But a course added to an earlier term's plan would move students back, and a
registrar's exception would have nowhere to live.

## Consequences

Terms move with the grades, with no button to forget or press twice. A school sets once per
program how strict progression is and who enrolls students. Bulk runs and auto-enrollment both
follow grades. A school that registers students before the current term's grades are sent has no
path yet; that needs its own decision. Advanced standing still starts every student at stage 1,
and the registrar changes it by hand.
