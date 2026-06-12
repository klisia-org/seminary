# Announcements

Seminary Announcements let you send a single message to everyone enrolled this term, everyone teaching this term, all alumni, or any combination you need. Messages are delivered over the channels you choose — email and the in-app inbox by default, with SMS, WhatsApp, and Telegram available for urgent reach. Recipients are resolved from live data at send time, so students who enroll or drop between compose and send are picked up correctly.

## When to use it

- Deadline reminders (drop dates, exam windows, grade submission).
- Campus or calendar changes (closures, holidays, schedule shifts).
- Policy or administrative notices that need to reach a whole audience at once.

For messages scoped to a single course (one class of students + their instructor), use the course's own **Announcements** panel inside the course page. Seminary Announcements are for audiences that span multiple classes.

---

## Who can send

The **Academics User** role can create, submit, and cancel Seminary Announcements. Students and instructors can read the announcements they received, but cannot compose.

---

## Creating an announcement

Open **Desk → Seminary Announcement → New**.

### 1. Subject, category, and message

- **Subject** — the email/message subject line. Keep it short and specific: "Midterm week — building closure Friday" is better than "Important announcement".
- **Academic Term** — required when the audience is term-scoped (enrolled students, teaching instructors, or specific course schedules); optional for an all-alumni or custom-filter broadcast. Defaults to the current term.
- **Category** — the routing/consent class (default **Academic**). Most announcements are Academic. Choose **Emergency** for a genuine calamity (campus closure, safety alert): Emergency messages **bypass recipient opt-outs and the hourly send throttle** so they reach everyone at once. Promotional messages only reach recipients who have opted in.
- **Send via channels** — leave empty to send **Email + In-App** (the default). Add **SMS**, **WhatsApp**, **Telegram** (urgent reach), **Voice** (an automated call that reads the message), or **Print** (a PDF letter to mail). Each needs a configured provider account — see [Communication](communication.md); Print works out of the box. Submit is blocked if you pick a channel with no provider account configured.
- **Message** — the body. Full rich-text: headings, lists, links, bold, inline images. Used for Email, In-App, **and Print** (the printed letter). You can personalize it with Jinja tokens that resolve per recipient: `{{ recipient.first_name }}`, `{{ recipient.name }}`, `{{ recipient.email }}` (and `{{ person.* }}` for spine fields). Example: *"Dear {{ recipient.first_name }},"*. Syntax errors are caught when you save.
- **Voice Recording** — *(shown when Voice is selected)* an optional MP3/WAV the call plays instead of reading the text aloud (e.g. the director records the message). Up to ~40 MB; the file is made public so the carrier can fetch it.
- **Short Message** — a plain-text version for the length-limited / spoken channels (SMS, WhatsApp, Telegram, Voice). Leave it blank and the system strips the rich message down to plain text automatically; fill it in when you want a tighter wording for a 160-character world or a call.
- **Email + In-App fallback** *(on by default)* — if a recipient can't be reached on any selected channel (no phone/Telegram connected, or opted out), they're sent Email + In-App instead, so the announcement still arrives. Email is always available. Turn it off only if you want a channel-exclusive send.

#### Print options

When **Print** is among the channels, a **Print Options** section appears:

- **Letter Head** — *Seminary Default* (the one set in Seminary Settings), *None*, or *Specific* (pick any Frappe Letter Head). The chosen letterhead wraps the printed PDF letter.
- **Print mailing labels** — also produce a sheet of mailing labels (PDF). Pick a **Label Format** — a **Mailing Label Format** record. Common Avery layouts (5160, 5161, 5163, L7160) are shipped; a seminary can add its own by measuring its label stock (columns, rows, label size, margins in mm) under **Mailing Label Format**. Use the **Mailing Labels (PDF)** button to generate/download; labels are also attached to the announcement when it's sent. Labels are produced for recipients with a postal address (on their Person record, or a Student record); those without one are listed as omitted so you know who to follow up.

**Printing the letters.** While drafting, **Letter Preview (PDF)** shows a single letter (subject + message in the letter head, personalized for one recipient) so you can check the layout. After you **submit**, the button becomes **Print Letters (PDF)**: the official, consolidated document — every recipient's personalized letter, one per page, ready to print and mail. It's also generated automatically on send and attached to the announcement (alongside the mailing labels), so the finished letters live on the announcement itself.

### 2. Audience

Announcements resolve their recipient list from live queries. Pick one or more audience rules — they're combined (union) and then de-duplicated by email.

| Rule | Who it includes |
|---|---|
| **All students enrolled this term** | Every student with a non-withdrawn Course Enrollment in a Course Schedule for the selected term. |
| **All instructors teaching this term** | Every instructor listed on any Course Schedule for the selected term. |
| **All alumni** | Every enabled Alumni Profile. Term-independent — ignores the term/program/course narrowing. Use for alumni newsletters or invitations. |
| **Only these Programs** | Narrows the student audience to the listed programs. Leave empty for all programs. Does not affect instructors. |
| **Only these Course Schedules** | Narrows to those specific sections. Picks up those sections' students, and — if "All instructors teaching this term" is also checked — their instructors only. Use this to message "everyone in Theology 101, Section A". |
| **Custom Filter** *(advanced)* | Pick any doctype and a JSON filter. Useful for edge cases: "all students in the MDiv program with a pending withdrawal", "all instructors in a specific department". |

