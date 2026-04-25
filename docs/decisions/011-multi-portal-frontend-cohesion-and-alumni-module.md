# 011 — Multi-Portal Frontend Cohesion and Alumni Module

**Date:** 2026-04-25
**Status:** Accepted

## Context

Frappe apps integrate cleanly on the **Desk** (one app switcher, one sidebar,
one search) but each app's public-facing SPA was a visually separate site:
`/seminary/...` and `/donate/donorportal/...` had different headers,
different login redirects, different styling. The pain was about to compound:

- An **Alumni Portal** was needed, semantically overlapping with Student
  (same people, same programs) and Donor (alumni often donate). A separate
  app would fragment the schema and the UX further.
- A **closed-source Accreditation app** is planned, requiring deep backend
  coupling to seminary (course assessments → CLO attainment) but with a
  distinct frontend audience (accreditators, program directors).

We needed an architecture that (a) made the open portals feel like one
product, (b) kept the closed Accreditation app loosely coupled at the
frontend while tightly coupled at the backend, and (c) was incremental
enough to ship Alumni first.

LMS was deliberately scoped out: the `apps/lms` app is deprecated in
production and absorbed into seminary; the Student Portal **is** the
seminary SPA.

## Decision

### Alumni lives as a module *inside* seminary

Not its own app. New module `alumni/` under [`seminary/seminary/`](../../seminary/alumni/)
registered in [`modules.txt`](../../seminary/modules.txt). One doctype:
[`Alumni Profile`](../../seminary/alumni/doctype/alumni_profile/alumni_profile.json),
which **links** to `Student` (optional, to support non-student alumni such
as honorary degrees). Sharing the seminary SPA shell means no UX seam between
Student and Alumni; sharing the database means no cross-app joins for
"alumni who took course X".

The student → alumni transition is **manual**: a *Mark as Alumni* button on
`Program Enrollment` (visible only when the audit reports
`graduation_eligible`) calls
[`seminary.alumni.api.mark_as_alumni`](../../seminary/alumni/api.py), which:

1. Verifies the enrollment is submitted and graduation-eligible.
2. Auto-populates `date_of_conclusion` (today) if blank, via
   `pe.db_set("date_of_conclusion", today())` since the enrollment is
   submitted.
3. Creates the `Alumni Profile`, sets its `owner` to the student's User
   (so `if_owner` permissions work), and grants the `Alumni` role via
   `User.add_roles("Alumni")`.

