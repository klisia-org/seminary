# 074 — Portal taxonomy: one portal per deployed SPA

**Date:** 2026-09-22
**Status:** Accepted

Amends [ADR 011](011-multi-portal-frontend-cohesion-and-alumni-module.md) (portal
registry), [ADR 064 §8](064-discipleship-cohorts-and-channels.md) (the
Cohort Participant portal entry), and [ADR 034](034-role-taxonomy.md) (the
`Academics User` → `Program Chair` rename, which a one-shot patch cannot hold).

## Context

`configurePortals` in [`seminary/frontend/src/main.js`](../../../frontend/src/main.js)
had grown to seven entries. Five of them — `examiner`, `alumni`, `partner`,
`community`, and `student` itself — are `/seminary/...` URLs, and the seminary
SPA mounts at `createWebHistory('/seminary/')`. They are **routes of the app the
user is already in**. Choosing one from the switcher costs a full page reload to
land on a view the sidebar already links to.

The symptom that surfaced this: an Instructor who also holds `Cohort Participant`
saw a *Community* tile **and** the Community sidebar link for the same page, and
an account holding `External Examiner` saw a *Project Reviews* tile pointing at
the same `/culminating-project` route its sidebar link already offered. Because
`<PortalSwitcher>` only renders above one visible tile, one extra role flips the
entire control into view — so the registry's noise was invisible on some accounts
and dominant on others.

Two structural causes:

1. **No definition of "portal".** The registry was a bookmark list, so every new
   audience (ADR 053 partners, ADR 059 external examiners, ADR 064 pastors) added
   a tile by default rather than by decision.
2. **Union, not precedence.** `visiblePortals` shows a tile if the user holds
   *any* listed role. Overlapping audiences therefore accumulate tiles instead of
   resolving to one. [`seminary/seminary/auth.py`](../../seminary/auth.py) already
   had the right shape for this — an ordered `PORTAL_HOME` tuple with `STAFF_ROLES`
   short-circuiting — but the switcher never adopted it.

Drift compounded it. ADR 011 accepted a duplicated registry "acceptable for three
portals"; at seven it had diverged three ways across seminary, aretenic and
frappe_giving (aretenic's `partner` entry pointed at `/seminary/alumni`;
frappe_giving labelled Academics "Courses"), and seminary still gated on
`Academics User`, renamed to `Program Chair` by [ADR 034](034-role-taxonomy.md).

Auditing those gates turned up three further defects that share the registry's
root cause — a tile or a route that promises access the backend will refuse — so
they are decided here rather than deferred:

- The **Donate** tile carries no capability predicate. On a site without
  frappe_giving installed, `/donate/donorportal` has no `website_route_rules`
  entry and the tile leads to a 404. This is the exact situation `has_aretenic`
  already solves for Aretenic.
- **`/seminary/partner/*` has no route guard.** An instructor with no
  `Partner Contact` row can reach *New Job Posting*, fill the entire form, and
  only discover on submit that `portal._require_org` throws
  *"Your account isn't linked to a partner organization."* The backend is
  correctly guarded; the frontend simply doesn't ask.
- **`Academics User` is back on tlink, alongside `Program Chair`** — see below.

### The `Academics User` role resurrects itself

The ADR 034 rename patch is correct and idempotent, and it did run. But patches
run **once**, and Frappe recreates the role afterwards on every migrate:
[`doctype.py`](../../../frappe/frappe/core/doctype/doctype/doctype.py) `#L1937-L1944`
auto-creates any role named in a DocPerm that does not exist, with
`desk_access = 1`. Three installed apps still name it:

| App | File | Why it fires |
|---|---|---|
| erpnext | `setup/doctype/department/department.json:119` | DocPerm on Department |
| hrms | `hr/doctype/interest/interest.json:38` | DocPerm on Interest |
| frappe_giving | `dashboard_chart/donor_base/donor_base.json:29` | chart role |

So the merge is undone by the next `bench migrate`, and a one-shot patch cannot
hold. Worse, the resurrected role is a **trap**: it carries no seminary
permissions (those moved to Program Chair) but reads like the academic-authority
role it used to be, so granting it looks meaningful and does nothing.

### Role names are *not* mis-created by `_()` — corrected

An earlier reading of [`install.py`](../../seminary/install.py) flagged
`_("Student")`, `_("Instructor")` etc. as creating translated role names on a
Portuguese site, which would silently break every literal role check in
`get_user_info`. **That is wrong, and it is recorded here so it is not
re-investigated.** Two independent reasons:

1. `frappe.local.lang` is set at init to `local.conf.lang or "en"`
   ([`frappe/__init__.py`](../../../frappe/frappe/__init__.py) `#L187`).
   `set_user_lang` runs only on session begin/resume, never during
   `bench install-app` or `bench migrate` — so `_()` resolves against `en` and
   returns the English string, unless a site explicitly sets `lang` in
   `site_config.json`.
2. Portuguese role names in **User → Roles** are a display artifact, not stored
   data: `Role` is declared `"translated_doctype": 1`, so link fields, list views
   and search translate role names for presentation while `name` stays English.

The `_()` wrapping is still wrong in principle — a role name is an identifier,
not display text — but it is cosmetic, and unwrapping it is explicitly **not**
part of this decision.

## Decision

### A portal is a separately-deployed SPA with its own base path

Anything reachable without leaving the current SPA is **navigation**, not a
portal, and belongs in that app's sidebar. The seminary registry becomes three
entries: **Academics** (`/seminary`), **Aretenic** (`/aretenic`, behind the
existing `when: (s) => !!s?.has_aretenic` predicate), and **Donate**
(`/donate/donorportal`, behind a new `has_giving` predicate).

### A tile must never point at something that isn't there

Every portal whose app is optional carries a `when(session)` predicate backed by
an installed-apps flag from `get_user_info`. `has_aretenic` gains a sibling,
`has_giving` (`"frappe_giving" in frappe.get_installed_apps()`), and the Donate
tile gates on it. Donate keeps **no role gate** — anyone may donate — but an
uninstalled app is not a permissions question, it is an absent route.

This generalises: a tile is justified by *reachability*, not by role alone.

The `examiner`, `alumni`, `partner` and `community` entries are removed. Each
audience keeps its route; only the tile goes. This amends ADR 064 §8, which asked
for a Cohort Participant tile in `PortalSwitcher.vue`: the tile is unnecessary
because `after_login` already lands pastors on `/seminary/community` and the
sidebar link is already gated to include them. ADR 064's substance — Community is
a page inside the existing portal, not a new one — is unchanged and in fact
better served.

### Overlapping audiences resolve by precedence, not union

Where a user legitimately reaches more than one real portal, the switcher shows
the tiles; where an audience is subsumed by a broader one, the broader wins. This
is the rule `auth.py` already applies to login landing, and the two should not
disagree.

### Every removed tile must leave working navigation behind

A tile may only be removed once the sidebar covers its audience. Three of the
four already did (`has_culminating_projects`, `is_alumni`, and the
`isParticipant` branch of the Community link). **Partner did not** — there is no
`is_partner` branch in the sidebar link list, so a partner-only user sees a
sidebar containing just *Preferences* and the tile is their sole route into
`/partner/jobs`. A Partner sidebar link is therefore part of this decision, not a
follow-up.

### One canonical registry, exported from portal-shell

`@seminary/portal-shell` exports the ecosystem list; seminary, aretenic and
frappe_giving import it and pass it to `configurePortals` alongside their own
brand and session fetcher. Per-site variation stays in the existing
`when(session)` predicate. This retires ADR 011's residual risk without the
`Portal Shell Settings` doctype it proposed — three static entries do not justify
backend surface, and the collapse from seven to three removes the pressure that
made the doctype look necessary.

### Faculty Worklist absorbs project reviews

CPs awaiting a faculty member's sign-off become a section of
[`FacultyWorklist.vue`](../../../frontend/src/pages/FacultyWorklist.vue), keyed
off the payload of `faculty.get_my_faculty_worklist` like the sections beside it.
The split is deliberate: **Faculty Worklist is what needs my action;
`/culminating-project` is where I browse everything I'm on.**

The section is gated on the **`Thesis/CP Advisor` capability**, the seeded peer
of `Placement Examiner` and `Manual-Verification Verifier` — not on whether the
user currently occupies a reader slot. Holding the capability *is* the statement
that culminating projects are your work, so an empty list is the useful answer
("nothing awaiting you") and a vanished section is not; an advisor wired to the
unit but between projects should see a 0, exactly as they do for the other two
routes. Reader slots count on their own as well, because this module's standing
rule is that manual entry wins: an advisor may be set directly on a project
without ever holding the capability.

External examiners stay out of it. Per [ADR 059](059-seminary-departments-and-faculty-capabilities.md)
they are not faculty and not `is_instructor`; they keep the existing Culminating
Project sidebar link, which `has_culminating_projects` already counts them into.
The page keeps its name.

### One server-side flag decides the Faculty Worklist link

