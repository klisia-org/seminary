# 111 — Application questions from a shared pool, chosen per program

**Date:** 2026-11-24
**Status:** Accepted 2026-11-24
**Amends:** 091 §10 (agreements can be asked on the application too)
**Delivers:** SIS-ADM-01 (Yes)
**Related:** 019 (term admissions), 058 (requirement review), 068 (Person-first identity),
091 (agreements and documents), 112 (applicant review)

## Context

Every program's application asks the same questions. The doctype hard-codes them: reading habits,
computer literacy, employer, church reference, testimony and more. A certificate can't skip the
church reference, and a DMin can't ask about ministry years, without a code change. Reviewers ask
for each program's own questions and documents. Documents are already set per program (091 §10).
Education history and emergency contacts are facts about the person, but they stay on the
applicant. Admission drops the education rows, so a returning graduate types them again. No school
is live, so these fields can move without migrating anyone's answers.

## Decision

1. **Application Question** is a pool shared by all programs. Each one has a label, help text, a
   type (Short text, Long text, Select, Check, Date, Number, Phone, Email, or Table section), the
   Select options, a group heading (e.g. *Church*, *Employment*), and an Active check.
2. **Program.application_questions** is a child table that links pool questions, with *Required*
   and *Order* on each row. The form shows the chosen program's rows by order, under their group
   headings. Required answers are checked on the server.
3. **Table sections** are three fixed pool entries: *Education history*, *Emergency contacts* and
   *References*. A program shows one only if it links it. *Required* means at least one row.
4. **Answers** go into a `Student Applicant Answer` child table. It holds the question, the label
   and group as they were when the applicant applied, and the answer. Answers can't be changed
   once the application is In Review (112), so every reviewer scores the same file.
5. **Person Education** is a new record, one per qualification: Person, institution, country,
   degree, level (Secondary school, Certificate or Diploma, Bachelor's, Master's, Doctoral,
   Other), field of study, year completed (blank while in progress), notes, and an optional
   Person Document for the diploma (091). The applicant's education rows gain a read-only
   `person_education` link. On insert, each row creates a Person Education, as 091 §10 does for
   documents. Later applications by the same Person show those rows already filled in.
6. **Emergency contacts move to Person.** `Person.emergency_contacts` holds name, relation, phone
   and email. The applicant's rows are written there on insert. `Student.contacts` is removed, and
   a patch moves its emergency rows to the Person. **References** stay on the applicant, because
   they speak to one application. Their rows gain phone and email, and admission no longer copies
   them to the Student.
7. **Fixed fields stay.** These are the fields that feed the Person, plus program, term, Term
   Admission, documents, and the requirement-review request (058).
8. **Moved to the pool:** reading, computer literacy, email use, the employment block, the church
   block, gospel understanding, testimony, and program expectations. Their columns are dropped.
   Install seeds them as pool questions and links them to every existing program, so today's form
   is unchanged until a school edits it.
9. **Removed, with no replacement:**
   - *Highest degree*, which is derived from Person Education.
   - *Disability* and *accommodations*, because asking about disability before admission is
     restricted (US Section 504) and is sensitive data (LGPD). It also put the answer in front of
     admission reviewers.
10. **Doctrinal statement → agreement** (amends 091 §10). An `ask_on_application` rule may name an
   Agreement Template. The applicant signs its current version on the form, which creates the
   Signed Agreement that enrollment then finds. `ds2`, `ds_body` and `signdoctrine` are removed.
   `Doctrinal Statement.use_in_student_admission` stays: it picks the statement a student
   agreement shows as `{{ doctrinal_statement }}`.
11. **One application form.** `Program.application_web_form` and
   `Seminary Settings.default_application_web_form` are removed. They let a program use a copied
   Web Form, but every field still had to exist on the doctype. The built-in form now shows each
   program's questions. `assert_capture_complete` stays, for API clients.
12. **Who edits:**
   - The pool and the program rows: Seminary Manager and Registrar.
   - Person Education and emergency contacts: Registrar and Seminary Manager. The person can see
     their own rows.
   - Seeded labels are wrapped in `_()` so they are translated. Labels a school writes are its own
     text.

## Consequences

- A school sets each program's form on Desk, with no code change. Shared questions are written
  once.
- Education history and emergency contacts follow the person from one application to the next.
- Reports can't filter on a pooled answer as a column. They read the answers table. Data another
  report needs has to be a fixed field or come from another record.
- A pool question that has answers can't be deleted, only made inactive. Old answers keep their
  own label, so editing a question doesn't rewrite past applications.
- An agreement signed on the application is a full Signed Agreement, with its version and
  evidence. Before, it was an unversioned signature image.
- Schools can no longer ask for accommodations on the application. A request made after admission
  needs its own decision.

**Rejected:**
- Separate question sets for each program. They are simpler to explain, but the same church or
  testimony question would be copied into every program.
- Person Education as a child table of Person. A diploma Person Document and an applicant row
  each need to link to one qualification, and a child row is a weak link target.
