# 101 — Community: channels by cohort type, reactions by channel, cohort meetings

**Date:** 2026-11-21
**Status:** Accepted 2026-11-21; implemented 2026-11-21
**Amends:** [064](064-discipleship-cohorts-and-channels.md) §2 (channels, reactions, prayer)
**Related:** 051a (school meeting accounts), 100d-a (time zones, invites), 043 (comms ledger), 038 (overlap)

## Context

Every enabled channel shows in every cohort, so a faculty development cohort cannot have its own
channels (student engagement, assignments and rubrics) without students seeing them too. 064
planned `default_channels` on Cohort Type but it was never built. Reactions are one catalog for
all channels, so *Insightful* shows on a prayer request. Praying for someone leaves no trace for
the one praying. Cohorts meet, but agreeing on a time happens outside Seminary, and nobody is
reminded. The page itself shows its filters as loose rows and puts the cohort in a dropdown.

## Decision

### 1. Channels by cohort type

1. **Cohort Type Channel**, a child table on Cohort Type (Table MultiSelect of Cohort Channel). A
   cohort offers its type's channels; a type needs at least one.
2. **Cohort Channel** drops `icon` and gains `is_default`. A new Cohort Type starts with the
   default channels, which staff then trim or extend.
3. A post's channel must be one its cohort's type offers. Readers see posts only in channels
   that one of their own cohorts offers, whatever the post's visibility, so a *Whole community*
   post in a faculty channel never reaches students.
4. A patch gives every existing type all enabled channels and marks them all default, so
   nothing disappears on upgrade.

### 2. Reactions by channel

1. **Cohort Channel Reaction**, a child table on Cohort Channel (Table MultiSelect of Cohort
   Reaction Type): the reactions offered on that channel's posts and comments. The patch gives
   every channel all enabled reactions; new installs seed them by channel kind (prayer: Pray,
   Amen; exegesis: Insightful, Like).
2. Each reaction shows its count; hovering or pressing it lists who reacted.
3. **Cohort Reaction Type** gains `saves_post` ("Reacting also saves the post"), seeded on for
   *Pray*.

### 3. Pray saves the request

1. Reacting with a `saves_post` reaction creates a Cohort Post Save marked `via_reaction`.
2. In **Saved**, prayer posts show under *Praying for* while unanswered and under *Answered*
   once the author marks them answered.
3. Removing the reaction removes the save it created. Unsaving keeps the reaction: the person
   did pray. Neither ever changes the post or its answered status, which stays the author's.
4. **Answered.** When the author marks a prayer answered, everyone who reacted with a
   `saves_post` reaction, saved or not, gets a portal notification and an email with the
   answer note, if the post's visibility still lets them read it.

### 4. Cohort meetings

1. **Cohort Meeting** (standalone): `cohort`, `title`, `mode` (Virtual / In person),
   `starts_on`, `ends_on`, `status` (Polling / Scheduled / Cancelled), `link`, `location`
   (text, in person), `school_meeting` with `meeting_account` and `meeting_id`, and `series`.
   Only the cohort's leader (064 §1) creates, changes or cancels one; members see their
   cohorts' meetings.
2. **Two ways to schedule.**
   - *Poll*: the leader offers options (child **Cohort Meeting Option**) and a required
     `poll_closes_on`. Members answer each with Yes / If need be / No (standalone **Cohort
     Meeting Vote**, one per person and option, so a member writes only their own). Each
     option also shows the members who have a class meeting then (038), named to the leader.
     Members who have not voted are reminded 24 hours before the poll closes, and the leader is
     told when it closes. The leader sees the tallies and who cannot come, then picks one,
     before or after the close; the meeting becomes Scheduled and the options are kept.
   - *Direct*: the leader sets the time, once or as a repeating series (weekly, every two
     weeks, monthly; until a date or for a count). A series is separate meetings sharing a
     `series`, each movable or cancellable on its own; *cancel the rest* ends a series.
