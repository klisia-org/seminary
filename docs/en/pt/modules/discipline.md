# Discipline

Seminaries hold students to a standard of conduct and academic integrity, and
they care deeply about _due process_ — a sanction should be proportionate,
consistent, and on the record. The **Discipline** module gives you a catalog of
reasons and sanctions, an **advisory progressive-discipline matrix** that
suggests the right action by how many times something has happened, and a clean
trail from "an instructor noticed something" to "the student was dismissed and
cannot re-enroll." Nothing is enforced automatically except a single, explicit
dismissal flag — every other decision stays in human hands.

## Visão geral

The module has **three building blocks**, plus an optional instructor-portal
reporting flow:

```
Disciplinary Reason   — the "what happened" catalog (plagiarism, absence, …)
        │  carries a recommended-actions matrix by occurrence number
Disciplinary Action   — the "what we do about it" catalog (warning … dismissal)
        │
Disciplinary Incident — one record of one event, with the action(s) applied
```

- A **Reason** is _why_ — a reusable category like _Plagiarism_ or _Unexcused
  Absence_. Each reason carries an **advisory matrix**: "1st time → Verbal
  Warning, 2nd → Written Warning, 3rd and beyond → Dismissal."
- An **Action** is _what you do_ — a sanction like _Verbal Warning_ or
  _Dismissal_, defined once and reused.
- An **Incident** ties a reason to a student on a date, records the evidence,
  and lists the action(s) actually applied. The matrix **pre-fills** suggestions
  by occurrence; the adjudicator confirms or overrides.

The only automatic consequence in the whole module is a Disciplinary Action
flagged **Triggers Program Dismissal**: recording such an action on an incident
separates the student from the program (through the same
[separation spine](withdrawal.md) used by withdrawals) and places a hold that
blocks re-enrollment. Everything else is advisory.

## Configurações

Disciplinary reporting from the instructor portal is gated by **two** switches —
both must be on for an instructor to file an incident from a course:

1. **Seminary Settings → `Instructors create Disciplinary Incident`** — the global switch. When
   checked, each course shows actions to report disciplinary incidents at the
   course and assessment levels.
2. **Disciplinary Reason → `Instructor Portal`** — the per-reason switch. Only
   reasons marked available to instructors appear in the portal report dialog.

If the global switch is off, the portal shows no reporting buttons at all, and
all incidents are filed by staff in Desk. The two-switch design lets you turn on
portal reporting broadly while still keeping sensitive reasons (say, anything
that can lead to dismissal) off the instructor-facing list.

## The catalog

### Disciplinary Reasons

A **Disciplinary Reason** (Desk → Disciplinary Reason) is a reusable category of
violation. Fields:

- **Reason** — the name students and staff see (_Plagiarism_, _Disruptive
  Conduct_, _Unexcused Absence_).
- **Category** — _Academic Integrity_, _Conduct_, _Attendance_, _Financial_, or
  _Other_. Used for filtering and reporting.
