# 027 — Culminating Project Workbench (student + advisor Vue page)

**Date:** 2026-05-30
**Status:** Accepted

## Context

ADRs 024–026 built the culminating-project backend (projects, dated milestones,
per-role sign-offs, submission rounds, choices) but deferred the **frontend
workbench**. This adds it: a dedicated, role-gated page so students see what to
do next and advisors/readers triage and review.

## Decision

**Three whitelisted endpoints** in `culminating_project.py`, matching the
auth/shape conventions of `api.get_program_audit`:
- `get_my_culminating_projects()` → `{ student_projects, advisor_projects }`;
  each row carries the active milestone, its due date, and (for advisors)
  `my_role` + **`needs_action`** (a milestone awaits my role's sign-off, or a
  submission round assigned to me is still Pending).
- `get_culminating_project(name)` → full detail (header, advisors with contact
  info, milestones with required-role sign-offs + the linked submission, and a
  `student_action` hint). **Authorization**: the student owner, a reader
  (advisor/second/third == session Instructor), or staff (Academics User /
  Seminary Manager / Registrar) — else `PermissionError`. The session→Instructor
  map reuses the existing `get_instructor_info` query; `get_user_info` now also
  returns `instructor` and `has_culminating_projects` (symmetric with `student`,
  for role detection + sidebar gating).
