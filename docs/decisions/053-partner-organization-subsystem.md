# 053 — Partner Organization subsystem

**Date:** 2026-06-13
**Status:** Accepted — foundation implemented; later phases future

## Context

The seminary wants to relate to other Christian organizations (churches, mission agencies,
denominations, para-church organizations, NGOs) and, over time, to build relationship-driven features
on top of those organizations: a **job board with applicant tracking (ATS)**, **internships**,
**one-off needs** ("substitute preacher for a date"), **service opportunities** (announcement +
RSVP), **partner QA on programs**, and **alumni placement** ("find churches where our graduates
serve"). Rollout is explicitly gradual.

The first instinct was to overload ERPNext's `Customer` — add `partner_type` / `engagement_tier`
custom fields and link a `Job Posting` to `Customer`. That is the wrong spine:

- `Customer` is **already the billing entity**. A `Student` auto-creates a linked `Customer`, and per
  [ADR 052](052-external-accounting-integration-quickbooks.md) `Customer` is the one-way push source
  to QuickBooks Online. Overloading it would drag every non-paying church into the billing/QBO
  namespace and bolt CRM/relationship concepts onto a sales doctype.
- The codebase already has the pattern this needs: the **Person identity spine**
  ([ADR 042](042-person-identity-spine.md)) — one `Person` per human, shared across
  student/instructor/alumni/applicant roles, linking *out* to `Customer` only for billing.

## Decision

Introduce **`Partner Organization`** as the *organizational relationship spine* — the org-level mirror
of `Person`. It is a fourth orthogonal entity alongside `Customer` (billing), `Person` (human
identity), and `Partner Seminary` (academic credit, [ADR 005](005-unified-partner-seminary-model.md)).

1. **Spine, not a billing record.** `Partner Organization` carries the relationship (type, engagement,
   capabilities, contacts) and links *out* to a `Customer` only when money actually moves — the same
   optional-`customer` idiom `Partner Seminary` already uses. We never auto-create a `Customer` for a
   partner. A church that posts a job but never pays the seminary stays out of the billing/QBO surface.

2. **Distinct from Partner Seminary, but cross-linked.** `Partner Seminary` = academic-credit source
   (transfer/legacy grades); `Partner Organization` = ministry/employment relationship. An org that is
   *both* (e.g. a denominational college that is also an employer) is modeled as **two cross-linked
   records**, not merged — they have different lifecycles, fields, and permissions. The link follows
   the spine direction: `Partner Organization` is the org spine, `Partner Seminary` is a specialized
   role the org plays, so the **role points at the spine** — a single optional FK
   `Partner Seminary.partner_organization` (mirroring `Student.person → Person`). No second stored
   column; bilateral navigation comes from a dashboard `links` (connections) entry on
   `Partner Organization`. The link is **conditional**: it is hidden and rejected when
   `Partner Seminary.is_internal_legacy` is set (internal legacy is the school's own pre-system
   history, never an external partner), and it is manually curated, never auto-created.

3. **People-at-partner via the Person spine, not Frappe `Contact`.** A `Partner Contact` child table
   links each affiliated human by `Person`. A pastor who is also an alumnus is one `Person`, so the
   existing multi-channel communication ([ADR 043](043-multichannel-communication-system.md)/044),
   consent, and communication log work for free. A reverse `links` entry on `Person` surfaces
   "Affiliated organizations" on the human's dashboard.

4. **`engagement_tier` is descriptive CRM segmentation only — it does NOT gate feature access.**
   Access is gated by **orthogonal capability Check flags** on the organization
   (`accepts_job_postings`, `offers_internships`, `provides_qa_feedback`, `is_alumni_employer`), so a
   "Light" partner can still post a one-off need without being promoted up a tier. This applies the
   orthogonal-flags convention ([ADR 015](015-orthogonal-program-flags-and-workflow-conditions.md)) —
   we do not overload one tier field with multiple side-effects.

5. **`partner_type` is an open taxonomy** (`Partner Type` lookup), **seeded via the install hook, not
   fixtures** — fixtures re-import on every migrate and clobber a seminary's desk edits. Created
   once, create-only-if-missing (mirrors `seed_*` in `install.py`).

6. **New `Partner` module** (third entry in `modules.txt` after `Seminary` and `Alumni`) so the
   subsystem is self-contained and can be permissioned/rolled out independently. A dedicated
   **Partner portal role** will be added with the job board phase, per the app-owns-its-roles posture
   ([ADR 034](034-role-taxonomy.md)).

7. **Internship posting vs. internship hours boundary.** Recruiting *postings* (a phase-1 `Job
   Posting` with `posting_type = Internship`) live in this subsystem; internship *hours* remain a
   graduation-requirement concern, deliberately unmodeled
   ([ADR 012](012-graduation-requirements-architecture.md)). The two never link.

### Phasing

- **Phase 0 (this ADR, implemented):** Desk-only CRM spine — `Partner Type`, `Partner Organization`,
  `Partner Contact`, the `Person` reverse link, and the install-hook seeder. No portal, no frontend.
- **Phase 1:** Job board + ATS (`Job Posting` with `posting_type` absorbing internships and one-off
  needs; `Job Application` pipeline; applicant = `Person`), plus the Partner portal role, multi-user
  linkage via `Partner Contact.portal_user`, row-scoped permissions, and Vue portal pages.
- **Phase 2:** Service opportunities (#4).
- **Phase 3:** Partner QA on programs (#5).
- **Phase 4:** Alumni placement (#6) — augment `Alumni Profile` free-text `current_organization` with
  an optional `current_partner_organization` link + a non-destructive matching patch + an
  alumni-employer report. Decoupled; can be pulled forward.

### Phase 1 ATS data model (decided)

The job board / applicant-tracking layer is implemented as `Partner Job Opening` and
`Partner Job Application` (the concrete names of the ADR's generic "Job Posting"/"Job Application").
Six shape decisions:

1. **Locations are a standalone `Partner Organization Location` doctype, not a child table.** A
   Frappe `Link` cannot target a child-table row, so a child table couldn't be *picked* by a
   `Partner Job Opening` nor filtered on. The standalone doctype links back to the org
   (`partner_org`), carries the per-site address plus `ministry_setting` (Urban/Suburban/Rural/
   Campus) and an optional `congregation_size`, and a Job Opening links one site — making openings
   filterable by setting (the opening fetches `ministry_setting` read-only for a join-free filter).

2. **Skill matching uses one controlled vocabulary reused on both sides.** A `Skill Tag` master
   (seeded via install hook, not fixtures — same reasoning as `Partner Type`) plus a single tiny
   `Skill Tag Link` child surfaced as a **Table MultiSelect** on both `Person.skills` and
   `Partner Job Opening.skills`. Frappe manages the junction rows, so there are no hand-built
   "Job Posting Skills"/"Person Skills" doctypes. `Skill Tag`/`Skill Tag Link` live in the
   **Seminary** module (not Partner) so core `Person` does not depend on the Partner module.

3. **Applicant identity and resume are reused, not re-entered.** `Partner Job Application.applicant`
   links `Person`. `full_name` is `fetch_from`; the controller snapshots `primary_email`/
   `primary_mobile` as **preferred-or-primary** — `Person` carries `preferred_application_email`/
   `preferred_application_phone` (blank = use the primary), editable from the apply page, so the
   partner reaches the applicant on the channel they chose. The per-application `resume` defaults
   from `Person.resume` (overridable), served privately
   ([ADR 043](043-multichannel-communication-system.md)). One application per
   `(applicant, job_opening)`; audience flags (`open_students`/`open_alumni`) gate eligibility, and
   accepting an application decrements the opening's `vacancies` and auto-closes it when full.

4. **Draft → submitted lifecycle on the Select status; the who/when audit is free.** Pipeline values
   `Draft/Open/Replied/Shortlisted/Hold/Rejected/Accepted/Withdrawn`. A `Draft` is saved by the
   applicant but hidden from the partner and excluded from the published count; submitting moves it
   to `Open`. We model this on the existing status Select rather than Frappe `docstatus`, so reviews,
   status changes and the contact log (all *post-submission*) keep working without marking fields
   `allow_on_submit`. Completeness rules (cover letter required; doctrinal response required when the
   opening asks; explanation required when the response isn't full agreement) are enforced **only at
   submit**, never on a Draft. The `Partner Job Application Review` child holds `reviewer`/`rating`/
   `notes` only (no `changed_status` — who/when comes from `track_changes`), keeping review and
   status-audit orthogonal ([ADR 015](015-orthogonal-program-flags-and-workflow-conditions.md)). A
   `Partner Job Application Contact` child logs recruiter touchpoints. (Note: `reviewer` links
   `Person`, not `Partner Contact`, for the same child-table-not-linkable reason as #1.)

5. **Ministry-focused, not a generic board.** `Partner Job Opening` carries a `position_type`
   (ministry role taxonomy: Pastoral, Teaching, Worship, Youth, Counseling, Missions, Admin,
   Facilities, Other) and a `require_doctrinal_alignment` check — which the opening's `validate`
   rejects unless the organization actually publishes a `doctrinal_statement`. When required, the
   applicant must read that statement and answer (`I agree completely, without reservations` /
   `… with reservations` / `I agree partially` / `I disagree`), with an explanation required for
   anything short of full agreement. `description` is mandatory on the opening. The portal filters by
   position type, employment type, ministry setting, the org's Partner Type, and "requires doctrinal
   agreement"; submission is a prayerful confirmation, not a one-click apply.

6. **Phase 1 portals are implemented — both sides.** Applicant side: Vue pages (`Jobs`,
   `JobOpening`, `JobApplication`) on the student/alumni portals, backed by `seminary.partner.api`
   (eligibility-scoped listing/detail + draft-aware `apply_to_job`). **Employer side**: a self-
   contained **Partner portal** (its own switcher entry + sidebar) where partner staff manage their
   profile, people, locations, postings, and applicants, backed by `seminary.partner.portal`. A new
   `Partner` role (portal-only, auto-granted when a `Partner Contact` is given `portal_access`) plus
   record-level scoping (`seminary.partner.permissions`, registered as
   `permission_query_conditions`/`has_permission`) confines each partner user to their own org.
   Partner-created/edited postings save **unpublished** (staff approval before public); partners run
   the applicant pipeline (status changes) and review/contact-log each applicant; an application
   carries `submission_date` (set when it leaves Draft) for ordering, and its résumé `File` is
   attached to the application on submit so partners read it through their application permission.

## Consequences

Easier: relationship modeling is orthogonal to billing — partners never pollute AR/QBO; the spine
reuses Person for people, so comms/consent are free; capabilities are composable, not tier-gated; the
subsystem is module-isolated and ships in phases. Harder: a partner that is also a billing customer
and/or an academic Partner Seminary is several cross-linked records rather than one; partner-portal
identity (phase 1) resolves through `Partner Contact.portal_user` rather than a single `user` field
(deliberate — orgs have several staff).

## Open questions

- **Service opportunities (#4):** reuse `Event` ([ADR 028](028-events-first-class.md)) +
  `Seminary Announcement` ([ADR 045](045-announcement-audiences-categories-channels.md)) — attendees
  already model RSVP — vs. a dedicated doctype. **Deferred to Phase 2.** Default lean is reuse, with a
  single `Event.partner_organization` custom field for attribution.
- **Partner QA on programs (#5):** the feedback doctype shape. Deferred to Phase 3.
