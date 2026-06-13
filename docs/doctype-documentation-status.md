# Doctype Documentation Status

**Living tracker** of user-facing documentation coverage for every Seminary
doctype. Keep it updated across sessions: when a new doctype is added, add a row;
when a doc page is written, set the doctype's `documentation` link and flip its
column here.

There are two distinct, user-facing surfaces this tracks:

1. **Description** -- the native Frappe doctype `description` (a top-level key in
   the doctype JSON). It shows on hover in a Workspace and at the top of the
   doctype's list, so it must read for the *end user* deciding "is this the
   record I need?" -- not for developers.
2. **Documentation** -- the native Frappe doctype `documentation` key (also
   top-level). When set, Frappe shows a Help icon on the form that opens that
   URL. Our pattern is always a page on **https://docs.seminaryerp.org**, ideally
   with the most specific sub-heading anchor, e.g.
   `https://docs.seminaryerp.org/modules/discipline.html#reporting-from-the-instructor-portal`.

Child tables (`istable: 1`) are intentionally excluded -- they are never browsed
on their own.

## Conventions

**Description tone** (it is end-user marketing/orientation, not a spec):
- 1-2 sentences (3 max), plain present tense, ASCII only.
- Start with the noun ("A building within a Campus..."), never "This doctype".
- Say what the record is and when you'd create/use it.
- No developer jargon, no raw fieldnames, and **no ADR references** -- those
  belong in `docs/decisions/`, not in something an end user reads.

