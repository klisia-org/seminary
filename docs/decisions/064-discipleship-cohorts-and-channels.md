# 064 — Discipleship Cohorts & Channels ("Community") subsystem

**Date:** 2026-07-22
**Status:** Proposed — design approved; implementation deferred and phased

## Context

The seminary wants an **engaging, discipleship-oriented social space** — closer to Discord/Reddit than
Facebook — that starts with **students in mentoring cohorts** and follows them into **alumni**. Once
alumni, leaders **self-manage** their cohorts within guardrails: inviting others and **splitting /
multiplying** the cohort while always retaining leadership, producing a trackable **lineage**. The
space extends to **less-educated pastors mentored by alumni**, who get lightweight portal access, and
lets pastors also engage with **portal-wide** (extra-cohort) posts. The whole space is
registered-users-only — there is no anonymous/public tier.

Content is organized into **channels** — Sermon Lab, Exegetical Insight, Family Ministry, Children's
Ministry, Discipleship, Missions, Prayer, Personal Challenges — and channels **interconnect** via
tags: a sermon tags the Bible passages and topics it treats; the Exegetical channel can then surface
any sermon or challenge tied to a passage.

Two channels lean on hard problems. **Sermon Lab** needs timestamped comments on videos. **Exegetical
Insight** needs comments/posts that pertain to *multiple, variable, possibly cross-chapter* verse
ranges, findable by passage overlap. Both must reuse what the app already has rather than grow a
parallel stack.

This ADR records the **design only**. No code ships with it; implementation is phased at the end.

## Decision

Introduce a **Discipleship (Community) subsystem** — a Person-centric, cohort-scoped social layer that
reuses the identity spine, the comms ledger, the Bible integration, and the anchored-comment model. It
**coexists** with `Student Group`, which stays a course-scoped grading grouping — no merge.

### 1. Cohort spine carries lineage; self-management is guarded by type flags

Three doctypes, mirroring the spine/role/membership separation the codebase already favors:

| Doctype | Key fields |
|---|---|
| **Cohort Type** (guardrail template) | `type_name`, `category` (Student / Pastor-Mentoring / Alumni-Peer / Mixed), `program` (Link, nullable), `course` (Link → Course, filtered by the program's courses), `auto_enroll_on_join` (Check), `open_enrollment` (Check), `allow_self_split` (Check), `default_visibility` (cohort_only / portal_users), `default_max_size` (Int), `default_channels` (Table MultiSelect → Cohort Channel), `graduates_to` (Link → Cohort Type, nullable) |
| **Cohort** | `cohort_name`, `leader` (Link → Person), `cohort_type` (Link), `parent_cohort` (Link → Cohort, nullable = root), `lineage_root` (Link → Cohort, denormalized, set on create, immutable), `status` (Active / Archived), `visibility` (defaults from type), `max_size` (defaults from type) |
| **Cohort Membership** (standalone, **not** a child table) | `cohort` (Link), `person` (Link), `role` (Mentor / Member), `is_leader` (Check), `invited_by` (Link → Person), `invite_status` (Invited / Active / Left / Removed), `course_enrollment` (Link → Course Enrollment Individual, read-only), `joined_on`, `left_on`, `active` (Check) |

`lineage_root` is denormalized on creation (root → self; child → parent's root) so "show me this whole
cohort family" is a single filtered query instead of a recursive walk. Membership is a standalone
doctype — not a child table — because it has an independent lifecycle and its own row-level
permissions, the same reasoning that made `Course Enrollment Individual` (CEI) standalone.

Self-management operations are whitelisted server methods gated by **leader capability + Cohort Type
flags**: **invite** (leader adds a membership; `ensure_person()` for new people), **split/multiply**
(only if `allow_self_split` — creates a child Cohort inheriting `lineage_root`, moves selected
memberships, retains the leader's subtree oversight), and **archive** (status flip, memberships
preserved for history). "Leader special access" is a **cohort-scoped capability derived from
membership** (`is_leader` on an active row), *not* a global role — the same posture as
[ADR 053](053-partner-organization-subsystem.md).

### 2. One unified Post model; channels are a shared catalog

Channels are a catalog; a Cohort inherits channels from its type's `default_channels`. A post
references a `(channel, cohort)` pair — **`cohort` is not nullable and is pre-filled, hidden on the form** as we want cohort members to always preferentially engage with each others posts,
with `visibility` governing reach.

| Doctype | Key fields |
|---|---|
| **Cohort Channel** | `channel_name`, `channel_kind` (generic / video_timestamp / bible_passage / prayer), `default_visibility`, `icon`, `description` |
| **Cohort Post** | `channel` (Link), `cohort` (Link, required, pre-filled + hidden), `author` (Link → Person), `title`, `content` (Text Editor), `visibility` (cohort_only / portal_users / **private** / **direct**), `direct_recipient` (Link → Person, required when `visibility=direct`), `status` (draft / published / blocked / pinned), prayer flags `prayer_answered` (Check) + `prayer_answered_on` (Date, read-only) + `prayer_answer_note` (Text), `reference_doctype` + `reference_name` (Dynamic Link — e.g. the source video for Sermon Lab) |
| **Cohort Post Comment** | `post` (Link), `parent_comment` (Link → self, nullable = **threading**), `author` (Link → Person), `content`, `status`, **generalized anchor**: `anchor_type` (General / Timestamp / VerseRange / TextRange / Region), `timestamp_s` (Int), `verse_start_ord` + `verse_end_ord` (Int), `range_from`/`range_to`, `page`/`x_pct`/`y_pct` |
| **Cohort Post Reaction** | `post` + `comment` (nullable), `person`, `reaction_type` (Link → **Cohort Reaction Type**) |
| **Cohort Reaction Type** (catalog, seeded via install hook) | `label`, `glyph` (unicode emoji), `sort_order`, `enabled` |
| **Cohort Content Flag** | `target` (Dynamic Link → Cohort Post / Cohort Post Comment), `reporter` (Link → Person), `reason` (Select), `detail` (Small Text), `status` (Open / Reviewed / Dismissed / Actioned), `reviewed_by`, `reviewed_on` |

`Cohort Post Comment` **directly generalizes `Assignment Submission Comment`** (`anchor_type` ∈
General/Page/Region/TextRange/Timestamp + `timestamp_s`). On a Sermon Lab post its comments carry
Timestamp anchors; on an Exegetical post they carry VerseRange anchors. Nesting via `parent_comment`
gives Reddit-style threads.

**Reactions use a seeded catalog, not a free emoji picker.** `Cohort Reaction Type` (seeded via the
install hook, create-only-if-missing — the same posture as `Partner Type` / `Skill Tag`) holds a small,
ministry-appropriate set (👍 like, 🙏 pray, 🙌 amen, 💡 insightful) as `glyph` + `label`; admins extend
it without code and without bundling a full emoji package (which adds weight and an off-tone/moderation
surface). **Flagging is a separate act from reacting:** a `Cohort Content Flag` lets any reader report a
post or comment (dynamic link + `reason`), creating an item in a moderation queue — never a reaction
glyph.

Interconnection rides tag structures on the post: **Cohort Post Topic** (catalog, hierarchical
via `parent_topic`) linked through a `Cohort Post Topic Link` Table MultiSelect; **Cohort Post
Scripture Ref** (child: `display`, `resolved_ref`, `verse_start_ord`, `verse_end_ord`); and a
self-referential **Cohort Post Link** child (`linked_post` → Cohort Post, `relation_type`:
journal / reflection / related) for author-curated post-to-post ties. Because topics and scripture
refs are normalized, the Exegetical channel browsing "John 3" surfaces *any* post — a Sermon Lab
video, a Personal Challenge, a prayer — whose range overlaps, via one indexed query.

**Two new personal-visibility levels.** The community is registered-users-only — there is no anonymous
tier, so `portal_users` (any signed-in community member, cohort or not) is the widest reach. Beyond
`cohort_only` / `portal_users`, a post may be **`private`** (only the author — personal prayers and
journal entries) or **`direct`** (author + one named `direct_recipient` — an *exhortation* stays between
the two people, never portal-wide and never seen by the cohort). Both still carry the required `cohort` for attribution/lineage, but `visibility` overrides
who reads — so the permission clause must be visibility-aware (§5), not "any cohort member sees any
cohort post."

**Prayer is a first-class post type**, not a new doctype — it is a `channel_kind = prayer` post with the
`prayer_*` flags above, plus dedicated views:
- **Prayer list** = posts on a prayer channel with `prayer_answered = 0`, ordered for active
  intercession. **Mark answered** sets `prayer_answered = 1` + `prayer_answered_on` + an optional
  `prayer_answer_note` (the testimony), which **removes it from the active list** but keeps it in a
  **"Answered prayers"** view (`prayer_answered = 1`).
- **Journal / reflection linkage**: a prayer author links private `journal`/`reflection` posts via
  **Cohort Post Link**, so when the prayer is later marked answered the "Answered prayers" view can
  surface the linked reflections — letting the author *recall the journey* that led to the answer.
- Personal prayers and journals use `visibility = private`; cohort or portal-wide prayer requests use
  `cohort_only` / `portal_users` as normal.

### 3. Sermon Lab reuses the anchored-comment model, not a new one

A Sermon Lab post is `channel_kind = video_timestamp` with a dedicated `video_url` field holding a
**YouTube link** — required for new Sermon Lab posts. YouTube-only (no uploads) is a deliberate
storage/performance choice, matching how the existing assignment video feature works. Timestamp
comments are `Cohort Post Comment` rows with `anchor_type=Timestamp` + `timestamp_s`, added via the
generic `add_comment` (anchor_data `{timestamp_s}`). The frontend reuses the existing
`YouTubePlayer.vue` (iframe API: "comment at current time" → capture `getCurrentTime`; click a comment
→ `seekTo`) rather than a native `<video>`.

### 4. Exegetical ranges use canonical verse ordinals (no verse table)

The current `parse_reference()` (`integrations/bible.py`) **explicitly refuses** cross-chapter and
multi-passage refs, and OSIS strings are not SQL-range-queryable. So:

- Add `BOOK_ORDER` (OSIS → 1..66) to `bible_books.py`, derived from the existing canonical `_BOOKS`
  order.
- **Ordinal = `book_index * 1_000_000 + chapter * 1_000 + verse`** (chapters/verses always < 1000).
  Strictly **monotonic** across the canon, so ordering and range-overlap are exact even though ordinals
  are non-contiguous — we never *count* verses between two points, only compare.
- A passage → one or more `[verse_start_ord, verse_end_ord]` segments stored as `Cohort Post Scripture
  Ref` rows. Whole chapter → `[C*1000+0 … C*1000+999]`; whole book → `[book*1e6 … book*1e6+999999]`.
- **Overlap query** (posts touching passage `[q1, q2]`): `verse_start_ord <= q2 AND verse_end_ord >=
  q1`, indexed on both columns. Works cross-chapter and cross-book.
- Add a richer `parse_reference_segments()` beside `parse_reference()` that handles cross-chapter
  (`Jn 3:36-4:3`) and multi-passage (`Jn 3:16; Rom 8:28`) by returning a **list** of segments — each
  still OSIS-resolvable for api.bible text via `lookup_passage`. The strict single-segment
  `parse_reference()` is left untouched for its current caller (quiz scripture matching).

**Per-user preferred Bible version.** `_resolve_bible_id()` (`bible.py`) currently falls back to
language defaults only. Add a `preferred_bible_id` (Data) custom field on **User** (mirrors the
`language` custom-field pattern; Person unchanged), a picker in `ProfileModal.vue` saved via a new
whitelisted `set_user_bible()` (mirror `set_user_language()`) fed by a **portal-safe**
`get_available_bibles_for_user()` (the existing `list_bibles()`/`get_bible_name()` stay admin-only),
and a step in `_resolve_bible_id()` that returns `User.preferred_bible_id` when set before the
language-default fallback — so every passage render honors the reader's version.

### 5. Row-level visibility follows the ADR 053 scoping template

A new subpackage `seminary/seminary/discipleship/permissions.py` — a plain Python package under the
existing **Seminary** module, not a new Frappe module (a new module clutters the desk); all new
doctypes carry `"module": "Seminary"`. Registered in `hooks.py` alongside the existing
`permission_query_conditions` / `has_permission` maps:

- `my_cohorts(user)` → active `Cohort Membership.cohort` for the user's Person (per-request cached);
  leaders additionally get their **subtree** via `lineage_root` / `parent_cohort` — but subtree
  oversight applies to `cohort_only` / `portal_users` posts **only**; `private` and `direct`
  posts are never visible to leaders (personal prayers and exhortations are sensitive).
- `get_permission_query_conditions(user)` on Cohort Post / Comment / Reaction is **visibility-aware**
  (staff bypass → `""`; `me` = the user's Person) — because private/direct posts still carry a cohort,
  a blanket `cohort IN (my_cohorts)` would leak them to the whole cohort:

  ```sql
  visibility = 'portal_users'
  OR (visibility = 'cohort_only' AND cohort IN (my_cohorts))
  OR (visibility = 'private'     AND author = me)
  OR (visibility = 'direct'      AND (author = me OR direct_recipient = me))
  ```
- `has_permission(doc, ptype, user)`: deny-only single-doc gate mirroring the clause above;
  write/moderate gated on leader capability or authorship. Answering a prayer, editing an
  `answer_note`, or reading a `direct`/`private` post is authorship-gated regardless of cohort role.
- Moderation/internal fields (block reason, `invited_by`) sit at **permlevel 1**, reader-visible content
  at permlevel 0 — the same discipline as Communication Log
  ([ADR 043](043-multichannel-communication-system.md)).
- Per [ADR 034](034-role-taxonomy.md), at most a thin **`Cohort Leader`** and **`Cohort Participant`**
  (invited pastors) portal role for menu/route gating; authorization stays membership-derived, not
  role-derived.
- **Moderation authority is Leader + Staff.** Cohort leaders moderate within their `lineage_root`
  subtree (block/pin posts, resolve `Cohort Content Flag`s on their cohorts' content); staff moderate
  globally. Both work the same flag queue. `private` / `direct` posts stay out of scope even for
  moderators.

### 6. Pastor onboarding through the Person spine; billing rides the CEI seam

**Invited pastors:** a leader invite calls `ensure_person()` ([ADR 042](042-person-identity-spine.md)
— the *only* onboarding mutation point) from the pastor's email/mobile, creates a
`Cohort Membership(invite_status=Invited)`, and delivers the invite via `comms.send()`
([ADR 043](043-multichannel-communication-system.md)) per channel + consent. Acceptance provisions a
light portal `User` with the `Cohort Participant` role, scoped by §5 to their cohort(s) + portal-wide
channels only.

**Billing mirrors the Culminating Project pattern — no new financial seam.** When `Cohort Type.course`
is set and `auto_enroll_on_join` is on, activating a membership **auto-enrolls the member's active
Program Enrollment into that course** by reusing the existing primitive `course_enroll(pe_name,
course_schedule)` — exactly how `enroll_in_project_course()`
(`doctype/culminating_project/culminating_project.py`) and `required_enrollment.py` already do it.
Billing then rides the **CEI's own** `on_submit` → `generate_enrollment_invoice()` →
`FinancialBackend` → oikonomos ([ADR 063](063-financial-backend-boundary-and-bridge-apps.md)). The
subsystem creates a CEI and lets the standard workflow invoice it; it **never names a billing
doctype**. Auto-enroll is guarded to members with an active Program Enrollment; pastor-only members in
a free cohort simply skip it. The membership's read-only `course_enrollment` link records the tie for
audit and idempotency, mirroring `Culminating Project.course_enrollment`.

### 7. Notifications avoid per-member fan-out; portal-wide threads foreground the cohort

Writing one Communication Log row per member per post does not scale. Instead: post/comment creation
fires Socket.io `refetch_resource` for live feed refresh; a lightweight per-member **read-state**
(last-seen timestamp per cohort/channel) computes unread counts with no fan-out rows; and a background
job sends In-App via `comms.send()` **only to members opted in for immediate**, batching the rest into
a digest — ADR 043-compliant without ledger bloat.

Even on **portal-wide** (`portal_users`) posts we foreground intra-cohort engagement: the feed/thread
API returns, per post and comment, an `author_membership` hint (`cohort_member` vs `outside`) relative
to the post's cohort, cheap to compute from `Cohort Membership`. The frontend badges cohort-member
authors and **ranks their replies above outside replies** (a secondary sort after pin/recency), keeping
intra-cohort discussion foremost while extra-cohort voices stay visible.

### 8. Frontend lives inside the existing portal; only pastors get a new one

Community is a **page inside the student/alumni portal** — a `/seminary/community` route and nav entry,
modeled on `Inbox.vue` (channel-filtered feed, threaded post/comment view with reactions, composer;
channel-kind renderers for the video timeline and the passage reader). Students and alumni do **not**
switch portals. Only **Cohort Participants** (invited pastors) get a dedicated portal entry in
`PortalSwitcher.vue` + an `after_login` home, scoped by §5 to their cohort(s) and portal-wide channels.

## Consequences

Easier: the subsystem reuses Person for identity, `comms.send()` for delivery, the anchored-comment
model for both video and scripture, the CEI seam for any billing, and the ADR 053 scoping recipe for
visibility — so consent, private-file serving, invoicing, and row-level permissions come nearly for
free. Verse ordinals make cross-channel "what touches this passage" a single indexed query with no
verse table to maintain. Lineage denormalization keeps cohort-family queries flat. Students and alumni
gain the space without a portal switch.

Prayer costs almost nothing extra: it is flags + views on the post model, and its journal linkage
reuses the same `Cohort Post Link` that connects any two posts. The `private`/`direct` levels give
personal prayers, journals, and exhortations a home without a second doctype.

Harder: one generalized `Cohort Post Comment` carries anchor fields most posts never use (accepted —
it matches the existing `Assignment Submission Comment` tradeoff); `parse_reference_segments()` adds
parsing surface (cross-chapter, multi-passage, whole-book) the strict parser deliberately avoided; a
member who is both a student and a paid-cohort participant is several linked records (Person +
Membership + CEI) rather than one; the `private`/`direct` levels make the permission clause
**visibility-aware** rather than a simple cohort-membership check — every reader of the Cohort Post
list query (feed, search, "related" rail) must go through it, and any future denormalized cache of
posts must not bypass it; and moderation of portal-wide, extra-cohort content (blocking, pinning, abuse) is
a genuinely new concern this app has not had before.

### Phasing (deferred)

1. **Cohort spine** — Cohort Type, Cohort, Cohort Membership; lineage + split/invite ops; permission module.
2. **Generic channel + posts** — Cohort Channel, Cohort Post/Comment (threaded) + Reaction + seeded Cohort Reaction Type; feed API; portal page; notifications (§7).
3. **Tagging** — topics + scripture-ref ordinals; `Cohort Post Link`; cross-channel overlap query + "related" rail.
4. **Prayer & journal** — prayer channel + `prayer_*` flags; active/answered views; `private`/`direct` visibility; journal linkage that resurfaces reflections when a prayer is answered.
5. **Sermon Lab** — video-timestamp channel reusing the anchor model.
6. **Exegetical Insight** — segment parser + passage reader + verse-anchored comments + per-user preferred Bible version.
7. **Billing wiring** — `Cohort Type.course` + `auto_enroll_on_join` → `course_enroll` on activation → CEI/FinancialBackend.
8. **Pastor onboarding** — invite flow, `Cohort Participant` role + new portal, comms invites.
9. **Portal-wide engagement + moderation** — extra-cohort posts, intra-cohort ranking, `Cohort Content Flag` queue + Leader/Staff moderation, blocking/pinning.

## Open questions

The four questions raised at design time are **resolved**: read-state is **last-seen per (person,
cohort, channel)** (§7); reactions are a **seeded `Cohort Reaction Type` catalog** (glyphs, admin-
extensible) rather than a bundled emoji package, with abuse handled by a **separate `Cohort Content
Flag`** (§2); **moderation is Leader + Staff** via the flag queue (§5); and the verse-ordinal helpers
live in `integrations/bible_books.py` (§4).

Still open, deferred to their phases:
- The exact `Cohort Content Flag.reason` vocabulary, and whether a leader's moderation reaches the whole
  `lineage_root` subtree or only their direct cohort (Phase 9).
- Whether `direct` should ever allow a small recipient set (2–3) instead of a single `direct_recipient`
  — revisit if mentors exhort subsets in practice, which would make `direct_recipient` a child table.

- During development a concern was raised: today, file size limits are site-wide. Communities may use too much system resources, and it may be interesting to have some granularity. This will need its own ADR, deferred for now.
