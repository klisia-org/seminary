# Withdrawal

The withdrawal module handles course drops and institutional withdrawals with configurable per-term rules.

## Overview

Students can request withdrawal through the LMS portal. 
Rules governing deadlines, penalties, and refund eligibility are configured by academic users on the Desk view.

## Key concepts

### Course Withdrawal Request
Initiated by the student or administrators/academic users

#### Student Request
Students can request withdrawal from any course they are currently enrolled and have access on the Portal.
Navigate to a Course --> My Status: At the bottom of the page, students can request widrawal from that course. The system will display on the top of this page the status of the course withdrawal request.

Students will need to provide a [pre-configured reason](#withdrawal-reasons) and any support documentation required by that specific reason. The system will auto-populate required fields.

Students may also create withdrawal requests for other courses, alongside this one. Each course will track its own Course Withdrawal Request, but seminary administrators will see the related requests.

### Withdrawal Reasons
It is a good practice to standardize and evaluate periodically the reasons that compel students to drop from courses. Many accrediting agencies require that and SeminaryERP makes it easier to fulfill this requirement.
When a withdrawal reason is created, administrators will give a name, a description, if it will be mandatory to attach support documentation (it is always available, just not mandatory) and if so, what label will be displayed to students. This is to make it easier to students to know exactly what is needed to submit. Two informational rich text editors provide initial documentation for students and staff. 

![Withdrawal Reasons screen](/modules/withdrawal/img/withdrawal-reasons.png)

### Withdrawal Rules

- **Penalty-Free Window** — a configurable period after term start where withdrawal carries no academic penalty
- **Withdrawal Reason** — a separate doctype allowing institutions to track and report on why students withdraw
- **Refund/Scholarship Handling** — financial implications configured alongside withdrawal rules