Alumni get **read access to all alumni profiles** (directory) and
**write access to their own** via the `if_owner` permission row plus a
whitelisted `update_profile` API. The whole graduation lifecycle (diplomas,
ceremonies, internship hours) is deliberately *not* modeled — see [open
questions below](#consequences).

### `@seminary/portal-shell`: shared chrome via a yarn-linked package

A new in-repo package at [`seminary/portal-shell/`](../../../portal-shell/)
provides:

- `<PortalHeader>` — top bar with brand, optional title slot, portal
  switcher, user menu.
- `<PortalSwitcher>` — dropdown listing portals visible to the current
  user's roles. Teleported to `<body>` with viewport-aware placement so it
  works equally well in seminary's left sidebar and in frappe_giving's top
  header.
- `<UserMenu>` — avatar + sign-out.
- `useSession()` / `useTheme()` composables.
- `configurePortals({ brand, portals, sessionFetcher, onSignOut })` for
  per-consumer registration.

**Zero peer deps beyond Vue.** No frappe-ui, no Tailwind. Built via Vite
library mode → `dist/portal-shell.{js,umd.cjs,css}`. This keeps the package
adoptable by frappe_giving (which deliberately doesn't use frappe-ui) and
by future closed apps without forcing a stack choice on consumers.

### Distribution: `link:` not `file:`

Both consumers reference the package as a yarn `link:` dependency:

```jsonc
// seminary/frontend/package.json
"@seminary/portal-shell": "link:../portal-shell"

// frappe_giving/frontend/package.json (open-source consumer — example)
"@seminary/portal-shell": "link:../../seminary/portal-shell"
```

`link:` creates a symlink in `node_modules`, so rebuilding portal-shell
propagates immediately into every consumer's bundle on the next consumer
build. We used `file:` first and lost a debug cycle to it: yarn 1's
`file:` to a directory **copies** at install time, freezing the consumer
to whatever was in `dist/` when `yarn install` ran.

### Adoption pattern, by app

| App           | What it uses               | Where it lives                                                                 |
|---------------|----------------------------|--------------------------------------------------------------------------------|
| seminary      | `<PortalSwitcher>` only    | Inside [`AppSidebar.vue`](../../../frontend/src/components/AppSidebar.vue), reusing the existing `UserDropdown` |
| frappe_giving | full `<PortalHeader>`      | Wraps `<router-view>` in [`App.vue`](../../../../frappe_giving/frontend/src/App.vue) (illustrative open-source consumer) |
| accreditation | full `<PortalHeader>`      | Same wrapping pattern as frappe_giving, in its own SPA                         |

Seminary keeps `UserDropdown` because the sidebar already owned that
chrome; we just add the cross-portal switcher.

### `configurePortals` reuses existing session sources

Each consumer can plug its own session fetcher into the shell rather than
making the shell call Frappe directly. Seminary passes a fetcher that
awaits its existing `usersStore.userResource` and maps the result, so we
don't duplicate the `seminary.seminary.api.get_user_info` round-trip.
Donor portal uses the shell's default cookie + `frappe.client.get`
fetcher because frappe_giving has no equivalent store.

`get_user_info` itself was extended with one new boolean: `is_alumni`,
mirroring the existing `is_student` / `is_evaluator` pattern at
[`seminary/seminary/api.py`](../../seminary/api.py).

### Hooks updates in this app

- **Bug fix**: `seminary/hooks.py` had two `website_route_rules`
  definitions; the second silently overrode the first, killing
  `/admissions` and `/program`. Merged into one list.
- `role_home_page["Alumni"] = "/seminary/alumni"`.
- `default_roles` grants the `Alumni` role automatically when an
  `Alumni Profile` is created with a matching User (belt-and-suspenders
  with `User.add_roles("Alumni")` in `mark_as_alumni`).
- `standard_portal_menu_items` adds an Alumni entry.
- `global_search_doctypes` includes `Alumni Profile`.

## Alternatives considered

**Alumni as its own Frappe app** — rejected. Doubles surface to maintain;
forces cross-app joins for natural Student↔Alumni queries; Alumni audience
is small enough that an isolated app's overhead doesn't pay off.

**One unified Portal SPA** (single Vue app at `/portal/` covering
student/alumni/donor/accreditation) — rejected. Would require partially
reimplementing the seminary SPA. Couples open portals at deploy time, and
doesn't help the closed Accreditation app (which stays separate anyway).

**Module federation / micro-frontends** — rejected. Real complexity, less
battle-tested in the Frappe ecosystem, version-alignment hazards across
remotes.

**Two builds of portal-shell (full + lite, with/without frappe-ui)** —
considered, then dropped. Making the shell zero-frappe-ui in the first
place removed the need for two artifacts.

**Custom directive `v-click-outside` for the dropdown** — initial
implementation; replaced by `<Teleport to="body">` plus
`getBoundingClientRect()` + viewport-aware placement. The directive
worked, but the menu was clipped by the sidebar's stacking context. Teleport
is the correct primitive here.

## Consequences

**Easier:**

- Adding a new portal is a one-liner in each consumer's `configurePortals`
  registry, plus the consumer's own routing — no shell changes required.
- Visual identity is consistent across `/seminary`, `/donate/donorportal`,
  and `/accreditation` without forcing them onto the same stack.
- Alumni naturally inherits the seminary SPA's existing layout, theming,
  i18n, and session handling.
- The closed Accreditation app can adopt the shell privately while keeping
  its codebase out of the seminary repo.

**Friction (accepted):**

- `link:` requires `yarn install` to be re-run when the dependency tree
  changes (which is rare). Day-to-day, only consumer rebuilds are needed
  after editing portal-shell.
- Each consumer must call `configurePortals` once at boot — the shell
  doesn't auto-discover portals.
- Donor portal frontend was refactored to consume the shell. The Stripe
  flow and lean stack are preserved; only `App.vue` and `main.js` changed.

**Open / residual risks:**

- **Graduation lifecycle is unmodeled.** `Alumni Profile` deliberately has
  no `certificate_number`, `graduation_date`, or `diploma` fields.
  Internship hours, non-course requirements, and ceremonies are also
  undefined. When that domain is designed, decide whether the new
  doctypes belong inside seminary or in a new `graduation` module.
- **Auto-transition is intentionally absent.** A `Program Enrollment`
  workflow change does NOT create an `Alumni Profile`; only the manual
  button does. If/when registrars want auto-transition, add a workflow
  state action — don't add an `on_submit` doc_event silently.
- **Portal registry is duplicated** across consumers' `main.js` files.
  Acceptable for three portals; if it grows, extract to a Frappe single
  doctype `Portal Shell Settings` and have the shell fetch it once.
- **`if_owner` permission on `Alumni Profile`** depends on the registrar
  flow setting `owner = student.user`. If profiles get created via any
  other path, alumni will lose write access to their own records. Worth
  centralising profile creation behind the API.
