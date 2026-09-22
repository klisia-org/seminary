# 077 — Alumni organization membership: the lifecycle after "create"

**Date:** 2026-09-22
**Status:** Accepted

Extends [ADR 053](053-partner-organization-subsystem.md) (partner subsystem) and
[ADR 070](070-alumni-reachability-and-peer-contact.md) (alumni-facing org
surfaces).

## Context

An alumnus with `allow_alumni_create_partner_org` can submit a new Partner
Organization: `partner.api.create_partner_organization` creates it as
`Prospect` / `Pending Approval` and records them as a `Partner Contact` with
`portal_access = 1`, which `Partner Organization.on_update` converts into the
`Partner` role. From there the affordances stop. Testing found three distinct
gaps, plus a duplication underneath them.

### 1. Editing the org is possible — but unreachable from where they are

Because they hold the `Partner` role, the creator *can* edit the organization,
through `/partner/profile` → `portal.update_org` (`_require_org` accepts them,
since `_my_orgs()` reads exactly their portal-enabled contact rows). Nothing in
the alumni portal says so: `MyOrganizationsPanel` calls only
`get_my_organizations` (read) and `create_partner_organization` (create), and
never links onward. This is a **discoverability** gap, not a capability one.

### 2. There is no way to change your own role at an org

`Partner Contact` carries `role_at_org` and `is_primary`, set once at creation
and never editable by the person they describe. `portal.create_contact` adds
*other* people; there is no update-own-contact anywhere in `partner/portal.py`
or `partner/api.py`.

### 3. There is no way to leave

`Partner Contact.relationship_status` exists as a Select
(`Active` / `Inactive` / `Former`) and **nothing ever transitions it**. No API
clears `portal_access`, removes the contact row, or reassigns `is_primary`. And
`add_roles("Partner")` has no counterpart: the partner module contains no
`remove_roles` call at all, so the role outlives any relationship it represented.

### Underneath: two different facts that the UI presents as one

`Alumni Profile` carries `current_role`, `current_organization` (free text) and
`current_partner_organization` (Link). `Partner Contact` carries `role_at_org`
and `is_primary`. It is tempting to call this a duplication and pick a winner.
**It is not.** They record two genuinely different things:

- **Employment** — *where this alumnus works*. It may have nothing to do with the
  seminary. An alumnus not using their degree professionally may still want to
  say they work at a large employer so classmates working there can find them
  ([ADR 070](070-alumni-reachability-and-peer-contact.md) peer discovery). That
  must not require standing up a Partner Organization for that employer, and
  nobody should be invited to submit one.
- **Representation** — *this alumnus acts for this organization as a partner*. A
  pastor whose church becomes a partner is the motivating case, and here the role
  belongs to the partner relationship, not to the person's employment history.

`current_partner_organization` is the bridge for when the two coincide. So the
real defect is presentational: the profile offers these as one undifferentiated
"where I work", so the alumnus cannot tell which question they are answering, and
the only editable half is the one that carries no partner meaning.

## Decision

### Editing org info is a link, not a second implementation

`MyOrganizationsPanel` links each org the alumnus manages into the partner area
rather than growing its own edit form. Per [ADR 074](074-portal-taxonomy-one-portal-per-spa.md)
these are routes of one SPA and the sidebar already reaches them; per
[ADR 075](075-secondary-navigation-and-page-tabs.md) the partner areas are tabs.
Duplicating the org form into the alumni portal would be a second surface to keep
correct for no gain.

### Leaving is a status transition, not a deletion

Leaving sets `relationship_status = 'Former'` and clears `portal_access`,
preserving the row. The organization's history should keep saying who set it up —
deleting the contact would erase a real fact, the same reasoning ADR 066 applies
to archived cohorts.

Clearing the last `portal_access` for a user must also revoke the `Partner` role,
or the role becomes permanent on first use.

### Role derives where a partner relationship exists; free text where it does not

The profile separates the two questions. Employment stays free text and is always
editable by the alumnus. When `current_partner_organization` is set, the role
shown for that organization is **derived from the `Partner Contact`**, not
re-typed — there is one relationship, and it already records the role.

Creating a Partner Organization is never a side effect of stating where you work.
It stays an explicit, separately-gated act (`allow_alumni_create_partner_org`).

### Every contact can leave from the Partner area, not only alumni

`get_my_organizations` — and therefore `MyOrganizationsPanel` — is gated on
`_require_alumni()` and the partner directory setting. A partner-organization
member who is not an alumnus has no alumni surface at all: per
[ADR 075](075-secondary-navigation-and-page-tabs.md) they see exactly **Partner**
and **Preferences** in the sidebar, which is the intent — they get the partner
area and nothing else.

So the self-leave control lives on the organization's own page in the partner
area, where every contact can reach it, and the alumni panel carries a second
copy for the alumni who live there. Putting it *only* on the alumni panel would
have made the ability to leave depend on being an alumnus, which is unrelated to
the relationship being ended.

### A contact may end their own relationship; the primary may end anyone's

Leaving sets `relationship_status = 'Former'` and clears `portal_access` (above).
The **primary contact** may additionally set any contact of their organization to
`Former` or back to `Active` — which is also the answer to rejoining: a `Former`
contact returns by being reactivated, not by creating a second row.

This is the governance line: managing who speaks for an organization is the
primary contact's job, not staff's and not every contact's. Staff retain their
existing full access.

### Orphaned organizations are staff's to resolve, with a report to find them

When the last portal contact leaves, the organization is **not** auto-deleted,
auto-archived, or blocked from being left. It simply has no contacts — the same
position as an org awaiting approval that nobody has adopted. Staff remove or
re-contact it by hand, exactly as they already approve listings.

What is missing is visibility, so this adds a report of **Partner Organizations
with no active portal contact**. Automating the removal was rejected: an
organization with no contact may be perfectly real and merely between people, and
deleting it would destroy a listing, its job openings and its history on a timing
coincidence.

## Consequences

**Easier:** an alumnus can correct or end a relationship they created, instead of
that record being permanent from the moment of submission.

**Harder / residual:**

- Revoking the `Partner` role touches a role the partner subsystem currently only
  ever grants. Anything assuming the role is monotonic needs checking.
- `is_primary` becomes reassignable, which means an org can transiently have no
  primary contact; whatever reads `is_primary` must tolerate that.
- A leave path invites the question of *rejoining*, which this ADR does not
  answer — a `Former` contact who returns is a fourth case.
