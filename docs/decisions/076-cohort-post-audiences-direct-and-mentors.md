# 076 — Cohort post audiences: making `direct` reachable, and a `mentors` level

**Date:** 2026-09-22
**Status:** Accepted

Amends [ADR 064 §6](064-discipleship-cohorts-and-channels.md) (post visibility levels).

## Context

ADR 064 specified four visibility levels on `Cohort Post`: `cohort_only`,
`portal_users`, `private`, and `direct` ("only the two people, never portal-wide
and never seen by the cohort"). Three of them work. **`direct` has never been
reachable**: the doctype's `visibility` Select offers only
`cohort_only / portal_users / private`, so the value can't be set — while
`CohortPost.validate()` checks it, `permissions._visibility_clause` implements it
twice (query and `has_permission`), `feed_api.create_post` handles
`direct_recipient`, and the frontend threads `direct_recipient` through both the
compose and edit drafts and sends it to the API. Everything exists except the
option and a picker.

It stalled on two questions that were never resolved:

1. **Picking a person doesn't scale with lineage.** `direct_recipient` is a plain
   `Link → Person` with no query filter, so the picker searches every Person on
   the site. As cohort trees grow this is both unusable and wrong — it offers
   people the author cannot reach.
2. **1:1 may be the wrong arity.** The motivating case is "a post for all the
   mentors in my cohorts", which is an *audience*, not a recipient.

### What already occupies this space

| Mechanism | Audience | Lands in |
|---|---|---|
| `Seminary Announcement` (ADR 045) | staff-chosen checkboxes, term/program/course | email/SMS/Inbox, with a delivery grid |
| `broadcast_to_leaders` (`discipleship/api.py`) | **`is_leader = 1`** within `led_cohorts()` | Inbox, via `comms.send_message` |
| `Cohort Post.visibility = 'direct'` | one person | the feed — but unreachable |

### Correction: leaders are not mentors

It is tempting to assume the mentors audience already exists as the broadcast's.
It does not. `Cohort Membership` carries **two orthogonal fields**:

- `is_leader` (Check) — who runs the cohort; drives `led_cohorts()` and therefore
  moderation scope and the leader broadcast.
- `role` (Select: `Member` / `Mentor`) — the pastoral function.

A cohort may have a leader who is not a mentor, and mentors who do not lead. So a
mentors audience reaches a genuinely different set of people than
`broadcast_to_leaders` does, and cannot reuse `_leader_recipients`.

## Decision

### `direct` becomes reachable, scoped to who the author can actually reach

Add `direct` to the `visibility` Select, and give the composer a recipient
control backed by a **whitelisted search over the author's visible cohorts** —
the set `permissions.visible_cohorts()` already computes (active memberships plus
the subtree beneath cohorts the author leads). Type-ahead, so lineage size is
irrelevant: the list is never enumerated, only searched. Results show the
person's cohort as a disambiguator, because the same name can appear in several.

The picker is scoped for correctness, not just ergonomics: an author must never
be offered a recipient the permission layer would then refuse.

### A `mentors` audience level, not a general predicate

`visibility` gains **`mentors`**: visible to the mentors of the post's cohort and
its descendants, plus the author. The permission clause extends by one branch,
alongside the existing four:

```
(visibility = 'mentors' AND (
    author = me
    OR EXISTS (Cohort Membership
               WHERE person = me AND role = 'Mentor' AND active = 1
                 AND cohort IN descendants(post.cohort))))
```

A general `scope × role` predicate (any role, any scope) was considered and
**rejected, primarily to keep the UI simple for most people**. A predicate turns
one Select into two coupled controls that every author sees, in order to serve a
case only leaders have — and the composer is the most-used surface in Community.
Secondarily it would stand up a second audience model beside ADR 045's, and only
one of its combinations has a stated use. One named level answers the actual need
and can be widened later if a second audience earns its place. This follows the
same instinct as [ADR 065](065-competency-based-education.md)'s refusal to derive
what nobody asked for.

### The option appears only for authors who can use it

Following directly from that reason: `mentors` is rendered in the composer's
visibility Select **only for staff and leaders of the post's cohort** — the same
test that authorises it (below). For everyone else the composer is unchanged:
the three options they see today, plus `direct`. Simplicity for most people is
achieved by not showing them the control at all, rather than by keeping the
control small.

Scope is the post's cohort **and its descendants**, mirroring how
`led_cohorts()` treats a leader's subtree — "my cohorts" for a leader with a
split-off tree means the tree, and a mentors post that stopped at the parent
would miss exactly the people a growing cohort family needs to coordinate.

### It stays a post, not a message

`mentors` is a visibility level on `Cohort Post`, so it keeps threading,
comments, reactions and saves, and it is covered by the *same* permission clause
that already secures comments and reactions (they cache the parent post's scope,
per `cohort_post.on_update`). Generalising `broadcast_to_leaders` instead would
have been cheaper but produces a notification nobody can reply to, and splits
cohort conversation across the feed and the Inbox.

### Governance: who may author to an audience

Authoring a `mentors` post is restricted to **staff or a leader of the post's
cohort** — the same test `can_broadcast()` applies, for the same reason: reaching
everyone in a role across a subtree is a leadership act, not a member act.
`direct` carries no such restriction; any member may write to one person they can
already reach.

## Consequences

**Easier:** the direct level ADR 064 specified finally works, and the picker
cannot offer an unreachable recipient. Coordinating mentors across a cohort
family becomes a thread rather than a broadcast nobody can answer.

**Harder / residual:**

- A fifth and sixth visibility level make `_visibility_clause` the most intricate
  query in the module. It is already the one place all three doctypes' scoping is
  decided, which is an argument for keeping it — but it now warrants tests per
  level rather than per doctype.
- `mentors` posts are invisible to the cohort they are attached to, so a cohort's
  feed no longer shows everything posted "in" it. That is the point, and it is
  the same property `private` and `direct` already have.
- Adding a level means auditing every place that enumerates visibilities: the
  composer Select, the edit dialog, `visIconMap` in the frontend, and any
  analytics that group by visibility.
### Private replies already exist, on every post — correction

An earlier draft left open "whether a mentor should be able to reply privately to
the author rather than to the whole group", claiming comments merely inherit the
post's scope. **That was wrong.** `Cohort Post Comment.is_private` is a real
field, `comment_query` / `comment_has` already scope a private reply to *the
comment's author, the post's author, and the leaders of the post's cohort*,
`feed_api.add_comment` accepts `is_private`, and the reply composer has always
shown a checkbox for it ("Private — only the author and leaders will see this"),
with a lock badge on the rendered comment.

It is deliberately **not** restricted to mentors, and that stays: shepherding is
the motivating case, but any member may need to answer a post author privately,
and narrowing an existing freedom to serve a role would be a regression. It is
also available on *every* post, not only `mentors` ones — so the shepherding path
does not depend on this ADR's new levels at all.

Consistent with ADR 064's treatment of `private` and `direct`, a private reply
stays outside the moderation queue; leaders can see it because they can already
see everything in cohorts they lead, not as a moderation affordance.

## Consequences (continued)
