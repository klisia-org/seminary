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