- `review_submission(culminating_project, round, decision, comment, attachment)`
  → reader/staff records a decision on a submission round. `add_submission`
  gained a `milestone_row` arg so a student's upload links to the milestone and
  flips it to Submitted; round numbers derive from existing rounds (the validate
  counter doesn't run post-submit).

**Frontend** (mirrors `ProgramAudit.vue`): a `CulminatingProject.vue` page with a
**My Project / Projects I Advise** toggle (shown only when the user is both);
the student side renders the detail directly; the advisor side is a
client-filtered table (Program / Type / Status / My Role) with a
**Needs-my-action** badge and the next due date. A shared
`CulminatingProjectDetail.vue` renders title + collapsed abstract, advisors
(reusing `InstructorAvatar` + the CourseDetail contact block), the
work/waiting/done info card, and a `Disclosure` milestone accordion auto-expanded
on the active milestone — each milestone showing sign-off state, its submission,
and (per viewer) student upload (`add_submission`) or reviewer sign-off
(`record_signoff`) / submission review (`review_submission`). `statusTheme`
gained Active/Under Review/Approved/Accepted (→ blue/green), Rejected (red),
Revisions Required (orange).

## Consequences

- **More `allow_on_submit` (ADR 026 gotcha, again).** Editing a *submitted*
  project from the workbench surfaced three fields that silently dropped
  (children) or threw (parent): the **`submissions` table** (adding a round threw
  `Not allowed to change Submissions`), the parent **`current_round`** (threw
  `UpdateAfterSubmitError`), and the **submission reviewer fields** (`reviewer`,
  `reviewer_decision`, `reviewer_attachment`, `reviewed_on`, `reviewer_comment` —
  silently dropped). All are now `allow_on_submit`. Rule of thumb: any field a
  post-submit action writes must be `allow_on_submit`.
- The page is gated by `has_culminating_projects`, so it only appears for
  students with a project and for advisors/readers.
- Reviewer **milestone** sign-off is offered only to the three reader roles
  signing as their own role; staff review submissions and use the desk for
  sign-offs. The Defense calendar-`Event` (`creates_event`) wiring remains the
  one deferred item from ADR 025.

## Follow-up refinements (2026-05-30)

Dev testing surfaced five issues; the fixes harden the student↔reader hand-off:

- **The "ball" is explicit.** A milestone is *submittable* when it requires a
  submission **or** has any reader sign-off (you can't sign off on nothing), so
  the student always submits first. `review_submission` now moves the milestone
  on the reviewer's reply — **Revisions Required/Rejected → In Progress** (back
  to the student), **Accepted → Submitted** (awaiting sign-off). `_needs_action`
  was rewritten to mean *only* "a round assigned to me is Pending" **or** "the
  active milestone's latest round is Accepted and I haven't signed it." This
  killed two bugs: the **"Needs you" flag lingering after a reviewer requested
  revisions**, and the **standoff** where a sign-off milestone with
  `requires_submission=0` left the student waiting and no reader prompted (the
  student is now told to submit; the reader is prompted only once it's accepted).
- **Students don't pick the submission type.** It's derived: Proposal milestone
  → `Proposal`; first round of any other milestone → `Draft`; later rounds →
  `Revision`. **`Final`** is set by the advisor's act of approving the
  Final-Submission milestone (`record_signoff`), not chosen at upload. The submit
  dialog shows the derived type read-only.
- **Per-milestone submission history.** A new **`milestone_row`** field on
  Culminating Project Submission links each round to its milestone, so the
  detail returns every round per milestone (not just the latest). The reader UI
  shows the latest round with a collapsible **"Previous rounds (n)"** record of
  all student uploads + reviewer responses.
- **Reader↔student contact.** The detail returns `student_email`; readers/staff
  get a `mailto:` to the student (mirroring the advisor contact block).
- **More `allow_on_submit`** (ADR 026, yet again): `submission_type` (relabelled
  to `Final` post-submit) and the new `milestone_row` on the submission child.

## Committee sign-off (2026-05-30)

A `Culminating Project Committee` child table (field `committee` on Culminating
Project — renamed from the auto-generated `table_jkpe`) holds members that are
either an internal `Instructor` or an external reader (`external_name` /
`email_external`). The committee does **not** sign individually: when a milestone
requires `signoff_committee`, the **advisor** records the sign-off on the
committee's behalf.

- `record_signoff(role="Committee")` requires the caller to be the project's
  **advisor** (not staff, not other readers) and the committee to be non-empty
  ("create the committee first"). Staff who must override use Desk directly.
- `_needs_action` now checks every role a user is *responsible* for via
  `_responsible_signoff_roles` — the advisor carries **Advisor + Committee** — so
  a committee sign-off due flags the advisor on the list. Readiness was extracted
  to `_signoff_ready` (latest submission Accepted, or a co-reader already signed).
- `get_culminating_project` returns `committee` (members for display, each with
  its child-row `name`) and `viewer.can_sign_committee` (advisor only). The
  workbench shows a **Sign for Committee** button to the advisor and an **info
  banner** in the sign-off dialog ("recording on behalf of the committee",
  listing members). The `committee` table is `allow_on_submit` so the advisor can
  maintain it on an active project.
- The advisor **manages the committee from the portal** (no Desk needed):
  `add_committee_member` / `remove_committee_member` (advisor-only, dedupe
  internal instructors) back an inline editor in the detail header — chips with a
  remove (×), and an **Add** dialog toggling Internal Instructor (reuses
  `Controls/Link.vue` → `search_link`) vs External (name + optional email).

## Student-editable abstract (2026-05-30)

The abstract (a Text Editor / HTML field) is empty on creation and was only
shown when populated, so a student had no way to add it. Now `save_abstract`
lets the **student owner** edit it **until the project is defended**
(`defended_on` set) — readers/staff see it read-only as HTML. Because it's
student-supplied HTML rendered to others, it is **sanitized server-side**
(`frappe.utils.sanitize_html(..., always_sanitize=True)` — strips `<script>`,
event handlers, etc.). The field isn't `allow_on_submit` and the project is
submitted once active, so the (already-sanitized) value is written via
`frappe.db.set_value`. The portal edits it in a Dialog using the app's
`RichTextEditor` (Tiptap) with `:teleport="false"` (the Dialog already teleports
to body — the safe pattern for full editors in nested pages).

## Note
The portal Vue app is built by **Vite** (`frontend/`), separate from the desk
esbuild watch — changes need `yarn dev` (HMR) or `yarn build` to appear.
