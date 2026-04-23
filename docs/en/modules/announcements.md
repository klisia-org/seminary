# Announcements

Seminary Announcements let you send a single message to everyone enrolled this term, everyone teaching this term, or any combination you need. Messages are delivered by email and also appear inside the student/instructor app under **Announcements**. Recipients are resolved from live data at send time, so students who enroll or drop between compose and send are picked up correctly.

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

### 1. Subject and message

- **Subject** — the email subject line. Keep it short and specific: "Midterm week — building closure Friday" is better than "Important announcement".
- **Academic Term** — defaults to the current term. Change it only if you're announcing something for a different term (e.g., a heads-up to next term's audience).
- **Message** — the body. Full rich-text: headings, lists, links, bold, inline images.

### 2. Audience

Announcements resolve their recipient list from live queries. Pick one or more audience rules — they're combined (union) and then de-duplicated by email.

| Rule | Who it includes |
|---|---|
| **All students enrolled this term** | Every student with a non-withdrawn Course Enrollment in a Course Schedule for the selected term. |
| **All instructors teaching this term** | Every instructor listed on any Course Schedule for the selected term. |
| **Only these Programs** | Narrows the student audience to the listed programs. Leave empty for all programs. Does not affect instructors. |
| **Only these Course Schedules** | Narrows to those specific sections. Picks up those sections' students, and — if "All instructors teaching this term" is also checked — their instructors only. Use this to message "everyone in Theology 101, Section A". |
| **Custom Filter** *(advanced)* | Pick any doctype and a JSON filter. Useful for edge cases: "all students in the MDiv program with a pending withdrawal", "all instructors in a specific department". |

You must pick at least one rule. Submit is blocked otherwise.

### 3. Preview Recipients

Before submitting, save the draft and click **Preview Recipients** in the form's top-right menu. A dialog shows the total count and a sample of up to 50 rows (type, name, email). Use this to sanity-check that you haven't accidentally targeted the wrong program or forgotten a course.

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

Two places:

- **Email** — delivered via the seminary's configured outgoing Email Account.
- **Announcements** in the app sidebar — students and instructors see a list of every announcement they received, most recent first, inside the main app. No login to Desk required.

The in-app list matches recipients by either user account or email, so it works even for recipients who don't log in with the same email they receive mail on.

---

## Tracking delivery

Open a submitted announcement and go to the **Recipients** tab. Each row shows the party (Student / Instructor / custom), email, and a **Status**:

- **Sent** — email accepted by the outgoing server.
- **Failed** — a delivery error. The **Error** column has the message.
- **Pending** — not yet picked up (scheduled for later, or mid-flight).

The recipient count and the announcement's overall status at the top give you the at-a-glance view. Drill into the tab for per-person detail.

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
Yes. Standard Frappe email-queue rules apply: anyone who has unsubscribed from this seminary's emails is skipped.
