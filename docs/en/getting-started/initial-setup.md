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

A [Payment Terms Template](https://docs.frappe.io/erpnext/payment-terms-template) bundles one or more [Payment Terms](https://docs.frappe.io/erpnext/payment-terms) (e.g. *50% at enrollment, 50% mid-term*). Templates are attached to Fee Categories and to invoices, so create the templates you actually need before setting up Fee Categories.

## 8. Academic Year

Create your first **Academic Year**. It is a container for Academic Terms — terms cannot extend beyond their year's boundaries. Some fees and administrative tasks are scheduled once per year.

## 9. Fee Category

A **Fee Category** is SeminaryERP's billing automation unit. Each category links:

- An **ERP Item** (what is billed)
- A **Payment Terms Template** (how it is billed)
- A **Category Type** (Item Group) for reporting
- A **Trigger Event** (when the charge is created — e.g. program enrollment, term enrollment, per-credit)
- Flags for **Is Academic Credit** and **Is Audit** --Only fee categories with these indicators will be calculated per credit hour (in the case of audits, see also Seminary Settings)

Set up one Fee Category per chargeable event so SeminaryERP can post invoices automatically when the event happens. This is why Items, Price Lists, and Payment Terms must exist first.

## 10. Academic Term

Create your first **Academic Term** inside the Academic Year:

1. Set start and end dates
2. Configure enrollment windows and withdrawal deadlines — see [Academic Calendar](../modules/academic-calendar.md) and [Withdrawal](../modules/withdrawal.md) for how these dates drive downstream rules

## 11. Program

A **Program** is the curriculum structure students enroll into (e.g. *M.Div.*, *Certificate in Biblical Studies*). It defines required credits/terms, courses, tracks, emphases, and program-level fees. Create at least one program before opening enrollment. Detailed program modeling (tracks, emphases, credit requirements) is covered under [Enrollment](../modules/enrollment.md).

## 12. User Roles

See [User Roles](../administration/user-roles.md) for configuring instructor, student, and administrator access.

## 13. Manual Input OR Import the following data

The following must be present for you to start your first term:
1. Users
2. Customers
3. Students
4. Courses (Need to link them to programs)
5. Holiday List

If you have a small numer of students and prefer to do it manually, upon creation of a Student, SeminaryERP may create both a linked user and customer. However, it is also easy to import this data. You can follow [these instructions](https://docs.frappe.io/erpnext/data-import).

## 14. Import existing grades
SeminaryERP uses a single process to accept grades from other seminaries that also serves to import grades from any legacy system, manually or via CSV. See [Legacy Grade Import](legacy-grade-import.md) for the full workflow — one-time Partner Seminary setup, bulk equivalence creation, dry-run validation, and idempotent commit.
---

Once the above is in place, proceed to [Your First Term](first-term.md).