3. **Time zones.** Options, votes and meetings show in each member's own time (100d-a §9).
4. **Link.**
   - Virtual: the leader pastes their own link.
   - Cohort Type gains `school_meeting_allowed`. Where on, such as for a faculty cohort, the
     leader may tick *Use a school meeting account* instead. The link is then created as in
     051a: an account is a room, counted with class and group meetings, and a clash blocks
     scheduling and names it.
   - In person: `location` replaces the link.
5. **Invites and reminders.** Scheduling, moving and cancelling send each member a portal
   notification and an email with a calendar invite, as 100d-a does. Reminders are
   Communication Logs (043) queued with `scheduled_at` at the hours in the cohort type's
   **Cohort Type Meeting Reminder** rows (`hours_before`; new types start with 24 and 1, and
   no rows means no reminders). Moving or cancelling a meeting cancels its queued reminders
   and queues new ones. Links go only to members.
6. **Calendar feed.** Each cohort has a subscribable feed of its meetings, built and guarded as
   a section's is (a `calendar_token`, checked in constant time, rate limited). Cohort Type
   gains `meetings_in_calendar_feed`, on by default; off, the cohort has no feed and members
   rely on the invites. A member subscribes from the cohort's row.
7. **Attendance.** Once a meeting has started, the leader marks each member Present, Absent or
   Excused (child **Cohort Meeting Attendance**, filled from the active memberships when the
   meeting is scheduled). It is the cohort's own record: it does not touch class attendance or
   grades. The leader and the cohort's mentors see all of it; a member sees their own.
8. **No new dependency.** `ics` already builds invites, `dateutil.rrule` (with Frappe) expands
   series, and the comms ledger sends reminders. Poll services and self-hosted schedulers
   (Rallly, Cal.com) were rejected: they don't know cohort membership, members' time zones or
   school meeting accounts, and they would be another server to run, with links outside
   Seminary.

### 5. The page

The redesign keeps today's capabilities and changes how they are reached:

1. **Rail.** A left rail lists *All my cohorts* and each cohort (type, member count, unread
   count from the feed read state), replacing the cohort dropdown. A cohort's members, its
   meetings and its calendar feed open from its row, replacing the *My cohort* button. Below,
   under **Channels** (the mock's "Topics"; post topics keep that name), are the channels on
   offer, with post counts. The rail remembers the viewer's last selection in the browser,
   replacing the default-cohort star.
2. **Header.** The header names the selection and what is new since the last visit
   ("5 new since Thursday"). Its actions become labelled buttons: *Announce*, *Moderation · N*
   (open flags), *New post*.
3. **Filters.** One row holds search, a *Passage* picker (books tagged in posts, or all 66,
   chapters with counts, or a typed reference), a channel picker, and *All / Saved / Mine*.
4. **Posts.** A post card shows the author's initials, its channel, and its passage folded
   behind *Show passage*. A filtered list ends with a note of matching posts in other channels,
   e.g. "2 more posts about John 11 in Sermon Lab and Prayer".
5. **Phones.** The rail folds into a selector above the feed.
6. **New post.** The cohort is picked from cards (type, member count) and the channel from that
   cohort's channels as chips. Topics are typed as chips; suggestions are existing topics on
   posts the author can read, with how many use each, so a topic seen only on others' private
   posts is never offered. *Who can see this* sits beside *Post*, each choice saying who that
   is ("6 members of Faculty Development").

## Consequences

- Faculty and student cohorts each get their own channels, and a channel's audience follows
  from the cohort type.
- Each channel offers reactions that fit it, with counts. Someone who reacts *Pray* keeps
  the request in Saved until it is answered.
- Cohorts agree on and keep their meeting times inside Seminary, with invites and reminders.
- Members need not be students. An invited pastor or a staff member with no classes never shows
  a class clash; someone who has not signed in yet gets email only, and their time zone shows as
  unknown.
- Where a type allows school accounts, cohort meetings count against the same licences as
  classes.
- Upgrades change nothing visible until staff trim channels and reactions.
- A cohort's feed URL, like a section's, lets anyone holding it read the meetings and links.
- Open: online meeting attendance read from a school account's participant list (100d), if
  leaders ask for it.
