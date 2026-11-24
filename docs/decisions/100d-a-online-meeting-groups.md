# 100d-a — Online meeting groups

**Date:** 2026-11-21
**Status:** Accepted 2026-11-21; implemented 2026-11-21 (420f0983)
**Amends:** [100d](100d-capture-from-virtual-meetings.md) §1, §5, §7
**Related:** 051a (school meeting accounts), 097 (student groups), 038 (overlap)

## Context

100d captures an oral activity in a section's class meetings, which everyone sees. Group
presentations are usually not that: 21 students in groups of 3 means 7 short meetings, each for
its own group. As section meetings, every student would see all 7 in their calendar, not know
which is theirs, and could join the others'. Creating 7 meetings one by one, and finding times
that suit each group, is also tedious.

## Decision

1. **Two ways to capture**, chosen on the section for an activity whose `capture` is *Virtual
   meeting*:
   - *In a whole class meeting* (100d as it stands): a Course Schedule meeting that everyone attends;
   - *Group meetings*: each group gets its own meeting. Group meetings are never Course Schedule
     Meeting Dates.
2. **Configure Meetings.** For instructors, the activity in the lesson has a **Configure
   meetings** button, opening one page per section and activity.
3. **Groups.** The page lists the section's non-audit students, grouped by their student groups
   (097) when the section has any. The instructor either:
   - uses the section's student groups; or
   - makes groups for this activity only, by hand or by size, as student groups are made. These
     groups are kept on the meetings, not as Student Groups, so discussions and other
     activities are unaffected.

   Each student shows with their time zone and local time (§9). *By size* can keep nearby time
   zones together, so students in China, Australia, London and the Americas are not put in one
   group.
4. **An Oral Activity Meeting holds its own meeting.** It gains a date, from and to times, the
   link, and the expected students (its group). With school meeting accounts, the link is
   created as in 051a: an account is a room, counted with class meetings. Without them, the
   instructor pastes a link per meeting or one link for all.
5. **Suggested times.** The instructor gives:
   - a date range;
   - the weekdays and daily hours to use (e.g. Monday to Friday, 9:00 to 17:00);
   - each meeting's length and the break between meetings;
   - **I attend each meeting** (on by default).

   Seminary fills one slot per group, in order. A slot is refused when:
   - one of the group's students has another class meeting then (038);
   - no meeting account is free (051a);
   - with *I attend* on, the instructor has a class or another of these meetings then. Off,
     groups may meet at once, up to the free accounts, and are graded from the recording.

   With *I attend* off, the daily hours are read in each student's time zone, so 9:00 to 17:00
   means their 9:00 to 17:00. When no slot fits every member, nobody is left out. Seminary takes
   the slot that is closest for the group as a whole: the one with the least total time outside
   members' hours. So a lone student in China may meet at 7:00 their time, and their group at
   19:00 its time. Such a slot is marked and explained to the instructor, e.g. "7:00 for Li
   (Shanghai), 2 hours before her day; no slot fits all four". The instructor may still move it.

   Each slot shows in the instructor's time and in each member's.

   The instructor can move any slot, then creates all the meetings in one step. Each meeting is
   checked again under a lock as it is created; one that clashes is left unscheduled and named,
   and the rest are created.
6. **Only the group sees its meeting (§5 amended).** A student sees their own group's meeting
   (time, link, the recording notice) on the activity and on their course calendar, and is sent
   it as a portal notification and an email with a calendar invite. Others' links are never
   sent to them. The section's calendar feed, shared by all, does not carry group meetings.
7. **Changes.** The instructor's schedule stands; groups do not book or swap slots themselves. A
   student who cannot make it asks the instructor. Moving a meeting, or moving a student to
   another group before the meeting, updates the provider's meeting and the capture (100d §2).
   It also tells the students affected.
8. **Attendance (§7 amended).** A group meeting is not a class meeting and takes no attendance.
   A student who misses their group's meeting has no submission; the instructor can give them
   another meeting.

9. **Students' time zones.** Frappe's User has a `time_zone`, but it is filled with the site's
   own zone when the account is made, so it says nothing about the student. The portal reads the
   browser's zone when a student signs in:
   - while the stored zone is still the site default, the portal writes the browser's zone;
   - when it differs from a zone the student already has, the student is asked whether to
     change it;
   - the student can change it on their profile.

   A student with no zone of their own is shown as *unknown*, and their hours are not checked.
   The same zone shows their own meeting in their time (§6).

## Consequences

- Each student knows the one meeting that is theirs, and a class of 21 is scheduled in one step.
- Students spread across the world are grouped and scheduled in their own daytime.
- A student's time zone tells staff roughly where they are; it is the zone their own device
  reports, and they can change it.
- Licence clashes are found at scheduling, together with class meetings.
- Group meetings do not reach subscribed calendars except through each student's own invite.
- Open: groups booking their own slots, if instructors ask for it.
