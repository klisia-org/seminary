# Instructor Payment

SeminaryERP supports three different ways of paying instructors: as **volunteers** receiving honoraria, as **salaried** employees, or on a **per-course / per-student** basis. This page walks you through setting it all up.

## Overview

Each instructor record has an **Instructor Type** field. Pick the one that describes how the school compensates that person:

| Instructor Type | How they're paid | What you'll set up |
|---|---|---|
| **Volunteer** | Honorarium / "love offering" per visit | A Supplier record + Purchase Invoices |
| **Salaried** | Fixed recurring salary | Standard HRMS Employee + Salary Structure |
| **Per-Course** | Paid per course taught, optionally per enrolled student | HRMS Employee + the Instructor Pay component (automated) |

You can mix and match across your faculty — some salaried, some per-course, some volunteers — all in the same payroll system.

The **Volunteer** flow works on its own with no extra apps. The **Salaried** and **Per-Course** flows require the Frappe HRMS app to be installed on your site.

---

## Prerequisites (for Salaried and Per-Course only)

Skip this section if you only plan to pay volunteers via Purchase Invoice.

### 1. Install HRMS

Ask your bench administrator to install the Frappe HRMS app on your site. From the bench terminal this is:

```
bench get-app hrms
bench --site <your-site> install-app hrms
```

> **Note:** HRMS `v16.5.1` has a known installation bug against ERPNext v16. If the install fails with a `repost_allowed_types` error, pin HRMS to tag `v16.4.8`:
>
> ```
> cd ~/frappe-bench/apps/hrms
> git checkout v16.4.8
> ```
>
> …then retry `bench install-app hrms`.

### 2. Enable HRMS Payroll in Seminary Settings

Open **Seminary Settings** in Desk, scroll to the **HR / Payroll** section, and check **Enable HRMS Payroll**. Save.

Saving will:

- Add the per-category instructor pay fields to every Salary Slip.
- Create a ready-to-use Salary Component called **"Instructor Pay"**.

If you see an error saying HRMS isn't installed, return to step 1.

### 3. Set the HRMS Live Date

Still in **Seminary Settings → HR / Payroll**, fill in **HRMS Live Date (Pay Cutoff)** with the date your school is starting to use HRMS for payroll.

Courses whose start date is **before** this cutoff will *not* appear in payroll. This protects you from accidentally sweeping years of historical courses into your first payroll run. Leave it blank only if you want to include every course on record.

### 4. Choose a payment split policy

**Instructor Payment Split** tells the system when per-course pay is released across payroll runs:

- **End of period** *(default)* — the full amount is paid on the payroll slip whose period contains the course's end date.
- **50% at start + 50% at end** — half paid on the slip containing the course's start date, the other half on the slip containing the course's end date.

Pick one. You can change it later, but changes only affect courses paid going forward.

---

## Instructor Categories

Every instructor assigned to a course carries a **Category** — "Instructor of Record", "Graduate Teaching Assistant", "Grader", etc. Categories drive two things: accreditation reports and how much the instructor earns.

The system ships with four default categories: **Instructor of Record**, **Co-Instructor**, **Graduate Teaching Assistant**, **Grader**. You can add, rename, or hide them at **Desk → Instructor Category**.

Note: Currently, there is no configuration for different payment per program or program level. If this is important for you, please create an issue in our github repository. One way to make this without coding is just to create a new category, e.g., Instructor of Record - PhD with different pay rate values. 

### Attaching pay rates to a category

Open an Instructor Category and scroll to **Pay Rates**. Each row is one rate:

| Column | What it means |
|---|---|
| **Pay Mode** | `Per-Course` (flat amount per course) or `Per-Student` (amount × roster size) |
| **Amount** | How much to pay |
| **Currency** | The currency for this rate (supports USD for donor-funded programs, local currency for local) |
| **Effective From** | The date this rate takes effect |
| **Active** | Check the current rate. Uncheck older ones to keep the history visible but unused |

You can have one Per-Course row and one Per-Student row active at the same time — the system pays both. To change a rate, **uncheck Active on the old row** and **add a new row** with the new amount and a new Effective From date. This keeps the pay history for past payroll slips accurate.

#### Example: "Instructor of Record" category

| Pay Mode | Amount | Currency | Effective From | Active |
|---|---|---|---|---|
| Per-Course | 200 | USD | 2024-01-01 | ☐ (old rate) |
| Per-Course | 300 | USD | 2026-01-01 | ☑ (current) |
| Per-Student | 10 | USD | 2024-01-01 | ☑ |

An Instructor of Record teaching a Fall 2025 course with 8 students would earn 200 + 80 = **$280**. The same course in Spring 2026 would earn 300 + 80 = **$380**.

---

## Assigning a category on each course

When you create or edit a **Course Schedule**, the **Instructors** table now has a **Category** column. Pick the category for each instructor on that course. The category determines which rates apply for that person on that specific course.

When HRMS Payroll is enabled, saving a Course Schedule without a category on every instructor row is blocked — this prevents forgetting someone's pay.

After assigning instructors, open each instructor's record once and click **Update Instructor Log** (or wait for it to refresh on next load). This syncs the course to their log, which is what payroll reads from.

---

## Setting up each payment flow

### Volunteer flow

For guest lecturers or visiting professors who receive an honorarium:

1. Create the **Instructor** record with **Instructor Type = Volunteer**.
2. Open the Instructor form and click **Actions → Create Supplier**. A Supplier record is created automatically with the name, email, and phone copied from the Instructor. The Supplier link is saved back to the Instructor.
3. Each time you want to pay the volunteer, create a **Purchase Invoice** against that Supplier. Add an Item (e.g., "Instructor Honorarium") and the amount.
4. Submit the Purchase Invoice, then create a **Payment Entry** to disburse.

Volunteers do **not** need an Employee record and do **not** appear in Payroll Entry. Their compensation is tracked in the usual supplier ledger.

### Salaried flow

For full-time or part-time staff on a recurring salary:

1. Create the **Employee** record (HR module).
2. Create or edit the **Instructor** record and set **Instructor Type = Salaried**. Link to the Employee.
3. Create a **Salary Structure** (e.g., "Instructor — Full-Time") with the Salary Components you need (Base, allowances, deductions).
4. Create a **Salary Structure Assignment** connecting the Employee to the Structure.
5. Run **Payroll Entry** on your normal monthly schedule. HRMS does the rest.

No seminary-specific configuration is needed — this is stock HRMS.

### Per-Course flow

For instructors paid per course taught:

1. Create the **Employee** record.
2. Create or edit the **Instructor** record and set **Instructor Type = Per-Course**. Link to the Employee.
3. Make sure the Instructor Category assigned on each of this instructor's Course Schedules has **Pay Rates** defined (see section above).
4. Create a **Salary Structure** called something like "Instructor — Per-Course". In the **Earnings** table, add a single row:
   - **Salary Component:** `Instructor Pay` *(this component was auto-created when you enabled HRMS Payroll — don't recreate it)*
5. Assign the Structure to the Employee via **Salary Structure Assignment**.

That's it. When Payroll Entry runs, the system calculates the pay based on the courses taught in that period × the category's rates, and puts the result on the slip.

You do **not** need per-category components ("IoR Pay", "GTA Pay"). The single "Instructor Pay" component handles all categories, because rates live on the categories themselves.

---

## Running payroll

Run Payroll Entry the same way you always have:

1. **HR → Payroll → Payroll Entry → New**.
2. Set the period dates, company, and the Salary Structure Assignment filter.
3. Submit. HRMS generates one Salary Slip per employee.

Open a generated slip. Near the top, in the **Instructor Pay Inputs** section, you'll see:

- **Computed Instructor Pay** — the calculated total.
- **Instructor Log Summary** — a read-only breakdown showing, for each course paid on this slip: the course, category, rate applied, portion (100% or 50%), payment event (Start / End), and subtotal.

This is your audit trail. If something looks off, this table tells you exactly which courses and rates were used.

### Re-running a payroll

If you cancel a Salary Slip and re-run Payroll Entry, the system automatically excludes courses that were paid on the cancelled slip. **You cannot accidentally double-pay.**

---

## Reconciling: the Unpaid Instructor Log report

After each payroll cycle, check **Reports → Unpaid Instructor Log**. It lists every teaching row (instructor × course) whose term has ended but which hasn't been 100% paid.

This catches the usual mistakes:

- An instructor who doesn't have an Employee linked, so they were skipped.
- A Course Schedule with no category assigned (shouldn't happen with validation on, but caught if it does).
- A category with no pay rate defined.
- A payroll run that simply wasn't done for a given month.

Filters at the top let you narrow by instructor, academic term, or category.

---

## Day-to-day tasks

### Adding a new Instructor Category

1. **Desk → Instructor Category → New**. Give it a name, description, and check **Is Instructor of Record?** if it should count toward accreditation.
2. Open Seminary Settings and save it once (no changes needed — just Save). This refreshes the Salary Slip fields so the new category's counters appear on future slips.
3. Add pay rates to the category as described above.

### Changing a rate (e.g., year-end raise)

1. Open the Instructor Category.
2. On the current active row in **Pay Rates**, **uncheck Active**.
3. Add a new row with the new amount and a new **Effective From** date.
4. Save.

Historical slips automatically keep using the old rate (based on the course's start date), so past payroll is not affected.

### Starting a new academic year with a new Live Date

If you want to reset what counts for HRMS payroll (e.g., your first year used a pilot policy), update **Seminary Settings → HRMS Live Date** to the new cutoff. Only courses starting on or after the new cutoff will be considered.

---

## Common questions

**Can the same instructor have different categories in different courses?**
Yes. Category is per Course Schedule Instructor row, not per instructor. A professor might be "Instructor of Record" in one course and "Co-Instructor" in another.

**What happens if I forget to assign a category to a course?**
When HRMS Payroll is enabled, saving the Course Schedule is blocked until every instructor row has a category. Categories also default to blank; you can use a script or bulk update to backfill.

**What if an intensive course runs inside a broader term?**
Fill in **Start Date** and **End Date** on the Course Schedule itself. When those dates are set, the system uses them instead of the academic term dates — so a two-week intensive is paid on the slip whose period contains the intensive's end, not the term's.

**What if a volunteer later becomes a paid instructor?**
Change their **Instructor Type** from Volunteer to Salaried or Per-Course. Link to an Employee record. The old Supplier link stays (for historical Purchase Invoices) but is ignored going forward.

**Can I see what a slip *will* pay before running it?**
Yes. Create a Salary Slip manually for the employee and period — the **Instructor Log Summary** section populates as soon as you save as draft.
