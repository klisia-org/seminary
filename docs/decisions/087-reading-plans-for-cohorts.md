# 087 — Reading plans for cohorts

**Date:** 2026-10-12
**Status:** Accepted 2026-10-12
**Related:** 041 (course packs), 064 (cohorts, verse ordinals), 066 (mentoring cohorts)

## Context

Cohorts (064) post, comment and pray together, but cannot read together. Mentors want a cohort to
work through *Romans in 10 days* or a book's chapters at its own pace, and to reuse the same plan
with the next cohort. A plan carries no dates; the cohort that runs it supplies them. Plans are
worth sharing between schools, as courses are through course packs (041).

## Decision

1. **Reading Plan** holds the content and nothing about time: `title`, `plan_type` (Bible / Other),
   `description`, `is_standard`, and a child table of **Reading Plan Step**.
2. **Reading Plan Step**:
   - `step` (Int) is set from row order on save (1, 2, …) and is read-only.
   - Bible: `from_book`, `from_chapter`, `from_verse`, `to_book`, `to_chapter`, `to_verse`.
     Books are OSIS codes, so a plan is language-neutral and names render in the reader's language.
     An empty verse means the whole chapter. Ranges may cross chapters and books. On save the step
     derives `verse_start_ord` / `verse_end_ord` with `verse_ordinal()` (064 §4) and refuses an
     end before the start.
   - Other: `reading_text` (e.g. *Chapter 1 of Bonhoeffer, Life Together*), `attachment`,
     `link_url`. At least one is required.
   - Both: `message`, an optional rich-text note for comments or questions.
3. **Authoring.** Cohort leaders (an active `is_leader` membership, 064 §1) create and edit plans in
   the portal; staff do the same on Desk. Every leader can see every plan and start it for their own
   cohort. A plan's author and staff can edit it.
4. **Shipped plans.** Seminary ships a few Bible plans (such as *Romans in 10 days* and *Mark in
   16 days*). The install creates them if they are missing, with `is_standard` set. A standard plan
   is read-only. A leader duplicates it to change it.
5. **Steps lock once a plan is used.** After any Cohort Reading Plan points to a plan, its steps
   cannot be added, removed, reordered or changed, except for `message`, which stays editable. A
   leader can start a plan and keep writing the questions as the cohort reads. To change the
   readings, the leader duplicates the plan.
6. **Cohort Reading Plan** is a cohort running a plan: `cohort`, `reading_plan`, `start_date`,
   `status` (Active / Completed / Cancelled), and the reading days as weekday checks (`monday` …
   `sunday`), as Course Schedule does for meeting days. Step 1 falls on the first checked day on or
   after `start_date`, and each later step on the next checked day. Dates are computed and never
   stored, so changing the days moves every step not yet due. Checking every day makes the plan
   daily. A cohort may run more than one plan at once. `skip_public_holidays` (off by default) moves
   a step off any day `holidays.is_holiday()` reports for the site's country. School breaks are
   not modelled yet. When they are, they get a separate toggle, because breaks don't apply to
   alumni cohorts.
7. **Progress.** **Reading Plan Progress** records `cohort_reading_plan`, `person`, `step` and
   `read_on`, one row per member and step. A member marks a step as read on the cohort's portal
   page, in any order, and can unmark it. The leader sees a member-by-step grid. A member is
   *behind* when a step whose date has passed is not marked.
8. **Reminders only when a member falls behind.** A daily job looks at each Active run's step
   whose date was yesterday. A member who has not read it, and had read every earlier due step,
   gets one notice that names the unread steps and links to the cohort's page. A member who stays
   behind is not reminded again until they catch up and fall behind once more. Members who are up
   to date get nothing. No reminder state is stored.
9. **Discussion is one click, never automatic.** A *Discuss* action on a step opens a draft Cohort
   Post for the cohort. It fills `reference_doctype` / `reference_name` with the Cohort Reading Plan,
   a title naming the step, the step's scripture refs (Bible steps) and its message as the body. The
   member edits it, picks the channel and publishes. Nothing posts on its own.
10. The cohort's portal page shows today's step, the plan so far and the member's own marks. A Bible
    step opens the passage through the existing Bible integration in the reader's preferred version.
11. **Sharing** follows 041. A plan can be exported as a `.zip` (manifest plus attachments) and
    imported as a new, editable, non-standard plan, with the title made unique. The import keeps
    041's trust rules: the pack is untrusted input, field allow-lists apply in both directions, size
    bounds are checked before parsing, and media is stored private.

## Consequences

- One plan serves any number of cohorts and schools. Its dates belong to the cohort.
- Because Bible steps store ordinals, posts that touch a step's passage can be found with 064's
  overlap query.
- Locking keeps every member's progress pointing at the reading they actually did. The cost is
  that fixing a typo in a used reading means duplicating the plan.
- Packs carry no cohort, member, progress or date, so nothing personal leaves the school.
- A new step field reaches packs only once it is added to the allow-list (as in 041).
