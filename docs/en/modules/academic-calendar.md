# Academic Calendar

The academic calendar manages terms, important dates, and deadline rules. All aspects are controlled via Desk.

## Overview
The academic calendar has a tiered structure: 
### Academic Year: 
Contains academic terms. May be used to trigger specific fees. On the Academic Term, you can see if and when Invoices for "New Academic Year" (NAY) were generated.

### Academic Term:
Terms cannot overlap. Each term must be wholly contained in an Academic Year, with start and end dates within the Academic Year. Academic Terms may be used to trigger specific fees, and you can see if and when Invoices for "New Academic Term" (NAT) were generated.
Each academic term defines the structure of a teaching period: start and end dates and withdrawal deadlines (dates for each [Withdrawal Rule](withdrawal.md#withdrawal-rules)). Additionally, Academic Terms are used throughout the system as "anchors" to calculate other events, such as enrollment and grading periods (under Seminary Settings).

### Enrollment Window Rules
Course enrollment windows control **when a Course Schedule opens and closes for
student enrollment** (plus a third, informational *grade close* deadline). They
are defined once, seminary-wide, under **Seminary Settings → Enrollment Window
Rules**, and applied to every Course Schedule automatically.

Each of the three windows is set with an **anchor** plus an **offset in days**:

- **Anchor** — the reference date the offset counts from:
  - `term_start` / `term_end` — the [Academic Term](#academic-term)'s start / end date.
  - `classes_start` / `classes_end` — *this* Course Schedule's own start / end date.
- **Offset (days)** — how many days from the anchor. **Negative = before** the
  anchor, positive = after, `0` = on the anchor itself.

The three windows:

| Window | What it controls |
| --- | --- |
| **Enrollment Open** | When the Course Schedule moves from *Draft* to *Open for Enrollment* — students can enroll. |
| **Enrollment Close** | When it moves from *Open for Enrollment* to *Enrollment Closed* — enrollment stops. |
| **Grade Close** | Informational deadline for submitting final grades. After it passes, instructors of courses still being graded receive reminder emails. |

> **Leave an anchor blank to opt out** of that window. With no Enrollment Open
> rule (and no override), a new Course Schedule opens for enrollment
> *immediately* on creation instead of waiting in Draft.

**Auto-advance.** When **Auto-advance Course Schedule states** is enabled in
Seminary Settings, a daily job promotes each Course Schedule as its dates arrive
(Draft → Open for Enrollment → Enrollment Closed). With it off, the dates are
still computed and shown, but staff move courses through the states by hand.

**Per-course overrides.** The seminary-wide rule is only the default. Any
individual Course Schedule can override a date in its **Enrollment Dates**
section (*Enrollment Open Date Override*, *Enrollment Close Date Override*,
*Grade Close Date Override*) — the override always wins for that course. Use it
for a late-added course or a one-off exception.

#### Worked examples
Each example lists the values to enter under **Seminary Settings → Enrollment
Window Rules**.

##### Example 1 — All courses in a term open and close together
Everyone enrolls during a single term-wide window, no matter when each class
actually meets.

| Setting | Value |
| --- | --- |
| Enrollment Open Anchor | `term_start` |
| Enrollment Open Offset (days) | `-14` &nbsp;*(two weeks before the term starts)* |
| Enrollment Close Anchor | `term_start` |
| Enrollment Close Offset (days) | `7` &nbsp;*(one week after the term starts — a short add/drop grace)* |

##### Example 2 — Each course opens relative to its own start date
Useful when classes within a term begin on different dates (e.g. intensives or
modular courses).

| Setting | Value |
| --- | --- |
| Enrollment Open Anchor | `classes_start` |
| Enrollment Open Offset (days) | `-30` &nbsp;*(enrollment opens a month before each class begins)* |
| Enrollment Close Anchor | `classes_start` |
| Enrollment Close Offset (days) | `0` &nbsp;*(closes the day the class starts)* |

##### Example 3 — Close enrollment before the term ends
| Setting | Value |
| --- | --- |
| Enrollment Open Anchor | `term_start` |
| Enrollment Open Offset (days) | `0` |
| Enrollment Close Anchor | `term_end` |
| Enrollment Close Offset (days) | `-10` &nbsp;*(no new enrollments in the term's last 10 days)* |

##### Example 4 — A grading deadline after classes end
Pair any of the windows above with a grade deadline:

| Setting | Value |
| --- | --- |
| Grade Close Anchor | `classes_end` |
| Grade Close Offset (days) | `14` &nbsp;*(final grades due two weeks after the class ends)* |

Instructors of any course still in *Enrollment Closed* or *Grading* past this
date receive automatic reminder emails.

##### Example 5 — No automatic windows (open immediately)
Leave **all anchors blank**. Every new Course Schedule lands directly in *Open
for Enrollment* and stays there until staff close it manually. Choose this if
your seminary manages enrollment timing by hand or course-by-course.

##### Example 6 — One course needs an exception
Keep the seminary-wide rule, but for a single late-added Course Schedule, open
its **Enrollment Dates** section and set **Enrollment Open Date Override** to the
date you want. That course ignores the seminary rule; all others are unaffected.

## Key concepts

- **Academic Term** — the fundamental time unit (semester, trimester, quarter)
- **DateRuleResolver** — configurable logic for computing academic deadlines relative to term dates
- **Enrollment Windows** — seminary-wide anchor + offset rules that open and close Course Schedules for enrollment (overridable per course)
- **Term-Level Rules** — deadline and policy configuration lives at the term level, allowing different rules per term
