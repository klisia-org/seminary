# User Roles

SeminaryERP uses Frappe's role-based permission system to control access. The
module defines and owns the following roles. A user may hold more
than one role. ERPNext roles (for accounting, etc.) should be selected per your policy.
See [ERPNext Module Access documentation.](https://docs.frappe.io/erpnext/adding-users#27-allow-module-access)

## Staff roles (Desk)

- **Seminary Manager** — module administrator. Full access to academic and
  configuration doctypes, including workflow actions.
- **Registrar** — student-records lifecycle: admissions, enrollment, academic
  terms, withdrawals, graduation and transcripts, and disciplinary records.
- **Program Chair** — programs and curriculum authority: programs, courses,
  assessments, grading, and academic policy. (This role was previously named
  *Academics User*.)
- **Instructor** — teaches and grades their own courses, and may report
  disciplinary incidents.

## What an instructor may do on a section

The Instructor role opens the door; the **Category** on each section's
instructor row decides what they may do there. Every Instructor Category has
four checkboxes:

| Checkbox | Covers |
|---|---|
| **Edits course content** | Course outline, lessons, assessments, late policy, student groups |
| **Grades** | Grades and comments on submissions, due-date exceptions, sending final grades |
| **Records attendance** | Taking attendance for the section's meetings |
| **Posts to the class** | Announcements, messages to all of the section's students, instructor replies in discussions |

The starter categories come set like this:

| Category | Content | Grades | Attendance | Posts |
|---|---|---|---|---|
| Instructor of Record | ✓ | ✓ | ✓ | ✓ |
| Co-Instructor | ✓ | ✓ | ✓ | ✓ |
| Graduate Teaching Assistant | | ✓ | ✓ | ✓ |
| Grader | | ✓ | | |

A category you add starts with all four. Change them at **Desk → Instructor
Category**. If a section row has no category, the instructor's default category
applies; if that is empty too, they may do all four. Everyone on a section
still sees its students and gradebook, whatever their category. Program
Chairs and Seminary Managers are not limited by categories, and neither is the
Registrar where the Registrar may keep academic records.

## Observers

To let someone read a course without teaching it (a colleague reviewing the
teaching, an advisor, an accreditation visitor, a ministry supervisor), add
their Person to the **Observers** table on the Course Schedule, with an
optional **Until** date and a reason. They need a user account but no role.

Once the section is published, an observer finds it under their courses and
can read the outline, lessons, assessments and announcements. They do not see
the roster, grades, submissions or discussions. Access stops after the
**Until** date or when the section is cancelled.

If someone should also see students' work, add them as an instructor in a
category with no checkboxes ticked instead.

## Portal roles (frontend)

- **Student** — enrols in courses, submits work, and views their own records and
  published curriculum.
- **Alumni** — graduated students; access to the alumni portal and their own
  records.
- **Student Applicant** — prospective students completing the application
  web form.

## Portal vs Desk access

Students, alumni and applicants use the LMS portal (frontend) and have no Desk
access; they are redirected to the portal on login. Staff work in the Frappe
Desk for configuration, records and reporting.

## Notes

- `System Manager` (Frappe core) retains super-admin access everywhere.
