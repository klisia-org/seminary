# Programs

A **Program** is the thing a student enrolls in to gain access to courses — an
M.Div, a one-year certificate, a continuing-education track. It is also where
you set the academic and financial rules that govern everyone enrolled in it:
how progress is measured, whether it costs money, what counts toward
graduation, and how its courses and specializations are organized.

You author programs entirely from Desk (**Program → New**). This page walks
through the options and then explains the part that trips people up most —
**tracks and emphases**.

## How a program is shaped

A handful of orthogonal choices define the _character_ of a program. Set these
first; everything else hangs off them.

| Choice             | Field                                        | What it decides                                                                                                                                       |
| ------------------ | -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Level**          | `Program Level`                              | The tier (Certificate, Bachelor, Master, Doctorate, Continuing Ed…) and whether the program is _ongoing_.          |
| **Has an end?**    | _(mirrored)_ `Is Ongoing` | Degree-style (graduation, GPA, transcript) vs. ongoing (no end, no graduation). |
| **Progress model** | `Enrollment Type`                            | Measured by **terms** completed (Time-based) or **credits** earned (Credits-based).             |
| **Admissions**     | `Enrollment Mode`                            | Apply only during published windows (Timed) or any time (Continuous).                           |
| **Cost**           | `Free Program` + payment flags               | Free, or paid with payment-gated enrollment.                                                                                          |

These are independent — a program can be _Credits-based_, _Continuous_, and
_Free_ all at once, or any other combination.

### Program Level and "ongoing"

A **Program Level** (Desk → Program Level) is a reusable tier you attach to a
program — _Certificate_, _Bachelor_, _Master_, _Doctorate_, _Continuing
Education_, etc. Besides categorizing the program, it carries one important
switch:

> **Is Ongoing** — _"Check this ONLY if the Program has no definitive end (no
> graduation, credits, etc.). Useful for free courses, continuing education,
> etc."_

When the chosen level is ongoing, the program **mirrors** that as a read-only
`Is Ongoing` flag and automatically skips everything that assumes an end:
graduation audit and requests, GPA and honors, the alumni transition, and the
Academic Review step on withdrawal. Leave the level non-ongoing for any real
degree.

### Progress model — Time-based vs. Credits-based

For degree (non-ongoing) programs, **Enrollment Type** picks how you track a
student toward completion:

- **Time-based** — progress is counted in **terms**. Set **Terms for
  completion**. Courses can carry a suggested **Term number** so the audit knows
  where each one belongs in the sequence.
- **Credits-based** — students enroll in courses in any term, and progress is
  counted in **credits**. Set **Credits for completion**.

**Max Years to Graduate** (optional, fractional years allowed, `0` = no limit)
caps how long a student has; on enrollment the system stamps a maximum
graduation date of _enrollment date + this many years_.

### Admissions — Timed vs. Continuous

**Enrollment Mode** controls how applicants get in:

- **Timed** — applications are accepted only during published
  [Term Admission](enrollment.md) windows.
- **Continuous** — applicants may apply any time; the public "Apply" button tags
  them to the current Academic Term.

### The application form

The public "Apply" button opens a **Web Form** that creates a Student Applicant.
The built-in form is intentionally thorough (personal, education, employment,
church, doctrinal statement, signature…), which is right for a degree program but
far heavier than a free course or continuing-education track needs.

To use a lighter form, set **Application Web Form** on the program. The button
then opens that form instead. The route is resolved in this order:

