# Withdrawal

The withdrawal module handles course drops and institutional withdrawals with configurable per-term rules.

## Overview

Students can request withdrawal through the LMS portal. 
Rules governing deadlines, penalties, and refund eligibility are configured by academic users on the Desk view.

## Key concepts
- **Penalty-Free Window** — a configurable period after term start where withdrawal carries no academic penalty
- **Withdrawal Reason** — a separate doctype allowing institutions to track and report on why students withdraw
- **Refund/Scholarship Handling** — financial implications configured alongside withdrawal rules

### Course Withdrawal Request
Initiated by the student (if allowed in Seminary Settings) or by administrators/academic users

#### Student Request
Students can request withdrawal from any course they are currently enrolled and have access on the Portal.
Navigate to a Course --> My Status: At the bottom of the page, students can request widrawal from that course. The system will display on the top of this page the status of the course withdrawal request.

Students will need to provide a [pre-configured reason](#withdrawal-reasons) and any support documentation required by that specific reason. The system will auto-populate required fields.

Students may also create withdrawal requests for other courses, alongside this one by selecting the appropriate choice in Withdrawal Scope. Each course will track its own Course Withdrawal Request, but seminary administrators will see the related requests.

![Withdrawal Requests Portal screen](/modules/withdrawal/img/withdrawal_request_portal.png)

#### Registar Request
Registars or other assigned users can create the Course Withdrawal Request within Desk.




### Withdrawal Reasons
It is a good practice to standardize and evaluate periodically the reasons that compel students to drop from courses. Many accrediting agencies require that and SeminaryERP makes it easier to fulfill this requirement.
When a withdrawal reason is created, administrators will give a name, a description, if it will be mandatory to attach support documentation (it is always available, just not mandatory) and if so, what label will be displayed to students. This is to make it easier to students to know exactly what is needed to submit. Two informational rich text editors provide initial documentation for students and staff. 

![Withdrawal Reasons screen](/modules/withdrawal/img/withdrawal-reasons.png)

### Withdrawal Rules
1. Give the rule with a clear name, easy to understand by itself.
2. The checbox "Exclude from Grade calculation" signals that this will not count towards the final GPA
3. Grading Symbol: How do you want this to appear on the transcript (can be a word, not necessarily a symbol)
4. Allow Partial Credit: The student submitted assessments may be used for partial credit (this feature is under development)
5. If the main setting in "Seminary Settings" allows for it, a [**Term-Based Date**](#term-widrawal-rules) may be calculated automatically for each term. When it is checked, additional fields will be available to calculate the "Applies until" date for each term. Note that since the rule is applied per term (even if it impacts course schedules), the date thresholds are always relative to the term.
6. Refund: If the checkbox is marked, a child table becomes available. This will define how much will be refunded and to whom, if the rule applies. That is, the system will automatically identify the Sales Invoice for that course and create a Credit Note against it, following the same tax procedure as the Sales Invoice. Three types of Payers are contemplated by the rules: Student (i.e., the ERPNext Customer associated with the Student), Scholarships (the ERPNext Customer associated with Scholarships in Seminary Settings), and Other Payers (as SeminaryERP also gives the option for churches, denominations to pay for part of tuition).

![Withdrawal Rules screen](/modules/withdrawal/img/withdrawal-rules.png)

### Term Widrawal Rules

If there is a need for manual adjustment of the dates a rule apply, this can be done on Desk, Term Withdrawal Rules.

![Term Withdrawal Rules screen](/modules/withdrawal/img/withdrawal-term-rules.png)