The sidebar gate hand-checks two capabilities
([`AppSidebar.vue`](../../../frontend/src/components/AppSidebar.vue) `#L105-L107`:
`Manual-Verification Verifier` or `Placement Examiner`) while the page renders
**three** sections, gated independently on its own payloads. A mentor-only user
with competency assessments due therefore has no sidebar link to the one page
that would show them their queue — and adding Project Reviews as a fourth section
would widen the gap again.

`get_user_info` gains **`has_faculty_worklist`**, true when any section would
render, and the sidebar gates on that single flag. The rule: *the link and the
page must be decided by the same logic*, and that logic lives on the server,
where the sections' data already comes from.

### Route guards where the backend will refuse

`/partner/*` redirects away in the router's `beforeEach` unless the session has a
`partner_org`. This is a **UX guard, not a security boundary** — `_require_org`
already refuses server-side, and that stays the enforcement. The guard exists so
a user is never invited to fill a form the server will reject.

Scope is deliberately narrow: only `/partner/*`, and only on a flag
`get_user_info` already returns. Routes whose empty state is honest (an examiner
opening an empty Culminating Project list) are left alone. A general per-route
role-guard layer is **not** adopted here.

### `Academics User` is merged on every migrate, not once

The merge moves from a one-shot patch to `install.after_migrate` (already wired
at [`hooks.py`](../../seminary/hooks.py) `#L251`), so a role that three
third-party apps keep recreating is collapsed into `Program Chair` each time it
comes back. It reuses `rename_doc(..., merge=True, force=True)` — the same call
the patch makes — and no-ops when the role is absent, which is the steady state
on a site without erpnext, hrms or frappe_giving.

The patch stays as-is for its historical role; the hook is what holds the line.
We deliberately do **not** fork erpnext or hrms to strip the DocPerm: the role's
resurrection is cheap to absorb and vendoring those apps is not.

## Alternatives considered

**Keep the tiles, dedupe by hiding the sidebar link instead** — rejected. It
optimises the wrong surface: the sidebar is in-app and free, the tile costs a
page load.

**A `Portal Shell Settings` single doctype** (ADR 011's own proposal) — deferred,
not rejected. Revisit if portals become genuinely site-configurable; three
compile-time entries do not warrant a fetch at boot.

**Rename Faculty Worklist to "My Worklist" and serve external examiners from it**
— rejected. It would blur the faculty/external separation ADR 059 established
deliberately, to spare one sidebar entry for a small audience.

**Fork erpnext/hrms to remove the `Academics User` DocPerm** — rejected.
Vendoring two upstream apps to delete three lines is far more expensive than
absorbing the role on each migrate.

**A one-shot patch for `Academics User` (again)** — rejected; that is what is
already in place, and the role came back. Anything that runs once loses to
something that runs every migrate.

**A general per-route role-guard layer for the SPA** — deferred. Every route is
currently server-permissioned and most empty states are honest. `/partner/*` is
guarded because it actively invites a form submission that cannot succeed; that
is a specific defect, not a reason to build a guard framework.

## Consequences

**Easier:** most users see no portal switcher at all, since it hides itself below
two visible tiles. "Is this a portal?" has a mechanical answer — does it have its
own base path — so new audiences no longer add tiles by default. The registry has
one home, so it cannot drift again. Faculty get one place that answers "what needs
me today", and the link to it finally agrees with the page. No tile can point at
an uninstalled app. `Academics User` stops coming back.

**Harder / residual:**

- Partner navigation now depends on a sidebar link that must not regress; a
  partner-only user has no other way in. The route guard and that link are the
  same user's only path — regressing either strands them, so they ship and are
  verified together.
- Portal membership becomes a decision rather than an addition — new audiences
  need an explicit call, which is the point, but it is a step that did not exist.
- `has_faculty_worklist` must be kept in step with the page's sections. Moving
  the decision server-side removes today's drift but does not make it impossible;
  a section added to the page without a matching clause in the flag reintroduces
  exactly the bug this fixes.
- `after_migrate` now carries a correction for someone else's data. If erpnext or
  hrms ever gives `Academics User` real permissions, silently merging it away
  would destroy them. The merge away is safe only because Academics User is used
  by other Frappe products incompatible/redundant with seminary: education and lms.
- Role names created via `_()` in `install.py` (see Context). Inert
  today; revisit only if a site sets `lang` in `site_config.json`, which would
  make it real. Not a problem on hosted installs (no access to it).
- **Left open:** no route in the seminary SPA carries a role guard beyond the
  `/partner/*` case above, so any logged-in user can navigate to
  `/faculty-worklist` or `/culminating-project` and receives an empty or
  API-driven error state rather than a router-level block. Permissions are
  enforced server-side, so this is a UX question, not a security one.

