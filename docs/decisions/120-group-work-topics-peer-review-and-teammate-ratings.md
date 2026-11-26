# 120 — Group work, topics, peer review and teammate ratings

**Date:** 2026-11-26
**Status:** Accepted 2026-11-26; implemented 2026-11-26
**Delivers:** LMS-ASM-07 (Yes), LMS-ASM-08 (Yes)
**Amends:** 100d-a §3 (groups for one activity become Activity Groups), 100b §1 (a
conversation's groups are Activity Groups, not section student groups)
**Related:** 021 (inline submissions, timestamp comments), 082 (due dates), 095 (rubrics), 097
(student groups), 100 and 100b (oral activities), 119 (grade freeze)

## Context

An assignment is submitted and graded per student. Group work exists only in discussions (097)
and oral conversations (100b, 100d-a). A section's student groups split grading between
instructors, so they are the wrong shape for project teams. Instructors hand out topics by email:
a different topic per presentation group, or a book chapter per doctoral student. Students never
review each other's work or sermons, and the instructor of a group project cannot tell who did it.
Peer review and teammate ratings share one mechanism: students assigned to assess other students,
due by a date, then released. We build all of it together.

## Decision

1. **Settings** on Assignment Activity and Oral Activity, copied with the course template:
   - `group_work` (on Oral Activity, the *Conversation* mode), with a `group_source`: *Section
     groups*, *By hand*, *Random* (with a size) or *Self sign-up* (with a maximum size and a close
     date);
   - `topics` (§3) and how they are given: *By hand*, *Random* or *Students choose* (with a close
     date);
   - `peer_review`: `reviews_per_student`, `review_opens` (*At the due date*, *At the cut-off* or
     *By hand*), `review_due` (days after it opens), `review_anonymous` (off by default) and
     `review_form` (*Rubric* when the activity has one, or *Comments only*);
   - `teammate_ratings` (group work only), with `ratings_shown`: *Named* (the default),
     *Anonymous* or *Instructor only*;
   - `review_share`: the percent of the grade that review work earns (§7).
2. **Activity Group** is a new doctype: a Course Schedule, `activity_doctype` + `activity`, a name,
   a `topic` and `members` (Student, `joined_on`, `left_on`). Groups are made per section and
   activity, beside the section's student groups, which keep splitting grading. *Section groups*
   copies them when the activity opens, and the copy can then be edited. Audit students are left
   out, as in 100d-a. Self sign-up closes at its date, and the instructor places anyone left over.
   The groups 100d-a made for one activity only become Activity Groups, and its meetings point to
   them.
3. **Topics.** `Activity Topic` holds a section's topics for one activity: Course Schedule,
   `activity_doctype` + `activity`, `title`, `description` and `capacity` (default 1, so each
   topic goes to one group or student). Activities are shared by the sections of a course, so
   topics are kept per section: the template import copies them, and the section then changes them
   freely. With group work the topic belongs to the group. Without it, each student holds one
   through a `Topic Choice` (Course Schedule, activity, student, topic). With *Students choose*,
   students take a free topic first come, first served, under a lock, and can change it until the
   close date. The instructor sees who has which topic and places anyone left without one. The
   topic shows on the submission, the grading page and the gradebook cell.
4. **One assignment submission, a record per member.** Any member submits. The answer and file
   are saved on every member's Assignment Submission, with `activity_group` set. A later
   submission replaces the earlier one for the whole group. The instructor grades once: the
   grade, rubric score (095), comments and thread are copied to each member. An override changes
   one member's grade alone and is marked on that record. Gradebook, outcomes (077) and the freeze
   (119) stay per student. Group conversations keep their per-student grading (100b).
   - Lateness is measured against the activity's due date. *Extend for the group* creates an
     082 override for each member in one step. One member's own override does not move the group.
   - A member who leaves keeps the submission and grade as they were when they left. A member who
     joins gets the group's current submission.
   - The grader is the section-group instructor all members share, and otherwise the section's
     instructors.
5. **Peer review.** When review opens, Seminary assigns each submitter `reviews_per_student`
   submissions:
   - never their own or their group's;
   - spread evenly, so each submission gets about the same number of reviews;
   - in group work each member reviews other groups' work on their own.

   A submission made after review opens joins the pool, and reviewers who have finished are
   offered it as an extra. The instructor sees every submission short of reviews and reassigns
   with one click. Reviewers fill the rubric (without points) or write comments, and may attach
   a file: the author's work marked up in their own editor, so reviewers never edit the
   submission. On an oral
   activity, such as a sermon, they listen to the recording beside its transcript and can anchor
   a comment to a moment in it. Those comments are kept with the review, not as Oral Moments, so
   the instructor's grading marks stay theirs. Names show both ways unless `review_anonymous` is
   on. The author sees the reviews at `review_due`, or earlier when the instructor releases them.
   The instructor can hide a review, and a hidden review still counts for the reviewer unless the
   instructor withdraws its credit.
6. **Teammate ratings.** After the due date, each member rates every other member of their group
   with a short form. Its criteria live in Seminary Settings (`teammate_rating_criteria`): by
   default *contributed their share*, *met commitments* and *worked well with others*, each 1–5,
   plus a comment. Teammates see the ratings they received at `review_due`, *Named* or
   *Anonymous*, unless they are shown to the instructor only. Rating a teammate honestly, under
   one's own name, is part of formation, so *Named* is the default. Next to the group grade, the
   instructor sees each member's average, the spread and the comments. Ratings never change a
   grade by themselves; they are evidence for the per-member override.
7. **Review work is part of the activity's grade.** The grade is (100 − `review_share`)% from the
   work and `review_share`% from completing the assigned reviews and ratings by `review_due`.
   Each assessment that was due counts equally. The instructor can change the review part for one
   student, for example when a review is careless. Students see both parts. A `review_share` of 0
   makes reviewing ungraded.
8. **Where it shows.** The activity page shows the topic, the group, its members and the shared
   submission. The course card and outline carry a *Reviews to do* count. Instructors see a group
   grading view, a topic board and a review progress page per section. Notices for groups made,
   topics given, reviews assigned, reviews released and ratings due go through comms (043). The
   section's observers (105) see the same as its instructors, read-only.
9. **A hook for a group workspace.** `activity_group_changed` (doc, event) fires when a group is
   created, changes members or closes. An installed app can use it to give each group a
   workspace. Seminary itself ships no workspace.

Rejected: one submission row with a members table. Every grade report, rubric score, outcome
query and freeze reads one student per submission, so all of them would need a group branch.
Ratings that adjust grades by formula (as in WebPA): they are opaque to students and turn
perception into a number nobody chose.

## Consequences

- Schools get group projects, topic sign-up, peer review of papers and sermons, and contribution
  checks inside the activities they already use, with one grade per student throughout.
- Instructors grade a group once and adjust only the exceptions, and the ratings tell them where.
- Saving the submission on each member's record duplicates text, never files.
- Review credit makes reviewing worth doing but adds a grade part students must understand.
- Discussions get no peer review: replying to each other is already the review.
- Open: sharing a reviewed sermon to a cohort's Sermon Lab channel (064).

## Found in implementation

- **Close dates are per section.** Sign-up and topic choice close on the assessment row
  (`signup_closes_on`, `topics_close_on`), as do the round's `review_opened_on`, `review_due_on`
  and `reviews_released_on`, because the activity is shared by sections.
- **Copying is for assignments only.** A conversation already gives every participant their own
  record and grade from one recording (100b), so §4's copy would undo talk-time grading. Its
  groups are Activity Groups; section Student Groups are no longer made for it.
- **The comment thread is read, not copied.** The grader's anchored comments are shown from every
  member's record, which keeps editing and deleting a comment simple.
- **Observers do not get these pages.** 105 §5 keeps student lists from observers, and every page
  here lists students. §8's "observers see the same" gives way to it.
- **Nothing asked, nothing taken.** A student given no reviews or ratings keeps the whole grade
  on the work. Ratings count once every criterion has a score.
- **Reviewers never read the submission.** Files come through a checked download; a recording is
  readable by its reviewers, with the speakers' names hidden.
- **Allocation.** At opening, individual work uses a shuffled ring, so every piece gets exactly
  *n* reviews. Group work and late work are filled greedily, the least-reviewed first.
- **Hook events** are `created`, `members`, `topic` and `deleted`; there is no "closes" event.
- **Not built:** the topic in the gradebook cell (it shows in the submissions list and on the
  grading page).