You must pick at least one rule. Submit is blocked otherwise.

### 3. Preview Recipients

Before submitting, save the draft and click **Preview Recipients** in the form's top-right menu. A dialog shows a reachability tally — **how many are reachable on the channels you picked**, broken down per channel, and how many will rely on the Email/In-App fallback — plus a sample of up to 50 rows with a ✓/✗ **Reachable** column (with the reason: "no address" or "opted out"). Use this to sanity-check the audience *and* to spot, before sending, when an urgent SMS/WhatsApp blast would actually reach only a fraction of people (e.g. "SMS 12 of 32") so you can act on it.

If the preview count is zero, your audience rules are too narrow — nothing will submit in that state either. The form tells you the same thing at submit time.

### 4. Send immediately or schedule

- Leave **Send At** blank to send the moment you submit.
- Fill **Send At** with a future date/time to schedule. The announcement is saved in **Queued** status and picked up by the hourly scheduler. Granularity is roughly one hour — don't use this for time-sensitive messages that must go out at an exact minute.

### 5. Submit

Click **Submit**. At this moment:

1. The audience query runs and the resulting list is frozen into the **Recipients** tab as a permanent audit record.
2. If the send is immediate, the emails are queued right away; if scheduled, they queue on the next scheduler tick after the Send At time.
3. Status moves **Draft → Queued → Sending → Sent**. A failed SMTP transaction for one recipient marks that row **Failed** and is logged; the rest of the list still goes out.

Once submitted, the announcement is sealed — you cannot edit subject, body, or audience. If you need to fix something, cancel and amend (or just create a new announcement).

---

## Where recipients see it

Wherever you sent it:

- **Email** — delivered via the seminary's configured outgoing Email Account.
- **In-App** — the **Inbox / Announcements** in the app sidebar lists every message a person received, most recent first. No login to Desk required.
- **SMS / WhatsApp / Telegram** — if selected and the recipient has a number/chat connected for that channel, the Short Message is delivered there too.

The in-app list matches recipients by either user account or email, so it works even for recipients who don't log in with the same email they receive mail on. A recipient who has no address for a chosen channel (e.g. no Telegram connected) simply doesn't get that copy; the other channels still go out.

---

## Tracking delivery

Open a submitted announcement and go to the **Recipients** tab. Each row shows the party (Student / Instructor / custom), email, and a **Status**:

- **Sent** — at least one of the chosen channels reached the recipient (any successful channel marks the recipient Sent).
- **Failed** — every channel attempted for that recipient failed. The **Error** column has the message.
- **Pending** — not yet picked up (scheduled for later, or mid-flight).

The recipient count and the announcement's overall status at the top give you the at-a-glance view. Drill into the tab for per-person detail. For full per-channel detail (which channels were tried, delivery receipts), open the recipient's Person record and its **Conversation** tab, or the **Communication Log** list filtered by this announcement.

---

## Common tasks

### Sending a reminder to a specific program

1. New Seminary Announcement.
2. Check **All students enrolled this term**.
3. In **Only these Programs**, add the program. Leave instructors and courses empty.
4. Preview — confirm only the right program's students show. Submit.

### Messaging one section's students and instructor together

1. New Seminary Announcement.
2. Check **All students enrolled this term** and **All instructors teaching this term**.
3. In **Only these Course Schedules**, add the section.
4. Preview. Submit. The student list is narrowed to that section; the instructor list is narrowed to that section's instructors.

### Emailing everyone teaching, across all programs

1. New Seminary Announcement.
2. Check **All instructors teaching this term**. Leave everything else blank.
3. Preview. Submit.

### Emailing a custom slice (advanced)

Use **Custom Filter** when none of the built-in rules fit:

- **Filter DocType:** the doctype to query (`Student`, `Instructor`, or anything with an email field).
- **Email Field:** the name of the email column on that doctype (e.g. `student_email_id` for Student, `prof_email` for Instructor).
- **Filters (JSON):** a Frappe filter expression, e.g. `[["Student","enabled",1]]`.

Combine with the built-in rules or use it on its own.

---

## Common questions

**Can I edit an announcement after submitting?**
No. Submitting freezes subject, body, and the recipient snapshot — this is intentional, so what was sent always matches what's on record. If you need to correct something, cancel and send a new announcement noting the correction.

**What happens if the outgoing Email Account isn't configured?**
Submit still succeeds — recipients are frozen and rows enter Pending state — but no mail leaves the system. Configure or fix the Email Account and the queue flushes on the next attempt.

**What if a student withdraws between compose and send?**
The recipient list is frozen at submit time, not at send time. If someone withdraws between submit and the scheduled send, they'll still receive the message. If you need to re-resolve, cancel the queued announcement and create a new one closer to the send time.

**Can I schedule an announcement to recur?**
No — each announcement is a one-shot. For recurring reminders (monthly tuition reminders, weekly attendance warnings), use Frappe Notifications with a scheduled trigger instead.

**Does this respect unsubscribe preferences?**
Yes, by category. A recipient who has opted out of the announcement's category on a channel is skipped for that channel — except for **Emergency** announcements, which are delivered regardless of consent. Promotional announcements only reach recipients who have explicitly opted in. Recipients manage these preferences on their portal **Preferences** page.