1. The program's **Application Web Form**, if set.
2. **Seminary Settings → Default Application Web Form**, if set (a site-wide
   default for every program that doesn't choose its own).
3. The built-in `student-applicant` form, as the final fallback.

So you can leave most programs blank and only point your free/CE programs at a
short form — or flip the _default_ and reserve the long form for the few programs
that need it.

> **Build your own form; don't edit the built-in one.** The shipped
> `student-applicant` form is a _standard_ web form — it is re-synced from the app
> on every update, and any changes you make in Desk are overwritten. Instead,
> **create a new Web Form** (Desk → Web Form → New) for the _Student Applicant_
> doctype with just the fields you want. Your own forms live in the database and
> are never clobbered. The **Application Web Form** picker only lists Web Forms
> built on Student Applicant.

A few things to get right on a custom form:

- **Keep the prefill fields.** Include `program` and `academic_term` (and
  `term_admission` if you accept Timed applications). The Apply button passes
  these in the URL, and Frappe only prefills them if the form actually contains
  those fields. You also need the `Student Email`, as this is needed for login.
  You do **not** need to add `academic_year` — it is derived automatically from
  the academic term, so leave it off the form.
- **For the doctrinal statement, just add the `signdoctrine` signature field.**
  The current admission Doctrinal Statement is rendered automatically as a
  read-only block directly above the signature on every Student Applicant form
  (built-in or custom) — you don't add a `ds2` field and you don't write any
  script.
- **Set its own success behavior.** The built-in form redirects to the payment
  page after submission. That redirect lives on the built-in form, so a custom
  form for a **free** program won't carry it — set the new form's **Success URL**
  (or a success message) to send applicants wherever makes sense, e.g. a simple
  thank-you instead of a payment page.

### Cost and payment gating

- **Free Program** — bypasses enrollment invoicing and skips Financial Review on
  withdrawal.
- For paid programs, **Require Payment Before Enrollment** holds each course
  enrollment at _Awaiting Payment_ until the student pays (or reaches the
  **Minimum Payment %**). **Require Staff Verification of Course Enrollments**
  makes a registrar approve a student's draft enrollment before they can pay.

The mechanics of payment-gated enrollment are covered in
[Enrollment](enrollment.md).

## Courses

The **Courses** table lists every course that belongs to the program. For each
row:

- **Mandatory for this program** (`required`) — every student must pass it to
  graduate. Leave it unchecked for **electives**.
- **Credits for this program** — the same course can be worth a different number
  of credits in different programs, so credits live on the program row.
- **Term number** — a suggested term, used to sequence the audit.
- **Allow more than once** — permit the course to count for credit more than
  once.
- **Disabled** (+ **Disable Reason**) — retire a course from this curriculum
  without deleting history. Students who already took it keep their record; new
  students no longer see it. The system stamps **Disabled On** automatically.

> **List every course here.** Even courses that only matter to one track or
> emphasis must appear in this main Courses table. The track tables below just
> point at courses that already exist here.

## Tracks and emphases

A **track** is a named group of courses inside a program. Tracks come in two
flavors, distinguished by one checkbox — **Program Emphasis?** — and they behave
very differently.

### Organizational tracks (not an emphasis)

Leave **Program Emphasis?** unchecked to use a track as a **requirement
carve-out** — a way to say _"the program requires N credits from this group of
courses."_

> Example: _"Students must earn 6 credits of Biblical Greek."_ Create a track
> _Biblical Greek_, set **Track Credits Required = 6**, and list the Greek
> courses under it (on the **Courses per Track** table). The student may satisfy
> the 6 credits from any of those courses.

Organizational tracks are about **communicating and grouping** structure.
Students do **not** declare them; they are not specializations on a transcript.

### Emphases (a declared specialization)

Check **Program Emphasis?** to make a track a **declared concentration** — an
Old Testament emphasis, a Counseling emphasis, a Missions emphasis. Emphases are
actively tracked on the student's audit and (unless marked advisory) **gate
graduation**.

Key fields on an emphasis track:

- **Track Credits Required** (`addcredits`) — the minimum credits the student
  must earn within the emphasis. These count toward the program's total.
- **Track Credits Ceiling** (`max_credits`, `0` = unlimited) — the maximum
  emphasis credits that count toward the degree. Credits beyond the cap are
  still earned, but stop counting toward the program total.
- **Emphasis Declaration** — _when_ a student takes it on:
  - **At Enrollment** — must be chosen before the enrollment is submitted.
  - **Anytime** — may be declared later (optionally only after earning a
    **Min Credits to Declare**).
  - **Auto-grant** — assigned automatically once the student meets the
    emphasis's credit requirements.
- **Advisory Only** — the emphasis is informational and does **not** block
  graduation.
- **Fallback Emphasis?** — marks the one default emphasis (e.g. _General
  Studies_) assigned to students who never declare a specific one.

**Mandatory courses for an emphasis** are set on the **Courses per Track** table
by ticking **Mandatory?** for a (track, course) pair. A student on that emphasis
must pass those specific courses, on top of meeting the credit total.

### Multiple emphases

If **Allow Multiple Emphases** is on, a student may declare more than one. The
**Emphasis Overlap Policy** then decides how the credits add up:

- **Shared Credit Pool** — all emphases draw from the same program total. A
  course can help satisfy two emphases at once.
- **Additional Credits Required** — each emphasis beyond the first adds its
  track credits _on top of_ the program total, so a double emphasis genuinely
  costs more credits.

### Worked examples

**1 — A language requirement (organizational track).**
_Goal: 6 credits of Greek, student's choice of course._
Track _Biblical Greek_, **Program Emphasis? off**, **Track Credits Required =
6**; list the eligible Greek courses on Courses per Track. The track documents
the requirement and groups the courses; the student picks any 6 credits' worth.

**2 — An Old Testament emphasis declared up front.**
_Goal: students choose OT at enrollment, take 12 emphasis credits including two
required courses._
Track _Old Testament_, **Program Emphasis? on**, **Track Credits Required = 12**,
**Emphasis Declaration = At Enrollment**. On Courses per Track, add the OT
courses and tick **Mandatory?** on _Hebrew I_ and _OT Theology_. The student must
choose this emphasis before submitting enrollment, pass both required courses,
and reach 12 OT credits.

**3 — A counseling emphasis declared later.**
Same as above but **Emphasis Declaration = Anytime** and **Min Credits to
Declare = 30** — the student can pick it up only after 30 program credits.

**4 — Auto-granted emphasis.**
Set **Emphasis Declaration = Auto-grant**. The student never declares it; once
they have met the track's credit requirement, the system records the emphasis
for them.

**5 — Double emphasis that costs more.**
Turn on **Allow Multiple Emphases** and set **Emphasis Overlap Policy =
Additional Credits Required**. A student who declares both _Old Testament_ and
_Missions_ must complete the program total **plus** the second emphasis's track
credits.

**6 — A safety-net emphasis.**
Create _General Studies_, tick **Program Emphasis?** and **Fallback Emphasis?**.
Students who never declare anything else are treated as being on General Studies
for graduation.

## GPA, honors, and graduation

For degree programs:

- **Basis for GPA** — the top of your scale (US = 4.0; others vary).
- **Credit-weighted GPA** — when on, GPA is weighted by course credits; when off,
  it is a simple average.
- **Accept Transfer Grades in GPA** — whether transferred course grades count in
  GPA (also requires the source Partner Seminary to allow it).
- **Honors Levels** — a list of honor names with minimum GPAs (e.g. _Cum Laude_
  at 3.5). The highest level a student qualifies for shows on their enrollment.
- **Students Can Request Graduation** + **Graduation Request Trigger** (_Enrolled
  in final courses_ vs. _Passed final courses_) — whether and when a student can
  file a [Graduation Request](graduation-request.md) from their audit page.

The non-course requirements a program demands (letters, chapel, projects, etc.)
are configured separately — see [Graduation Requirements](graduation-requirements.md).

## Publishing on the web

The **Web** tab controls the public-facing program page: **Route** (URL slug),
**Blurb** and images for the program list, **Program Description** and
**Requirements**, duration fields for sorting/filtering, and two visibility
switches — **Display Enrollment Windows on Web** and **Display Apply CTA on Web**
(both off by default; the CTA has no effect for Continuous programs, which apply
any time). Untick **Publish on web** to hide a program entirely.

## How it all shows up on the Program Audit

Everything above converges on the **Program Audit** page (also visible to
staff). For each enrolled student it shows:

- **Credit / term progress** toward the program total.
- **Program mandatory courses** and their status.
- **Each declared emphasis** — credits required vs. earned (respecting the
  ceiling), and any still-missing mandatory track courses.
- The parallel **Graduation Requirements** (non-course evidence).

A student is _eligible to graduate_ only when the credit/term total is met, all
program-mandatory courses are passed, every non-advisory emphasis has met its
credits and required courses, and the graduation requirements are clear.

## Quick reference

| If you want to…                                                                                                                                                                                      | Do this                                                                                                                                                                     |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Create a degree program                                                                                                                                                                              | New Program; pick a non-ongoing Program Level; set Enrollment Type + Terms/Credits for completion                                                                           |
| Create a free, never-ending offering (e.g., a Free Courses page on the website to train believers and serve as a marketing tool for the seminary) | Use a Program Level with **Is Ongoing**; tick **Free Program** (often, Enrollment mode = continuous)                                                     |
| Track progress by credits, any order                                                                                                                                                                 | Enrollment Type = **Credits-based**; set Credits for completion                                                                                                             |
| Mark a course required for everyone                                                                                                                                                                  | Tick **Mandatory for this program** on its Courses row                                                                                                                      |
| Retire a course from the curriculum                                                                                                                                                                  | Tick **Disabled** on its Courses row and give a reason                                                                                                                      |
| Require N credits from a group of courses                                                                                                                                                            | Add an organizational track (Program Emphasis? **off**) with **Track Credits Required**                                                                  |
| Offer a declared specialization                                                                                                                                                                      | Add a track with **Program Emphasis? on**; set credits, required courses, and declaration timing                                                                            |
| Let students declare two specializations                                                                                                                                                             | **Allow Multiple Emphases**; choose an **Emphasis Overlap Policy**                                                                                                          |
| Give undeclared students a default                                                                                                                                                                   | Mark one emphasis as **Fallback Emphasis?**                                                                                                                                 |
| Let students apply year-round                                                                                                                                                                        | Enrollment Mode = **Continuous**                                                                                                                                            |
| Use a shorter application for a free/CE program                                                                                                                                                      | Build a Web Form on _Student Applicant_; set it as the program's **Application Web Form** (or the **Default Application Web Form** in Seminary Settings) |
| Show the program (and Apply button) publicly                                                                                                                                      | Web tab → **Publish on web**, **Display Apply CTA on Web**                                                                                                                  |

## Related

- [Enrollment](enrollment.md) — how students enroll, and payment-gated course
  enrollment for paid programs.
- [Graduation Requirements](graduation-requirements.md) — the non-course
  requirements (letters, chapel, projects) that sit alongside courses.
- [Graduation Request](graduation-request.md) — the request-and-approval flow.
- [Academic Calendar](academic-calendar.md) — terms and the enrollment windows
  that open courses for registration.
