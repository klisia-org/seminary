# 051a — School meeting accounts

**Date:** 2026-11-20
**Status:** Accepted
**Amends:** [051](051-per-meeting-room-virtual-and-attendance.md) (#2 per-meeting virtual meeting)
**Related:** 038 (overlap), 092 (hooks for other apps), 100d (capture from virtual meetings)

## Context

A join link today is text an instructor pastes, usually from their own Zoom. Seminary cannot
schedule, change or record a meeting it did not create, and connecting every instructor's personal
account is neither possible nor the school's to govern. Schools that pay for meeting licences
want sections to get a link without anyone pasting it, and two classes at 7 pm must not land on
the same licensed host, which can run only one or two meetings at once.

## Decision

1. **Web Meeting Account**, a school list: `label`, `provider`, `host_id` (the provider's user,
   e.g. a licensed Zoom user's email), `max_concurrent` (default 1) and `enabled`. Seminary holds
   no credentials; the app that provides the provider holds them, once per school.
2. **Providers come from a hook**, `meeting_providers`, `{provider: "dotted.path"}`, whose object
   creates, updates and deletes a meeting and returns its `join_url`, `meeting_id` and a host key.
   With no app providing one, the list is empty and 051 is unchanged.
3. **A toggle, not a link.** A section, or a single meeting row, sets `school_meeting`. The
   meeting row's `cs_web_meeting` is then filled and read-only, and the row stores
   `cs_meeting_account` and `cs_meeting_id`. Off, the pasted link of 051 works as before and that
   meeting is never managed or captured.
4. **An account is a room.** Seminary picks an enabled account free for the meeting's window,
   counting overlaps (038 `times_overlap`) up to `max_concurrent`. When none is free the save is
   blocked, naming the clashing sections, as a double-booked room is.
5. **One provider meeting per meeting row.** Time changes update it; a deleted or cancelled row
   deletes it. Calls run after commit in the background; a failure shows on the row and leaves
   the previous link. A standing link per section was rejected: students like it, but a recording
   could then only be matched to a meeting by its clock, and concurrency could not be checked.
6. **Hosting.** An instructor of record whose email is a user in the account is made an
   alternative host; otherwise the host key shows to the section's instructors only, never to
   students.

## Consequences

- Registrars stop collecting links, and host clashes surface at scheduling, not at 7:01.
- The school buys as many licences as it has overlapping online classes; the clash message
  shows when it has too few.
- Only meetings Seminary created can be captured by account (100d); a pasted link needs a bot.
- Open: a reusable account pool per campus; managed meetings for advising and office hours.
