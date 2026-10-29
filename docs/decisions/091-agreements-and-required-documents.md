# 091 — Agreements and required documents for students and instructors

**Date:** 2026-10-20
**Status:** Accepted 2026-10-20; implemented 2026-10-20 (d8ec8259)
**Delivers:** SIS-REC-06 (Yes), SIS-ADM-03 (Partial)
**Amended 2026-10-20:** §8 — signature fields in the template.
**Related:** 042 (Person spine), 068 (Person-first identity), 071 (tax identifiers), 083 (bulk enrollment), 084 (staff-enrolled programs)

## Context

Schools want students to sign contracts when they enrol, such as a Brazilian *contrato de
prestação de serviços educacionais*. The contracts are filled in for each student. Schools also
want students to upload documents, such as a bachelor's diploma, an ID or a transcript. Instructors
need the same thing, for example signing the doctrinal statement every year. One school does this
today with a templated web page it built itself. Seminary has no model for any of it: Student
Applicant has two loose Attach fields and one Signature field, with no version, evidence or review.
This ADR sets one set of parts that students and instructors share.

## Decision

1. **The parts belong to the Person**, so the same parts serve students and instructors:
   - Document Type
   - Person Document
   - Agreement Template
   - Signed Agreement
   - Person Requirement
2. **Requirement Rule** is a child table that says what a role must provide. It is used in two
   places: Program (*Enrollment requirements*) and Seminary Settings (*Instructor requirements*).
   Each row has:
   - `kind`: Agreement or Document;
   - `agreement_template` or `document_type`, depending on the kind;
   - `blocking`;
   - `due_days`;
   - `renewal`: Not needed, Every Academic Term or Every Academic Year;
   - `instructions`;
   - `ask_on_application`, which is used on Program only (§10).
3. **Person Requirement** is one thing one person owes.
   - Fields: `person`, `reference_doctype` / `reference_name` (a Program Enrollment or an
     Instructor), the rule's fields, `start_date`, `due_date`, and `academic_term` or
     `academic_year` for a renewing row.
   - `status` is Pending, Submitted, Satisfied or Waived. It is recomputed whenever the record
     that satisfies it changes, and is never typed in.
   - `satisfied_by` points to that record. `waived_by` and `waiver_reason` record a waiver, which
     needs a reason.
   - It is a separate doctype, not a child table, so one portal page and one review queue serve
     both roles.
4. **When rows are created.**
   - *Students:* rows are created when a Program Enrollment is submitted, copying the program's
     rules. Changing a program later does not change existing enrollments. Staff can add a row by
     hand. A Program button adds any missing rows to the active enrollments.
   - *Instructors:* rows are created when an instructor becomes Active, and by a daily sweep, both
     reading Seminary Settings. A rule a school adds later therefore reaches every active
     instructor.
5. **Renewal.** When a new academic term becomes current, the daily sweep adds a Pending row for
   each renewing rule:
   - for the new term, if the rule renews every term;
   - for the new year, if the rule renews every year and the year has changed.

   Earlier rows stay as history. A renewed row is satisfied only by:
   - a Signed Agreement made for that row; or
   - a Person Document accepted on or after the row's `start_date`.
6. **Document Type** is a list each school keeps, for example *Bachelor's diploma*, *RG* or
   *Proof of address*. Its fields are `description`, `allowed_extensions`, `needs_review` and
   `valid_months`. **Person Document** has:
   - `person`, `document_type` and a private `file`;
   - `status`: Submitted, Accepted, Rejected or Expired;
   - `reviewed_by`, `reviewed_on`, `rejection_reason` and `valid_until`.

   Any Accepted, unexpired document of the right type satisfies a Document row, whatever
   enrollment it was uploaded for. If the type does not need review, the document is accepted when
   it is uploaded. When staff reject a document, the person is asked to upload it again.