**Editing the JSON safely.** Frappe exports doctype JSON with sorted keys; to set
the two fields without churning the rest of the file, use this recipe (it
reproduces Frappe's export byte-for-byte -- do not hand-edit the keys):

```python
import json
f = "seminary/seminary/doctype/<name>/<name>.json"
d = json.load(open(f))
d["description"] = "<ascii description>"
d["documentation"] = "<docs url>"      # omit / d.pop() if no page exists yet
with open(f, "w") as o:
    json.dump(d, o, indent=1, sort_keys=True, ensure_ascii=True)
    o.write("\n")
```

New docs pages live under `docs/en/` and must be registered in the English
(`root`) sidebar in `docs/.vitepress/config.mjs` (the `pt`/`es` mirrors are
filled by Crowdin). To find the right anchor, slugify the heading the VitePress
way: lowercase, strip punctuation, spaces -> `-`, and a leading digit gets a `_`
prefix (so `## 12. Course Schedule Lifecycle` -> `#_12-course-schedule-lifecycle`).

## Status (89 non-child doctypes)

- **Description:** 89 / 89 have a user-facing description.
- **Documentation:** 75 / 89 link to a docs page.
  14 have no page yet (see backlog below; 2 are deliberate "won't document"
  decisions).

Legend: Description / Documentation = ✓ present, ✗ missing. The
Documentation ✓ links to the live page.

| Doctype | Description | Documentation | Needs |
| --- | :---: | :---: | --- |
| Academic Term | ✓ | [✓](https://docs.seminaryerp.org/modules/academic-calendar.html#academic-term) |  |
| Academic Year | ✓ | [✓](https://docs.seminaryerp.org/modules/academic-calendar.html) |  |
| Alumni Profile | ✓ | [✓](https://docs.seminaryerp.org/modules/alumni.html) |  |
| Assessment Criteria | ✓ | [✓](https://docs.seminaryerp.org/modules/grading.html#setting-up-an-assessment-plan-for-a-course) |  |
| Assignment Activity | ✓ | [✓](https://docs.seminaryerp.org/modules/grading.html#assignment) |  |
| Assignment Submission | ✓ | [✓](https://docs.seminaryerp.org/modules/grading.html#assignment) |  |
| Bible API Settings | ✓ | [✓](https://docs.seminaryerp.org/administration/bible-api.html) |  |
| Building | ✓ | [✓](https://docs.seminaryerp.org/modules/rooms.html#building) |  |
| Campus | ✓ | [✓](https://docs.seminaryerp.org/modules/rooms.html#campus) |  |
| Channel Provider Account | ✓ | [✓](https://docs.seminaryerp.org/modules/communication.html#channel-provider-accounts) |  |
| Chapel | ✓ | [✓](https://docs.seminaryerp.org/modules/graduation-requirements.html#example-1-chapel-attendance-self-check-in) |  |
| Chapel Attendance | ✓ | [✓](https://docs.seminaryerp.org/modules/graduation-requirements.html#example-1-chapel-attendance-self-check-in) |  |
| Communication Channel | ✓ | [✓](https://docs.seminaryerp.org/modules/communication.html#communication-channels) |  |
| Communication Log | ✓ | [✓](https://docs.seminaryerp.org/modules/communication.html#communication-log) |  |
| Communication Template | ✓ | [✓](https://docs.seminaryerp.org/modules/communication.html#communication-templates) |  |
| Communication Trigger | ✓ | [✓](https://docs.seminaryerp.org/modules/communication.html#communication-triggers) |  |
| Course | ✓ | [✓](https://docs.seminaryerp.org/modules/program.html#courses) |  |
| Course Activity | ✓ | [✓](https://docs.seminaryerp.org/modules/grading.html#assessment-types) |  |
| Course Cancellation Reason | ✓ | [✓](https://docs.seminaryerp.org/getting-started/initial-setup.html#course-cancellation-reasons) |  |
| Course Enrollment Individual | ✓ | [✓](https://docs.seminaryerp.org/modules/enrollment.html#course-enrollment-lifecycle) |  |
| Course Folder | ✓ | ✗ | Doc to write: "Course files / materials" subsection (folders, enrolled-student download access) in the courses docs. |
| Course Gradebook | ✓ | [✓](https://docs.seminaryerp.org/modules/grading.html#the-gradebook-the-whole-grid) |  |
| Course Lesson | ✓ | ✗ | Doc to write: "Lessons" subsection in course-authoring docs (content, assessments, preview, progress). |
| Course Result Tool | ✓ | [✓](https://docs.seminaryerp.org/modules/grading.html#the-gradebook-the-whole-grid) |  |
| Course Schedule | ✓ | [✓](https://docs.seminaryerp.org/getting-started/initial-setup.html#_12-course-schedule-lifecycle) |  |
| Course Schedule Chapter | ✓ | ✗ | Doc to write: "Chapters" subsection in course-authoring docs (ordering lessons, SCORM). |
| Course Schedule Progress | ✓ | ✗ | **Won't document (2026-06-13)** -- internal, system-maintained tracking record; surfaced via course progress reports. |
| Course Type | ✓ | [✓](https://docs.seminaryerp.org/modules/rooms.html#course-type-what-a-course-needs) |  |
| Culminating Project | ✓ | [✓](https://docs.seminaryerp.org/modules/graduation-requirements.html#culminating-projects-types-milestones-and-defenses) |  |
| Culminating Project Extension | ✓ | [✓](https://docs.seminaryerp.org/modules/graduation-requirements.html#culminating-projects-types-milestones-and-defenses) |  |
| Culminating Project Milestone Signoff | ✓ | [✓](https://docs.seminaryerp.org/modules/graduation-requirements.html#milestones) |  |
| Culminating Project Type | ✓ | [✓](https://docs.seminaryerp.org/modules/graduation-requirements.html#project-types) |  |
| Diploma | ✓ | [✓](https://docs.seminaryerp.org/modules/graduation-request.html) |  |
| Disciplinary Action | ✓ | [✓](https://docs.seminaryerp.org/modules/discipline.html#disciplinary-actions) |  |
| Disciplinary Incident | ✓ | [✓](https://docs.seminaryerp.org/modules/discipline.html#reporting-from-the-instructor-portal) |  |
| Disciplinary Reason | ✓ | [✓](https://docs.seminaryerp.org/modules/discipline.html#disciplinary-reasons) |  |
| Discussion Activity | ✓ | [✓](https://docs.seminaryerp.org/modules/discussions.html) |  |
| Discussion Submission | ✓ | [✓](https://docs.seminaryerp.org/modules/grading.html#discussion) |  |
| Doctrinal Statement | ✓ | [✓](https://docs.seminaryerp.org/modules/graduation-requirements.html#example-5-doctrinal-statement-signed-by-both-sides) |  |
| Event Custom Category | ✓ | [✓](https://docs.seminaryerp.org/modules/graduation-requirements.html#event-categories-the-type) |  |
| Exam Activity | ✓ | [✓](https://docs.seminaryerp.org/modules/grading.html#exam) |  |
| Exam Submission | ✓ | [✓](https://docs.seminaryerp.org/modules/grading.html#exam) |  |
| Fee Category | ✓ | [✓](https://docs.seminaryerp.org/getting-started/initial-setup.html#_8-fee-category) |  |
| Grade Conversion Policy | ✓ | [✓](https://docs.seminaryerp.org/getting-started/legacy-grade-import.html) |  |
| Grading Scale | ✓ | [✓](https://docs.seminaryerp.org/getting-started/initial-setup.html#_1-grading-scale) |  |
| Graduation Request | ✓ | [✓](https://docs.seminaryerp.org/modules/graduation-request.html) |  |
| Graduation Requirement Item | ✓ | [✓](https://docs.seminaryerp.org/modules/graduation-requirements.html#layer-1-the-library) |  |
| Instructor | ✓ | [✓](https://docs.seminaryerp.org/getting-started/initial-setup.html#_16-add-instructors) |  |
| Instructor Category | ✓ | [✓](https://docs.seminaryerp.org/modules/instructor-payment.html#instructor-categories) |  |
| Instructor Log Payment | ✓ | [✓](https://docs.seminaryerp.org/modules/instructor-payment.html#running-payroll) |  |
| Mailing Label Format | ✓ | ✗ | Doc to write: short subsection under Announcements (Print channel / mailing labels) -- presets and measuring custom stock. |
| Open Question | ✓ | [✓](https://docs.seminaryerp.org/modules/grading.html#quiz) |  |
| Partner Seminary | ✓ | [✓](https://docs.seminaryerp.org/getting-started/legacy-grade-import.html#_2-one-time-setup-external-partner) |  |
| Partner Seminary Course Equivalence | ✓ | [✓](https://docs.seminaryerp.org/getting-started/legacy-grade-import.html#_2-one-time-setup-external-partner) |  |
| Partner Transcript Import Batch | ✓ | [✓](https://docs.seminaryerp.org/getting-started/legacy-grade-import.html#_3-importing-transcripts) |  |
| Payers Fee Category PE | ✓ | ✗ | Doc to write: a "Split billing / multiple payers" subsection (how a program enrollment's fees are divided across student / church / sponsor, the per-fee shares, and how split invoices are generated). Nearest page: [enrollment](https://docs.seminaryerp.org/modules/enrollment.html). |
| Person | ✓ | [✓](https://docs.seminaryerp.org/modules/communication.html#person) |  |
| Program | ✓ | [✓](https://docs.seminaryerp.org/modules/program.html) |  |
| Program Enrollment | ✓ | [✓](https://docs.seminaryerp.org/modules/enrollment.html) |  |
| Program Graduation Requirement | ✓ | [✓](https://docs.seminaryerp.org/modules/graduation-requirements.html#layer-2-the-policy) |  |
| Program Level | ✓ | [✓](https://docs.seminaryerp.org/modules/program.html#program-level-and-ongoing) |  |
| Question | ✓ | [✓](https://docs.seminaryerp.org/modules/grading.html#quiz) |  |
| Quiz | ✓ | [✓](https://docs.seminaryerp.org/modules/grading.html#quiz) |  |
| Quiz Submission | ✓ | [✓](https://docs.seminaryerp.org/modules/grading.html#quiz) |  |
| Recommendation Letter | ✓ | [✓](https://docs.seminaryerp.org/modules/graduation-requirements.html#example-2-three-recommendation-letters-with-named-slots) |  |
| Room | ✓ | [✓](https://docs.seminaryerp.org/modules/rooms.html) |  |
| Room Feature | ✓ | [✓](https://docs.seminaryerp.org/modules/rooms.html#room-features-what-a-room-has) |  |
| Scheduled Course Roster | ✓ | ✗ | Doc to write: "Course roster / grading & standing" page (progress, attendance limits, grades, Fail-for-Absence). Central operational record; warrants its own section in the courses docs. |
| Scholarship Award | ✓ | [✓](https://docs.seminaryerp.org/modules/scholarships.html#the-scholarship-award) |  |
| Scholarships | ✓ | [✓](https://docs.seminaryerp.org/modules/scholarships.html#the-scholarship-template) |  |
| Seminary Announcement | ✓ | [✓](https://docs.seminaryerp.org/modules/announcements.html#creating-an-announcement) |  |
| Seminary Help Entry | ✓ | [✓](https://docs.seminaryerp.org/administration/customization.html#in-app-help) |  |
| Seminary Lesson Note | ✓ | ✗ | Doc to write: brief mention in the student-portal / taking-a-course docs (one private note per user per lesson). |
| Seminary Settings | ✓ | [✓](https://docs.seminaryerp.org/administration/customization.html#seminary-settings) |  |
| Student | ✓ | ✗ | Doc to write: a core **Students** records page (creating a student, auto User/Customer, standing & holds, enrollments). No people/records page exists yet. |
| Student Applicant | ✓ | [✓](https://docs.seminaryerp.org/modules/program.html#the-application-form) |  |
| Student Attendance | ✓ | [✓](https://docs.seminaryerp.org/modules/attendance.html) |  |
| Student Attendance Tool | ✓ | [✓](https://docs.seminaryerp.org/modules/attendance.html#capturing-attendance) |  |
| Student Balance | ✓ | [✓](https://docs.seminaryerp.org/modules/enrollment.html#payment-status-section-on-the-cei) |  |
| Student Group | ✓ | ✗ | Doc to write: "Student Groups" subsection (mentor groups, reuse/active flags, attaching to a Course Schedule). Nearest area: courses/scheduling docs. |
| Student Language | ✓ | ✗ | Low priority. One-line mention in a setup/lookups reference; trivial single-field lookup. |
| Student Leave Application | ✓ | ✗ | Doc to write: "Excused absences / leave" subsection in [attendance](https://docs.seminaryerp.org/modules/attendance.html). NOTE: controller attendance logic is currently commented out -- describe as a record-only form until reactivated. |
| Student Log | ✓ | ✗ | Doc to write: "Student Logs" subsection (note types, where they surface) under the proposed Students records page. |
| Term Admission | ✓ | [✓](https://docs.seminaryerp.org/modules/program.html#admissions-timed-vs-continuous) |  |
| Term Withdrawal Rules | ✓ | [✓](https://docs.seminaryerp.org/modules/withdrawal.html#term-widrawal-rules) |  |
| Trigger Fee Events | ✓ | ✗ | **Won't document (2026-06-13)** -- developer-only billing plumbing, not a user-facing record. |
| Withdrawal Reasons | ✓ | [✓](https://docs.seminaryerp.org/modules/withdrawal.html#withdrawal-reasons) |  |
| Withdrawal Request | ✓ | [✓](https://docs.seminaryerp.org/modules/withdrawal.html#withdrawal-request) |  |
| Withdrawal Rules | ✓ | [✓](https://docs.seminaryerp.org/modules/withdrawal.html#withdrawal-rules) |  |

## Documentation backlog

Doctypes with a description but no docs page. Each row is a decision: write the
section, or record here that we deliberately won't. When written, set the
`documentation` key and move the row up.

| Doctype | What's needed / decision |
| --- | --- |
| Course Folder | Doc to write: "Course files / materials" subsection (folders, enrolled-student download access) in the courses docs. |
| Course Lesson | Doc to write: "Lessons" subsection in course-authoring docs (content, assessments, preview, progress). |
| Course Schedule Chapter | Doc to write: "Chapters" subsection in course-authoring docs (ordering lessons, SCORM). |
| Course Schedule Progress | **Won't document (2026-06-13)** -- internal, system-maintained tracking record; surfaced via course progress reports. |
| Mailing Label Format | Doc to write: short subsection under Announcements (Print channel / mailing labels) -- presets and measuring custom stock. |
| Payers Fee Category PE | Doc to write: a "Split billing / multiple payers" subsection (how a program enrollment's fees are divided across student / church / sponsor, the per-fee shares, and how split invoices are generated). Nearest page: [enrollment](https://docs.seminaryerp.org/modules/enrollment.html). |
| Scheduled Course Roster | Doc to write: "Course roster / grading & standing" page (progress, attendance limits, grades, Fail-for-Absence). Central operational record; warrants its own section in the courses docs. |
| Seminary Lesson Note | Doc to write: brief mention in the student-portal / taking-a-course docs (one private note per user per lesson). |
| Student | Doc to write: a core **Students** records page (creating a student, auto User/Customer, standing & holds, enrollments). No people/records page exists yet. |
| Student Group | Doc to write: "Student Groups" subsection (mentor groups, reuse/active flags, attaching to a Course Schedule). Nearest area: courses/scheduling docs. |
| Student Language | Low priority. One-line mention in a setup/lookups reference; trivial single-field lookup. |
| Student Leave Application | Doc to write: "Excused absences / leave" subsection in [attendance](https://docs.seminaryerp.org/modules/attendance.html). NOTE: controller attendance logic is currently commented out -- describe as a record-only form until reactivated. |
| Student Log | Doc to write: "Student Logs" subsection (note types, where they surface) under the proposed Students records page. |
| Trigger Fee Events | **Won't document (2026-06-13)** -- developer-only billing plumbing, not a user-facing record. |

## Maintaining this file

- **New doctype?** Add a row (alphabetical). Write its description in the JSON;
  set `documentation` if a page exists, else add it to the backlog.
- **Wrote a doc page?** Set the doctype's `documentation` key (most specific
  anchor), register the page in `config.mjs`, flip the column to ✓ here, and
  remove it from the backlog.
- **Decided not to document something?** Leave Documentation as ✗ but change
  its backlog note to a dated "won't document because ..." so the decision sticks.
- Run `python` over the doctype JSONs to re-derive the counts when in doubt; this
  table is hand-maintained and can drift.
