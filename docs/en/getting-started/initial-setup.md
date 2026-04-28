# Initial Setup

After [installation](installation.md), walk through the sections below **in order**. Each one depends on the previous. Everything is done in the Frappe Desk unless noted.

::: tip ERPNext fundamentals
SeminaryERP is built on top of ERPNext. Several items below (Items, Price Lists, Customer Groups, Item Prices, Payment Terms) are *standard ERPNext records* — this page covers what a seminary specifically needs, and links out to the ERPNext manual for the full reference.
:::

## 1. Grading Scale

Create the default grading scale used seminary-wide. You can create additional scales later and assign them per-course. See [Grading](../modules/grading.md) for how scales interact with assessments and transcripts.

## 2. Seminary Settings

Open **Seminary Settings** in the Desk. This is the seminary-wide control panel:

- **Institution details and logo**
- **Default grading scale**
- **Scholarships** — Cost Center and Default Customer
- **Audits** — whether to allow non-credit students, and how they are charged (flat fee or per-credit hour)
- **Course withdrawal** — baseline policy (detailed rules are configured in the [Withdrawal module](../modules/withdrawal.md))
- **Course Schedule lifecycle**:
    - **Auto-advance Course Schedule states** (default on) — when checked, the daily scheduler advances Course Schedules automatically based on the dates below (Draft → Open for Enrollment → Enrollment Closed) and emails instructors who haven't sent grades by the deadline. Uncheck if your seminary prefers fully manual control.
    - **Enrollment Window Rules** — three pairs of (anchor, offset in days) that define when each Course Schedule opens for enrollment, closes enrollment, and expects grades. Anchors: `term_start`, `term_end`, `classes_start` (= each Course Schedule's start date), `classes_end` (= each Course Schedule's end date). Negative offset = before the anchor; positive = after. A blank anchor opts a window out — affected Course Schedules need explicit overrides on their own form (Lifecycle section) or land directly in Open for Enrollment with no enrollment deadline. See [Section 12](#_12-course-schedule-lifecycle).
- **HR/Payroll** - You may extend SeminaryERP functionality with our integration with Frappe HRMS to process payroll. In order to do this, click on [Enable HRMS Payroll](../modules/instructor-payment.md)
- **Student Portal** — toggle each capability students will have:
    - Request course enrollments
    - Request course withdrawals
    - Pay online through a payment gateway (and which gateway is the default — e.g. Stripe)
    - Edit course calendar instructions
    - Online student application workflow

## 3. ERP Items

In ERPNext, everything that can be billed is an **Item** (credit hour, registration fee, library fee, housing, etc.). SeminaryERP ships with a starter set — review them and decide which fit your seminary before creating more.

::: warning UOM must not be "whole number"
When creating a new Item, make sure its [UOM](https://docs.frappe.io/erpnext/uom) has **"Must be Whole Number"** unchecked. Credit hours and many fees are fractional.
:::

For anything else about Items — stock vs. non-stock, item groups, taxes — see the ERPNext [Item documentation](https://docs.frappe.io/erpnext/item).

## 4. Price Lists

A [Price List](https://docs.frappe.io/erpnext/price-lists) is simply a named set of prices. You can have as many as you want (e.g. *National Students*, *Foreign Students*, *Scholarship Tier A*), but **every additional list is ongoing maintenance** — add one only when pricing genuinely differs.

## 5. Customer Groups

SeminaryERP automatically creates a **Student** customer group. If you need different price lists applied automatically (e.g. national vs. international), create additional [Customer Groups](https://docs.frappe.io/erpnext/customer-group) and set each one's default Price List. Students assigned to the group will be billed from that list.

## 6. Item Prices

This is where you enter the price of each Item on each Price List. See [Item Price](https://docs.frappe.io/erpnext/item-price) for the mechanics.

Before entering numbers, read [Pricing Strategy](pricing-strategy.md) — how granular your pricing is determines how much automation and reporting SeminaryERP can do for you later.

## 7. Payment Terms

A [Payment Terms Template](https://docs.frappe.io/erpnext/payment-terms-template) bundles one or more [Payment Terms](https://docs.frappe.io/erpnext/payment-terms) (e.g. *50% at enrollment, 50% mid-term*). 
Therefore, templates are a simple and practical way to set up **when** and **the invoice portion (%)** of an invoice should be paid.

Payment terms will define the due date of a invoice based on the date of its creation, as well as the percentage of the invoice to be paid.
Templates are attached to Fee Categories and to invoices, so create the templates you actually need before setting up Fee Categories.

## 8. Fee Category

A **Fee Category** is SeminaryERP's billing automation unit. Each category links:

- An **ERP Item** (what is billed)
- A **Payment Terms Template** (how it is billed)
- A **Category Type** (Item Group) for reporting
- A **Event to Charge** (when the charge is created)
- Flags for **Is Academic Credit** and **Is Audit** --Only fee categories with these indicators will be calculated per credit hour (in the case of audits, see also Seminary Settings)

SeminaryERP defines the **Event to charge** and they are called programmatically. The following triggers are available for the creation of Fee Categories:

- **Program Enrollment** — fires once on Program Enrollment submission.
- **Course Enrollment** — fires once per course, on Course Enrollment submission.
- **New Academic Term** — daily scheduler fires on the Academic Term's start date (or the next day the job runs, if cron missed).
- **New Academic Year** — daily scheduler fires on the Academic Year's start date (or the next day the job runs, if cron missed).
- **Monthly** — daily scheduler fires on the calendar 1st of every month for every active Program Enrollment. A `Effective From` date on the Fee Category restricts billing to program enrollments whose Enrollment Date is strictly after that date (leave blank to bill everyone currently enrolled).

The three time-driven triggers (NAT / NAY / Monthly) are idempotent: the scheduler records that a period has been invoiced (via `invoiced_nat_on`, `invoiced_nay_on`, `last_monthly_invoiced_on` flags) and won't bill it twice. If a cron run is missed, the next daily run picks up any pending period. Billing can be paused globally via **Seminary Settings → Enable Automated Billing**. For one-off recovery, use **Registrar Hub → Regenerate Current-Term Invoices**.

Set up one Fee Category per chargeable event so SeminaryERP can post invoices automatically when the event happens. This is why Items, Price Lists, and Payment Terms must exist first.

Once Fee Categories are created, you will use them during the creation of Programs and courses.

## 9. Academic Year

Create your first **Academic Year**. It is a container for Academic Terms — terms cannot extend beyond their year's boundaries. Some fees and administrative tasks are scheduled once per year.

## 10. Academic Term

Create your first **Academic Term** inside the Academic Year:

1. Set start and end dates
2. Configure enrollment windows and withdrawal deadlines — see [Academic Calendar](../modules/academic-calendar.md) and [Withdrawal](../modules/withdrawal.md) for how these dates drive downstream rules

## 11. Program

A **Program** is the curriculum structure students enroll into (e.g. *M.Div.*, *Certificate in Biblical Studies*). It defines required credits/terms, courses, tracks, emphases, and program-level fees. Create at least one program before opening enrollment. 
Detailed program modeling (tracks, emphases, credit requirements) is covered under [Enrollment](../modules/enrollment.md). During enrollment, it will also be established **who** pays each fee category and what percentage (Payers Fee Category).

All Fee Categories for any course of that program **must** first be linked in the Program level. 

## 12. Course Schedule Lifecycle

Each **Course Schedule** moves through a six-state workflow that the daily scheduler advances automatically (when [Section 2](#_2-seminary-settings) "Auto-advance" is on) or that registrars walk through manually:

```
Draft → Open for Enrollment → Enrollment Closed → Grading → Closed
            ↓                       ↓
        Cancelled               Cancelled (terminal)
```

- **Draft** — created, not yet visible to students. The scheduler promotes to Open for Enrollment when the resolved enrollment-open date arrives.
- **Open for Enrollment** — students can request enrollment from the portal.
- **Enrollment Closed** — registration window has passed, term is running, prof is teaching.
- **Grading** — the system enters this state automatically the first time a non-null grade is saved against any active student (whether via Quiz/Assignment/Exam/Discussion submission or directly in the gradebook). No registrar action needed.
- **Closed** — final state, set when the prof clicks **Send Grades** on the gradebook (or, in the Desk, on the Course Schedule form). Final grades are written to the transcript at this moment.
- **Cancelled** — terminal. Reachable only before grading begins (see *Cancelling a Course* below).

### Per-Course-Schedule date overrides

Each Course Schedule's **Lifecycle** section (in the Class Roster tab) shows the resolved enrollment open / close / grade-close dates from the Seminary Settings rule, plus three optional **override** date fields. Filling an override replaces the rule for that one schedule — useful for late-added courses, intensives, or one-off exceptions.

### Course Cancellation Reasons

Cancellations require a **reason** chosen from a configurable list. SeminaryERP ships with five seeded reasons:

- Insufficient Enrollment
- Instructor Unavailable
- Curriculum Change
- Administrative Decision
- Force Majeure

To add or rename reasons, open **Course Cancellation Reason** in the Desk (search bar). Mark old reasons as inactive rather than deleting them so historical cancellations keep a valid label.

### Cancelling a Course (registrar workflow)

A course can be cancelled only while it is in **Open for Enrollment** or **Enrollment Closed**. Once any grade is entered, the system moves the course to **Grading** and cancellation is no longer offered — at that point cancelling would risk losing transcript data.

Steps:

1. Open the Course Schedule form (Desk).
2. **Status** action group → **Cancel Course**.
3. Pick a Cancellation Reason in the dialog and confirm.

The system will:

- Mark every enrolled student's Course Enrollment Individual with `Course Cancelled`, the chosen reason, and a timestamp (distinct from a student-initiated withdrawal).
- Remove the affected Program Enrollment Course rows so cancelled courses don't appear in transcripts or progress audits. Rows that came from a partner seminary's transferred grades are preserved.
- Send a Seminary Announcement to all enrolled students explaining the cancellation.
- Free the students to enroll in another section or course immediately — duplicate-enrollment checks and "courses available" lists ignore cancelled-course CEIs.

Cancellation cannot be undone in this version. The dialog warns about this, so verify before confirming.

::: tip Emergency: cancel after grading started
If a course must be retired after grading has begun (e.g., the instructor dies mid-term), the procedure is: withdraw each enrolled student through the standard withdrawal flow, then have the prof (or registrar) click **Send Grades** on the empty roster. The course closes cleanly with no grades to dispute.
:::

::: warning Sales Invoices are NOT touched on cancellation
This version does not touch Sales Invoices when a course is cancelled. Reconcile manually — typically by cancelling the per-course invoice and creating a credit note. A future iteration may automate this; until then, treat invoice cleanup as a separate registrar task.
:::

### Minimum enrollment

Each **Course** has an optional **Default Minimum Enrollment** field. Each Course Schedule has its own **Minimum Enrollment** override (in the Lifecycle section). Both are *informational only* — the system does not auto-cancel courses that miss the threshold. Use the **Term Enrollment Status** report (Desk → Reports) to see, per Academic Term, every Course Schedule with its minimum, current enrollment, and the gap. Below-minimum courses are highlighted; cancel them via the workflow above before classes start.

### Late-grade reminders

When **Auto-advance** is on, every day the scheduler emails any instructor whose Course Schedule is past its grade-close deadline and still hasn't reached **Closed** state. The Registrar role is CC'd. The reminder is sent once per Course Schedule (idempotent flag prevents repeat sends).

### Auto-seeding assessment criteria from the Course

A new Course Schedule does not start empty. As soon as you save a fresh Course Schedule, its **Assessment Criteria** table auto-populates from the parent Course's `Assessment Criteria` (set up under **Course → Assessment** tab). The mapping copies title, criterion link, and weight verbatim — so if your Course has 100% of weight assigned, the new Schedule starts ready to teach without manual data entry.

If you change the Course on an existing schedule, the seeding does **not** re-run — it only fires once on creation. To pull a fresh copy, use **Import Course Template** below.

::: tip Set up Course assessments first
Configure the parent Course's Assessment Criteria (Course → Assessment tab) with weights summing to 100% before creating any Course Schedule. The same setup carries over automatically every term.
:::

### Reusing a Schedule as a Template

The auto-seed above covers the assessment criteria, but a fully-built Course Schedule typically has more: chapters, lessons (with videos, PDFs, instructor notes), and assessment links wired into specific lessons. To reuse all of that across terms:

1. Open the parent Course (Desk → Course → *your course*).
2. In the **Assessment** tab, set **Default Course Schedule Template** to the Course Schedule you want to use as the canonical structure.

Then, when creating a new Course Schedule for that course:

1. Save the new Course Schedule as usual (assessment criteria seed automatically — no manual entry needed).
2. On the new schedule's form, click **Actions → Import Course Template**.
3. The dialog pre-fills with the Course's default template; you can pick any other same-course Schedule. Click **Import**.

The import copies:

- **Chapters** (including SCORM packages, file references shared between schedules)
- **Lessons** — every one, regardless of whether it has an assessment link. Videos, PDFs, instructor notes, content, allow-discuss flag — all carry over.
- **Assessment criteria** — replaces what's on the new schedule (so the auto-seeded rows are overwritten by the template's). Lesson-level assessment links are remapped to the new schedule's criteria automatically.

The import does **not** copy:

- Roster, enrollments, or graded data
- Assessment due dates (stay null until you set them per-term)
- Cancellation history or workflow timestamps

A timeline Comment on the new schedule records what was imported, from where, when, and by whom.

**Constraints:**

- Available in **Draft** or **Open for Enrollment** state only — once enrollment closes, the structure is committed.
- Permitted to **Academics User**, **Seminary Manager**, or **Registrar**.
- Refuses if the target schedule already has chapters (one-shot operation, not a merge). To re-import, delete chapters first.
- Refuses if the source schedule has no assessment criteria, or if its weights don't sum to 100% — fix the source first.

::: warning Import is not reversible
There is no "undo" for the import. The dialog warns about this. If you imported the wrong template, delete the chapters and try again.
:::

## 13. User Roles

See [User Roles](../administration/user-roles.md) for configuring instructor, student, and administrator access.

## 14. Manual Input OR Import the following data

The following must be present for you to start your first term. 
If you have a small numer of students and prefer to do it manually, upon creation of a Student, SeminaryERP may create both a linked user and customer. However, it is also easy to import this data. You can follow [these instructions](https://docs.frappe.io/erpnext/data-import).

| ***Import*** in this order | ***Input manually*** in this order |
| --- | --- |
| 1. Users | 1. Students |
| 2. Customers | 2. Courses |
| 3. Students | 3. Holiday List |
| 4. Courses | 4. Program Enrollment |
| 5. Holiday List |  |
| 6. Program Enrollment |  |

Then, you need to link courses to your programs.
It is **strongly recommended** to double-check the import and **complement** the information on Courses before adding them to Programs. Courses will propagate several pieces of information to **Course Schedule**, so its completeness of information will expedite the work every term. 
To add them in bulk, navigate to Courses, select all courses you want to add to a Program, and click on **Actions** &rArr; **Add to Program**. A pop-up window will open where you need to select the Program that these courses should be added to. The window also has a checkbox to indicate if all the selected courses should be mandatory for this program or not.  

## 15. Import existing grades

SeminaryERP uses a single process to accept grades from other seminaries that also serves to import grades from any legacy system, manually or via CSV. See [Legacy Grade Import](legacy-grade-import.md) for the full workflow — one-time Partner Seminary setup, bulk equivalence creation, dry-run validation, and idempotent commit.

## 16. Add Instructors

Create an **Instructor** record for every person who will teach. Each instructor needs a linked **System User** (so they can log in to the Desk and LMS) and an **Instructor Type** that reflects how they are paid:

- **Volunteer** — unpaid or honorarium only. Click *Create Supplier* on the form to enable honorarium billing through Purchase Invoice.
- **Salaried** or **Per-Course** — requires [HRMS Payroll enabled](../modules/instructor-payment.md) and a linked Employee record.

For accreditation, fill in the **Education** section with each instructor's degrees, institutions, and supporting documents. When an Employee is linked, use *Education → Pull from Employee* to copy education already recorded in HRMS instead of re-entering it.

---

Once the above is in place, proceed to [Your First Term](first-term.md).