7. **Agreement Template** has a `title`, a rich-text `body` with Jinja fields, a `countersign_role`
   and read-only `versions` rows.
   - When a body that someone has already signed is saved, it becomes a new version. A body no one
     has signed is updated in place.
   - The body is rendered in Jinja's sandbox with: `person`, `student`, `program`,
     `program_enrollment`, `instructor`, `school`, `doctrinal_statement` and `today`. The
     `doctrinal_statement` is the active one marked for admission (for a student) or for
     instructors (for an instructor).
   - An `agreement_context` hook adds more fields. oikonomos and tamias use it for fees.
8. **Signed Agreement** is submitted and never changed. It stores:
   - the person, the requirement, the template version and the rendered HTML;
   - a private PDF on the Seminary Settings letterhead, with an evidence block;
   - SHA-256 hashes of the HTML and the PDF;
   - `signed_on`, the user, the IP address, the user agent, the name the signer typed and an
     optional drawn signature.

   The portal asks the signer to tick a consent box before signing. When the template has a
   countersign role, someone holding that role countersigns on Desk. The same evidence and a final
   PDF are recorded for them, and the agreement is complete only then.

   *Amended:* a template places `{{ signature }}` and `{{ countersignature }}` where each party
   signs. While the person reads, they render as empty, labelled lines. That text is what is stored
   and hashed. Each PDF fills the lines with the drawn signature (if any), the typed name and the
   time. The countersigner may draw a signature too. The evidence block stays at the end of every
   PDF, so a template without these fields still records who signed.
9. **What blocking stops.** A blocking row that is not Satisfied or Waived by its due date:
   - stops a student's course self-enrollment;
   - shows as a warning column in Bulk Course Enrollment (083);
   - shows a warning when the instructor is put on a Course Schedule.

   It never stops a Program Enrollment or an Instructor being created. A row that is not blocking
   only sends reminders.
10. **Asking on the application.** Student Applicant's `document_id` and `education_docs` fields
    are removed. A `documents` table takes their place, with `document_type`, `file` and a
    read-only `person_document`.
    - The application form fills the table from the chosen program's `ask_on_application` rules.
    - On insert, each file becomes a Submitted Person Document for the applicant's Person.
    - When the applicant enrols, their requirements find those documents already there.
    - A patch moves the old files into the table and into Person Documents, never dropping any. It
      creates two Document Types for them only if such files exist: *Identity document* and
      *Education documents*. Files of Admitted applicants become Accepted, and all others
      Submitted.
11. **Portal and staff.**
    - The portal has a *Requirements* page for students and instructors. It shows *Sign* and
      *Upload* actions. A panel on the Courses page and a badge on the sidebar link show what is
      open.
    - Staff accept or reject documents and countersign on Desk.
    - Notices go through `comms.send_message` in three cases: when rows open, on the due date, and
      when a document is rejected.
12. **E-signature providers are out of scope.** Signing is a simple electronic signature recorded
    inside the platform. Between private parties in Brazil that is valid under MP 2.200-2/2001 art.
    10 §2. Integrations with ClickSign, D4Sign or DocuSign are left for a later decision, which
    would add a provider seam on Signed Agreement.

**Rejected:**
- **A web form per contract** (what the school does today). It has no versions, no evidence and
  nothing to say whether someone has signed.
- **aretenic Read & Acknowledge (025).** It acknowledges controlled documents. It does not fill in
  a document per person, and seminary-only schools need these features too.
- **Separate systems for students and instructors.** The two would drift apart and need two review
  queues.

## Consequences

- A school sets up its contracts and document lists without custom code. A document is uploaded
  once for each person, whatever role they hold.
- Each Signed Agreement carries its own evidence. A later template edit never changes what someone
  signed.
- Status is a derived cache, so every writer of a satisfying record must recompute it. The daily
  sweep also expires documents past `valid_until`.
- The only signer is the student or the instructor. Seminary students are adults, so there is no
  guarantor or co-signer.
- ID and diploma scans are personal data under LGPD. Retention rules for Rejected and Expired files
  are still to be decided.
- Schools that used the two applicant Attach fields must add `ask_on_application` rules to keep
  asking for those files.