- **Description** — a catalog description of what this reason covers.
- **Instructor Portal** — when checked, instructors can pick this reason when
  reporting from the portal (the second gate described under
  [Settings](#settings)).
- **Requires Assessment** — when checked, this reason lives at the **assessment
  level**: filing it requires the course enrollment _and_ the specific
  assessment involved. Use it for things tied to a piece of work (plagiarism on
  an essay, cheating on an exam). Leave it unchecked for course-level conduct
  (disruption, repeated lateness).
- **Recommended Actions** — the advisory matrix (next section).

#### The progressive-discipline matrix

Inside each reason you list **Recommended Actions** — rows that map an occurrence
number to the sanction you suggest:

| Coluna                 | Significado                                                                                                                   |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **Occurrence from**    | First occurrence this row applies to (1 = first offense).                                  |
| **Occurrence to**      | Last occurrence this row applies to. **0 means "and above"** (open-ended). |
| **Recommended Action** | The Disciplinary Action to suggest.                                                                           |
| **Note**               | Optional guidance copied onto the incident as an outcome note.                                                |

A row applies when the student's occurrence number falls between _from_ and _to_
(inclusive), treating _to = 0_ as "and above." So a classic three-step ladder
for _Plagiarism_ (with one verbal and two written warnings) is:

| De | Até | Recommended Action |
| -- | --- | ------------------ |
| 1  | 1º  | Verbal Warning     |
| 2  | 3   | Written Warning    |
| 4º | 0   | Dismissal          |

The **occurrence number** is computed automatically — it is a 1-based count of
this student's incidents _for this same reason_. The third plagiarism incident
for a student lands on the "3 and above" row and suggests Dismissal. This is the
heart of the module: repeated minor offenses escalate on their own, without
anyone having to remember "wasn't this the third time?"

> **Advisory, not automatic.** The matrix only **pre-fills** an incident's
> applied actions. The adjudicator can confirm them, add others, or remove them
> entirely. The matrix is a recommendation engine, not an enforcement engine.

### Disciplinary Actions

A **Disciplinary Action** (Desk → Disciplinary Action) is a sanction you can
apply. The system seeds a starter set you can edit or extend: _Verbal Warning_,
_Written Warning_, _Disciplinary Probation_, _Suspension_, _Dismissal_. Fields:

- **Action Name** — the sanction's name (unique).
- **Severity** — _Informal_, _Formal_, _Probation_, _Suspension_, or
  _Dismissal_. Informational/for reporting.
- **Triggers Program Dismissal** — **the one automatic effect in the module.**
  When an applied action of this type is recorded on an incident, the student is
  dismissed from the program through the shared
  [separation spine](withdrawal.md) and a re-enrollment hold is placed. By
  default only _Dismissal_ carries this flag.
- **Instructor Action** — when checked, instructors may **record** this action
  themselves from the portal. Use it for low-stakes sanctions an instructor is
  authorized to hand out on the spot — chiefly **verbal and written warnings**
  that don't need escalation. Leave it off for anything that should go to an
  adjudicator (probation, suspension, dismissal).
- **Is Active** — untick to retire a sanction without deleting history.
- **Description** — what the sanction means.

> **Two different flags, two different jobs.** _Triggers Program Dismissal_
> decides whether applying the action ends the student's program. _Instructor
> Action_ decides whether a classroom instructor (rather than an adjudicator)
> may record it. A Verbal Warning is an _Instructor Action_ and does **not**
> trigger dismissal; a Dismissal triggers dismissal and is **not** an Instructor
> Action.

### Disciplinary Incidents

A **Disciplinary Incident** (Desk → Disciplinary Incident) records one event.
Key fields:

- **Program Enrollment** / **Student** — who the incident concerns (the student
  is derived from the enrollment).
- **Course Enrollment** / **Assessment** — the course (and, for
  _Requires Assessment_ reasons, the specific assessment) involved.
- **Incident Date**, **Reason**, **Occurrence number** (auto-computed).
- **Evidence** and **Attachment** — describe what happened and attach proof.
- **Applied Actions** — the sanctions actually applied. Rows pre-filled from the
  matrix are flagged _was suggested_; each row stamps who applied it and when.
- **Status** — the incident's lifecycle:
  - **Reported** — filed, awaiting an action.
  - **Action Taken** — an instructor-authorized sanction was recorded.
  - **Escalated** — needs an adjudicator (e.g. the recommendation is a
    suspension or dismissal an instructor cannot record themselves).
  - **Dismissed** — an applied action triggered program separation.
- **Reported By** — who filed it (set automatically when reported from the
  portal).
- **Resolution Description** — a narrative of the actions taken.

When you pick a reason and the occurrence number is known, the matrix
automatically pre-fills the **Applied Actions** with the recommended sanction(s),
marked as suggestions, with a _"confirm or override"_ prompt. You stay in
control: keep them, change them, or add your own.

## Reporting from the instructor portal

When [the two switches](#settings) are on, instructors can file incidents
without touching Desk. There are two entry points.

### Course-level reporting

On a course card (for instructors and moderators) a **Report Disciplinary
Incident** button opens a dialog where the instructor:

1. Picks the **student** (the dropdown lists the course's enrolled students by
   name).
2. Picks a **reason** — only reasons that are _Instructor Portal_ **and** not
   _Requires Assessment_ appear here (course-level conduct).
3. Optionally adds **evidence** and an **attachment**.

As soon as student and reason are chosen, the dialog previews _"This will be
occurrence #N"_ and the recommended action. What happens next depends on the
recommendation (see [Recording now vs. later](#recording-now-vs-later)).

### Assessment-level reporting

While grading a single submission (exam, assignment, quiz, or discussion) a
**Report Disciplinary Incident for this Submission** button opens the same
dialog, but with the **student and assessment fixed** from the submission you
are grading — the instructor only needs to choose a reason (here, only
_Instructor Portal_ **and** _Requires Assessment_ reasons appear, e.g.
plagiarism) and optionally add evidence. This is the natural place to flag
academic-integrity issues the moment you spot them.

### Recording now vs. later

After the preview, the dialog adapts to the recommended action:

- If the recommendation is an **Instructor Action** (e.g. Verbal Warning), the
  instructor sees **two buttons**:
  - **Report & Record Action** — file the incident _and_ record the sanction
    now (status → _Action Taken_). Use it when you handle it on the spot ("I
    spoke to the student").
  - **Report Only** — file the incident now and leave the action for later
    (status → _Reported_). Use it when you want to report and keep grading, or
    when someone else should decide.
- If the recommendation is **not** an instructor action — or it would trigger
  dismissal — the instructor sees a single **Report** button. The incident is
  filed and **Escalated** for an adjudicator to handle in Desk. (The success
  message confirms it was reported.)

### Pending actions (report now, act later)

"Report Only" incidents don't fall through the cracks. Each course's **To-Do
card** shows a **Disciplinary — Pending Actions** list for instructors, with one
row per pending incident (student, reason, occurrence, recommended action) and a
**Record Action** button. **Any instructor on that course** can record the
action — so a grader can report an incident after hours and the professor of
record can record the sanction the next morning, or vice versa. Recording the
action moves the incident to _Action Taken_ and removes it from the list.

## Dismissal: the one automatic effect

If an applied action is flagged **Triggers Program Dismissal** (by default,
_Dismissal_), saving the incident:

1. Initiates a **full program separation** for the student through the shared
   [separation spine](withdrawal.md), with separation status _Dismissed_ and
   category _Disciplinary_, effective on the incident date.
2. Places a **re-enrollment hold** on the student, so they cannot simply
   re-register, with the incident recorded as the source.
3. Sets the incident's status to **Dismissed**.

This is deliberately the _only_ enforced outcome — and it requires a human to
record a dismissal action on the incident. Disciplinary exits never use the
student-facing [Withdrawal Reasons](withdrawal.md) taxonomy; the separation
carries the Disciplinary Reason in its history and uses a dedicated
_Disciplinary Dismissal_ reason only to satisfy the separation record.

## Exemplos práticos

### Example 1 — Plagiarism, escalating to dismissal

**Goal:** plagiarism is a Verbal Warning the first time, a Written Warning the
second, and Dismissal the third.

1. **Create the reason.** Desk → Disciplinary Reason → New.
   - Reason: `Plagiarism`; Category: `Academic Integrity`
   - Requires Assessment: ✓ (it is tied to a piece of work)
   - Instructor Portal: ✓ (so instructors can flag it while grading)
   - Recommended Actions:
     - 1 → 1 — Verbal Warning
     - 2 → 2 — Written Warning
     - 3 → 0 — Dismissal
2. **Confirm the actions exist.** _Verbal Warning_ and _Written Warning_ should
   be **Instructor Action = ✓**; _Dismissal_ should be **Triggers Program
   Dismissal = ✓** (these come seeded).
3. **First offense.** While grading the essay, the instructor clicks _Report
   Disciplinary Incident for this Submission_, picks `Plagiarism`, sees
   _"Occurrence #1 — Verbal Warning,"_ and clicks **Report & Record Action**.
4. **Third offense.** The same flow now previews _"Occurrence #3 — Dismissal."_
   Because Dismissal is not an instructor action, the instructor only gets
   **Report**, and the incident is **Escalated**. An adjudicator opens it in
   Desk, confirms the Dismissal action, and the student is separated with a
   re-enrollment hold.

### Example 2 — Repeated absences (course-level, report now / act later)

**Goal:** track unexcused absences so a pattern is visible, with warnings the
instructor can hand out.

1. Create reason `Unexcused Absence` (Category `Attendance`, Instructor Portal
   ✓, Requires Assessment ✗) with a matrix: 1–2 → Verbal Warning, 3 → Written
   Warning.
2. A teaching assistant notices a third absence and, from the course card,
   clicks _Report Disciplinary Incident_, picks the student and reason, and uses
   **Report Only** (they'd rather the professor decide).
3. The incident appears under **Disciplinary — Pending Actions** on the course
   To-Do. The professor of record opens it, clicks **Record Action**, and the
   Written Warning is on file.

### Example 3 — A sanction an instructor cannot give

**Goal:** a conduct violation whose recommended action is _Disciplinary
Probation_.

Probation is **not** an Instructor Action. When an instructor reports it, they
only see **Report**; the incident is **Escalated**. The dean opens it in Desk,
reviews the evidence, and records Probation (or overrides with a different
action). The instructor did the reporting; the adjudicator made the decision.

## No dia a dia da equipe

- **File an incident in Desk.** Desk → Disciplinary Incident → New. Pick the
  program enrollment and reason; the occurrence number and recommended actions
  fill in. Confirm or override the **Applied Actions**, add evidence, and save.
- **Find what needs attention.** A list view of _Disciplinary Incident_ filtered
  by `status = Reported` or `status = Escalated` shows the open queue;
  instructors see their courses' pending items on each course To-Do card.
- **Record or change an action.** Open the incident, edit the _Applied Actions_
  table, and save. Recording a _Triggers Program Dismissal_ action will separate
  the student — do it deliberately.
- **Build a student's history.** Filter _Disciplinary Incident_ by student to see
  every reason, occurrence, action, and status on record.

## Referência rápida

| Se você quiser... | Faça isto                                                                                                              |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Add a new kind of violation                                       | Create a Disciplinary Reason (set Category; tick Instructor Portal / Requires Assessment as needed) |
| Make warnings escalate automatically                              | Add Recommended Actions rows to the reason (use _to = 0_ for "and above")                           |
| Add a new sanction                                                | Create a Disciplinary Action (set Severity)                                                         |
| Let instructors hand out a sanction themselves                    | Tick **Instructor Action** on that Disciplinary Action                                                                 |
| Make a sanction end the student's program                         | Tick **Triggers Program Dismissal** on that Disciplinary Action                                                        |
| Let instructors report from courses                               | Turn on Seminary Settings → **Portal Disciplinary** _and_ the reason's **Instructor Portal**                           |
| Flag plagiarism while grading                                     | Use _Report Disciplinary Incident for this Submission_ on the submission                                               |
| Report now and decide later                                       | Use **Report Only**; record the action later from the course To-Do                                                     |
| Record a pending action                                           | Open the course To-Do → Disciplinary — Pending Actions → **Record Action**                                             |
| Dismiss a student for cause                                       | Record a _Dismissal_ (Triggers Program Dismissal) action on the incident                            |
| Review a student's record                                         | Filter Disciplinary Incident by student                                                                                |

## Relacionados

- [Withdrawal & Separation](withdrawal.md) — the spine disciplinary dismissals
  flow through; how holds block re-enrollment.
- [Grading](grading.md) — where assessment-level reporting lives.
- [User Roles](../administration/user-roles.md) — who can file incidents, record
  actions, and adjudicate.
