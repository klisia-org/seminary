# 097 — Course discussions: threads, notifications and unread

**Date:** 2026-10-31
**Status:** Accepted 2026-10-31
**Delivers:** LMS-COL-01 (Yes)
**Related:** 021 (anchored comments), 064 (Community), 082 (two due dates), 095 (rubrics)

## Context

Graded discussions (Discussion Activity) already have grades, rubrics (095), two due dates (082),
a minimum reply count, "post before reply" and student groups. Three things keep LMS-COL-01 at
Partial. The two settings were kept only in the browser. A reply cannot be answered, so the student
who posted and the instructor cannot talk back and forth. Nobody is told about a reply, and nothing
shows what is new. Canvas, Moodle and Brightspace have all three, and a reviewer checks them.

## Decision

1. **The server keeps the settings.** With "post before reply", a student sees no classmate's post
   until they have posted. With student groups, they see and answer only their own group's posts.
   Staff see everything. Built ahead of this record as a fix.
2. **Replies can be answered.** `Discussion Submission Replies` gains `in_reply_to`, the reply it
   answers (empty means it answers the post). Replies stay in the post's child table and are shown
   nested three levels deep, with deeper answers shown flat at the third level. Who may answer a
   reply follows §1.
3. **Counting does not change.** The minimum reply count still counts the classmates' posts a
   student replied to, at any depth, and their own post never counts. 082's missing-reply
   deduction reads the same rule.
4. **Instructor replies are marked.** A reply by one of the section's instructors carries an
   *Instructor* badge. It never counts toward a reply minimum.
5. **The person answered is told.** A reply sends one in-app notice through `comms.send()` to the
   author of the post or reply it answers, following their notification settings. Nothing is sent
   for your own replies, and instructors are not told about every post.
6. **What is new.** `Discussion Read State` (user, section, activity, last seen) keeps when a person
   last opened a discussion. The discussion list shows a count of unread posts and replies, and new
   ones are marked in the thread. This uses the same last-seen pattern as Community (064 §7), not a
   row for each reply.
7. **Lesson questions stay as they are:** ungraded, one thread per lesson. They gain §5 only: the
   person who asked is told when someone answers.

## Consequences

A graded discussion becomes a real thread, and nothing about grading or due dates moves. Deleting or editing a reply after it is sent is left out for now.
