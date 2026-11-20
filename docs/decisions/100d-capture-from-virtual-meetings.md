# 100d — Capture from virtual meetings

**Date:** 2026-11-20
**Status:** Accepted
**Parent:** [100](100-oral-assessment.md)
**Related:** 051 and 051a (virtual meetings, school meeting accounts), 100b (peer conversations)

## Context

Many seminars and case discussions already happen in Zoom, Meet or Teams. Recording them on one
student's browser (100b §3) loses the others' voices and the classroom's own setup. Providers
record well and can give one audio track per participant, which settles who spoke when without
guessing. Most class meetings are not assessed, though, and recording or analysing them all would
cost money and collect talk nobody will grade.

## Decision

1. **The activity decides, not the meeting.** An Oral Activity (100b) may set `capture` to
   *Virtual meeting* and name one `meeting` (a Course Schedule Meeting Dates row of its section).
   Only meetings named this way are captured; Seminary refuses a recording for any other.
2. **Capture methods come from a hook**, `meeting_capture`, `{method: "dotted.path"}`, chosen per
   activity from those the site provides and the school allows in Seminary Settings:
   - *Account*: the provider that created the meeting under a school account (051a) sends its
     recording; works only for managed meetings;
   - *Bot*: a recorder joins any meeting link by name and leaves when it ends; works for pasted
     links and for providers Seminary has no account for.
   A method is asked to arm before the meeting starts and calls
   `seminary.oral.meeting_recorded(meeting, result)` when it has the audio.
3. **Audio only.** The result carries mixed audio, a track per participant when the provider gives
   one, each participant's name and email, and server start and end times. Seminary stores the
   audio as private files; video stays with the provider.
4. **One recording, many submissions**, as 100b §2. A participant whose email belongs to a student
   on the section is linked to their submission and counted present. Each track becomes an Oral
   Speaker with its own `audio`, so `diarize` is skipped; a mixed-only result goes to `diarize` with
   the matched participants as expected speakers. A name with no email match stays *Suggested*.
5. **Notice (100 §7).** The activity, the meeting row and the calendar show that the meeting is
   recorded for assessment; the provider's own recording notice or the bot's name in the
   participant list shows it during the call.
6. **Breakout rooms are groups.** For a *Conversation* activity, each breakout room is a 100b
   group: the result carries a recording per room with its participants, and each room becomes its
   own Oral Recording shared by that room's submissions. Providers often record only the main room,
   so a method that cannot record rooms is not offered for an activity that uses them.
7. **Attendance is suggested.** The matched participants, with join and leave times, propose
   attendance on the meeting row (051 #4) as *Suggested*; the instructor confirms it as they mark
   attendance today.
8. **Retention (100 §8)** applies to Seminary's copy. The provider's copy is the school's.
9. **No live defense.** A defense led by the instructor in a meeting is graded while it happens and
   needs no recording; a student presentation is an Oral Activity captured like any other.

## Consequences

- A live seminar is graded like a recorded one, with exact talk time when tracks are available.
- Unassessed meetings cost nothing and leave nothing in Seminary.
- A bot's cost per hour falls only on assessed meetings; the app providing it reports usage.
- Students joining from a phone number or a guest name cannot be matched until someone labels them.
- Instructors get attendance for captured meetings without calling the roll.
- Open: suggesting attendance for every managed meeting (051a), not only captured ones.
