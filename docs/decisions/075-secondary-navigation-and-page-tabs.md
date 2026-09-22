# 075 — Secondary navigation: one page-tab primitive, addressable

**Date:** 2026-09-22
**Status:** Accepted

Follows [ADR 074](074-portal-taxonomy-one-portal-per-spa.md), which settled what a
*portal* is. This settles the level below it: how a page offers more than one
area without inventing a new control each time.

## Context

An audit of `frontend/src` found **nine distinct in-page mechanisms** for the
same job — letting the user switch between areas of a page:

| Mechanism | Uses |
|---|---|
| Native `<select>` as the primary view switcher | ~14 |
| `v-if` stack of `<section>`s, no switcher at all | ~10 pages |
| `router-link` rows/cards acting as tabs | 5 |
| frappe-ui `<Button>` `solid`/`subtle` used as tabs | 2 (at two different sizes) |
| Hand-rolled underline tab bar | 1 |
| Hand-rolled segmented control in a bordered box | 1 |
| Rounded-chip filter buttons / plain text toggles | 3 |
| `FormControl type="select"` doing the native select's job | 2 |
| Dialog-as-a-view, and in-place master→detail swap with no route | several |

Three findings matter more than the count.

**The primitive already exists and is unused.** frappe-ui ships `Tabs`
(reka-ui `TabsRoot`, animated indicator, keyboard accessible, supports vertical)
and `TabButtons` (a segmented `RadioGroup`). Neither is rendered anywhere.
`pages/InstructorProfile.vue` imports `TabButtons` and never uses it — a dead
import — and `stores/settings.js` exports an `activeTab` ref that nothing reads.
This was started twice and abandoned twice, which is why nine mechanisms grew in
the gap.

**Almost nothing is addressable.** Exactly one page keeps its sub-state in the
URL (`CompetencySelfAssessment.vue`, via an optional route param). Four more —
`Community.vue`, `CulminatingProject.vue`, `Inbox.vue`,
`SelfDevelopmentPlans.vue` — read a query param **once on load and never write
back**, so a reload or a shared link silently drops you on the first tab.
Everything else is a component-local `ref`. This is a large part of why the UI
feels disposable: nothing you are looking at has a name.

**Nav rules are duplicated per surface — the same defect ADR 074 just fixed one
level up.** There, the "which portals may this session see" rule existed in
three hand-rolled copies, two of which silently dropped the `when` predicate;
that is why a Donate tile kept appearing on sites without frappe_giving
installed. The shells repeat the pattern: `DesktopLayout` swaps in a whole
`PartnerSidebar` by route prefix, and `MobileLayout` re-implements the link rules
a third time, including its own `/partner` branch. Partner's navigation is
currently specified in three places.

The `<select>` count deserves naming plainly: a select is a control for choosing
a **value**, not for **navigating**. Using it as the primary view switcher hides
every option until opened, gives no sense of place, and cannot be linked to.

### Page headers are copy-pasted, and eight pages have none

The same problem one level up. The sticky page-header class string appears **68
times across `pages/`, in 9 distinct variants**:

| Variant | Copies |
|---|---|
| `flex items-center justify-between … border-b` | 36 |
| `flex items-center gap-2 … border-b border-outline-gray-1` | 9 |
| `flex items-center justify-between … border-b border-outline-gray-1` | 6 |
| `flex flex-col gap-2 … border-b border-outline-gray-1` | 5 |
| bare `border-b` (no flex at all) | 5 |
| `flex flex-col md:flex-row md:items-center justify-between` | 4 |
| three more one-off variants | 3 |

Twenty of them carry `border-outline-gray-1` and forty-eight do not, so the
divider is a visibly different colour depending on which page you are on. The
wrapper element is variously `<header>`, `<div>` and a bare `<h2>`.

**Correction, found during implementation.** An earlier draft of this ADR said
eight pages had *no* page header, naming `Courses`, `Enrollment`, `Fees`,
`Grades` and `ProgramAudit` among them. That was wrong, and it came from grepping
the contiguous string `sticky top-0`: those five write the same classes in a
different order (`text-xl font-bold … sticky flex items-center justify-between
top-0 …`), which is simply a **tenth variant**, not an absence. They needed
normalising, not a header added.

The genuinely headerless application pages were **`Community`** — a real gap, now
fixed — and **`CourseCheckin`**, a standalone kiosk page that is legitimately
headerless like `Login`. (`Home`, `Mock` and `RecommenderForm` are likewise
standalone or guest pages.) The variant and copy counts above are the
`sticky top-0`-ordered family only and undercount for the same reason; the
`sticky left-0` matches in the codebase are pinned table cells and unrelated.

The lesson worth keeping: a class-string survey measures *spelling*, not
structure, and copy-pasted Tailwind drifts in word order as readily as in
content. That is itself an argument for the component.

What goes *in* the header is equally unsettled: some pages put their whole filter
row up there, others put nothing. That inconsistency is most of what reads as
unpolished — the frame around the content keeps changing shape.

### "Back to …" is three different things wearing one coat

There is no rule for when a page offers a way back, and the app has grown three
mechanisms that look similar and mean different things:

1. **Breadcrumbs** — frappe-ui's `Breadcrumbs`, already used in **40 files**
   (the course/assessment/exam cluster). This is the de facto standard and
   nobody wrote it down.
2. **A back-link** — `ArrowLeft` + a destination label, ~9 uses, almost entirely
   in the partner/jobs/internship cluster, which has **no breadcrumbs at all**.
   So the app has two parallel location systems split by which part of the app
   you happen to be in.
3. **A return-to-origin action** — `useActivityReturn` + `examStore.returnContext`
   in `AssignmentForm`, `DiscussionActivityForm`, `ExamForm` and `QuizForm`.
   Conditional (`v-if="showBackToLesson"`), and it does not merely navigate: it
   splices the created activity back into the lesson. This is a *task
   completion* action that happens to be spelled like a back-link.

The surface drift on top of that: labels split between a bare destination name
(`Internships`, `Job Postings`, `Applicants`) and a literal `Back to X`
(`Back to lesson`, `Back to opening`, `Back to my courses`, `Back to list`);
icons split between lucide `ArrowLeft`, lucide `ChevronLeft` and frappe-ui's
`iconLeft="arrow-left"`; and placement split between the header and a loose
`Button` in the body (`CourseFeedback`, `CourseWithdrawalRequest`,
`CulminatingProject`).

## Decision

### One primitive: frappe-ui `Tabs`, below the page header

A shared `PageTabs` wrapper over frappe-ui's `Tabs`, rendered directly beneath
the page header, is the only way a page offers peer areas. Underline style: it
reads as navigation rather than as a form control, which is what it is.

#### Deviation, found in implementation

frappe-ui's `Tabs` could **not** be used directly, and `PageTabs` is a thin
shared component styled to match it instead. Two blockers, both structural:

1. `Tabs` wraps its list *and* its panels in one `flex flex-1 overflow-hidden`
   root, so it owns a scroll context. This app scrolls in `DesktopLayout`'s
   `#scrollContainer` and pins page headers with `position: sticky` inside it; a
   nested scroll context breaks both, and it makes "the tab row lives in the
   sticky header, the panel in the body" impossible — the two must be siblings
   under its root.
2. Its `v-model` is the tab **index**, which cannot round-trip through
   `?tab=directory`, and its active state cannot derive from the route.

Using reka-ui (the library underneath `Tabs`) directly was rejected: it is only
present in `node_modules` by hoisting, is not declared in
`frontend/package.json`, and frappe-ui is pinned at 0.1.261, so a future bump
could move it.

**Checked against frappe-ui 1.0.0-beta.8** (vendored in `apps/builder`), so this
is not re-litigated when the pin moves: an upgrade does **not** unblock it. 1.0
still depends on `reka-ui ^2.5.0` as a plain `dependency` (not a peer, so still
not ours to import), and `Tabs` still carries both blockers — the same
`flex flex-1 overflow-hidden` root and the same `:value="i"` index model on
`TabsTrigger`/`TabsContent`. `Tabs` remains the only export; there is no
standalone list to compose with.

The decision's substance is unchanged — **one** shared control, not nine
hand-rolled ones — and `PageTabs` implements the WAI-ARIA tabs pattern
(`role="tablist"`, roving focus, Home/End) rather than re-skinning buttons. But
the ADR should not claim to be using a component it could not use.

`TabButtons` is **not** adopted as a second *navigation* primitive. A rule of the
form "Tabs for page level, TabButtons for in-panel modes" is expressive but
requires a judgement call on every page, and a rule that needs policing is how
nine mechanisms happened. For navigation: one primitive, one answer.

### The toggle exception: state nobody would ever link to

A small class of controls is deliberately **not** navigation, and forcing those
into tabs would be worse, not more consistent. A **toggle** is allowed when all
of these hold:

1. It has exactly two states (or a tiny fixed set).
2. Both states show the *same kind of thing* — it changes a presentation mode or
   applies a binary filter **within** an area the user has already chosen.
3. It is not the page's primary area switcher.

The decidable test, and the one to apply when the above feels borderline:
**would you ever want to send someone a link to this state?** If yes, it is an
area, and it is a tab — that is the whole point of making tabs addressable. If
no, it is a toggle.

By that test the theme switch in `ProfileModal` is a toggle (nobody links a
colleague to dark mode; it persists per user, which is the right behaviour and
stays). Community's prayer Active/Answered is a toggle — a binary filter inside a
channel already chosen. Inbox's Received/Sent is **not**: those are two different
collections, and "look at what I sent you" is a link worth having, so it becomes
tabs.

Toggles keep their current hand-rolled form for now rather than gaining a
sanctioned component; there are few enough that a shared control would be
ceremony. If they proliferate, standardise them on `TabButtons` then — that is
what it is for — but do not let it drift into doing navigation.

### Tabs are always addressable, in one of two bindings

`PageTabs` supports exactly two bindings, and both put the active area in the
URL:

- **Route-backed** — where the areas are already sibling routes (`/partner/*`,
  `/alumni/profile` vs `/alumni/directory`). Tabs render as links; active state
  derives from the current route. No new state at all.
- **Param-backed** — where the areas are panels of one route (Inbox's
  Received/Sent, Culminating Project's student/reader views). A shared
  `useTabParam(key, default)` composable reads `?tab=` on mount and
  `router.replace`s on change.

`replace`, not `push`, so flipping between tabs does not bury the page the user
arrived from under a stack of history entries; the tab is still restored on
reload and still travels in a pasted link. An unrecognised value falls back to
the default rather than rendering an empty page.

Route-backed is preferred wherever the areas are already routes — it is strictly
less state. Param-backed exists so a page need not be restructured into child
routes just to become addressable.

### What is a tab, and what stays a `<select>`

- **A tab** is a peer *area* of a page: mutually exclusive, a stable set known at
  render, and something you would want to send someone a link to.
- **A select** chooses a *value* that parameterises one view: a program, a term,
  an academic year, a status filter, which cohort's feed, which organization.
  Open-ended or long lists stay selects.

So Community's cohort switcher and the Jobs/Internships/Directory filters remain
selects — correctly. Inbox's Received/Sent becomes tabs; its channel and category
filters stay selects.

### One `PageHeader`, and a rule for what belongs in it

A shared `PageHeader` component replaces all 68 hand-copied variants and is added
to the eight pages missing one. It owns the frame and nothing else:

- **title** (required), with an optional back affordance and subtitle;
- **actions** — page-level actions only, right-aligned: the buttons that act on
  the page as a whole (*New Job Posting*, *Compose*), not on a row;
- **tabs** — it hosts the `PageTabs` row beneath the title, so the tab bar is
  part of the sticky frame and survives scrolling.

**Filters do not go in the header.** They belong in the body, directly above the
content they filter. Three reasons: they filter the *content*, not the page, so
the sticky frame is the wrong owner; they compete with the title for the same
row; and they are what forced five of the nine variants into existence
(`flex-col gap-2`, `flex-col md:flex-row`) because filter rows wrap badly at
phone width. `Jobs`, `Internships` and `AlumniDirectory` move their filter rows
down accordingly.

The one exception: a **single** primary scope selector that determines what the
whole page is about — Program Audit's enrollment picker, Partner's organization
switcher — may sit in the header row, because it is closer to the page's identity
than to its content.

### Going back: breadcrumbs locate, actions return

Separate the three mechanisms by what they *mean*, and the "when" answers itself.

**Hierarchy is `Breadcrumbs`, in the header's title slot.** Required on every page
that has a parent — that is, any page you can only sensibly arrive at from
somewhere else (a detail, a form, a submission, a child list). Top-level pages
reachable from the sidebar get a plain title and no crumbs. This is already true
of 40 files; the partner/jobs/internship cluster adopts it and its bare
`ArrowLeft` + destination links are deleted.

**There is no separate "back to parent" control.** The second-to-last crumb *is*
the way back, and it is already a link. Adding a back-link beside a breadcrumb
gives the same destination two controls in one header. This is safe on phones
because frappe-ui's `Breadcrumbs` collapses to the **last two** crumbs behind an
ellipsis dropdown when it overflows, so the parent crumb never disappears —
verified, not assumed.

**Return-to-origin is an action, and lives with the actions.** When a page can be
entered mid-task from a page that expects a result back, it offers a
`Back to <origin>` Button in the header's **actions** slot, on the right,
rendered only when a return context exists. It is not navigation and must not be
styled as a crumb or placed on the left: it completes a task, and the existing
`useActivityReturn` composable (which splices the created activity into the
lesson) is exactly right — it was only ever missing a rule saying so.

So the answer to "when is a back affordance required":

| Situation | Control | Where |
|---|---|---|
| Page has a parent in the hierarchy | `Breadcrumbs` | header, title slot |
| Page is top-level (sidebar-reachable) | plain title, no crumbs | header, title slot |
| Entered mid-task, origin expects a result | `Back to <origin>` Button, conditional | header, actions slot |
| Master→detail *within* one page (no route change) | `Back to list` Button | above the detail panel, in the body |

The fourth row is `CulminatingProject`'s in-place swap; it stays a body control
because no navigation happened and the header's title did not change. Loose body
back-buttons that *do* correspond to a route change — `CourseFeedback`,
`CourseWithdrawalRequest` — become breadcrumbs.

Labels: breadcrumb crumbs are the destination's own name (`Internships`), never
`Back to …`. Only the return-to-origin action uses the `Back to <origin>` wording,
because there the word "back" is doing real work — it says the result goes
somewhere.

### Partner folds back into the standard shell

`PartnerSidebar` is deleted. Partner users get `AppSidebar` with the Partner link
(ADR 074) and the five partner areas become a route-backed `PageTabs` row. The
organization switcher — genuinely a value choice — moves into that row as a
select.

This removes the third copy of the nav rules and the second copy of the portal
switcher, and it stops a partner user losing the primary navigation the moment
they enter the section. `DesktopLayout` no longer branches on route prefix, and
`MobileLayout`'s `/partner` branch goes with it.

### Scope: tiered, not a full sweep

Converted now — the pages where the switcher *is* the primary interaction:
`AlumniHome` (+ Directory/Profile/Organizations), the `/partner/*` set,
`Community`, `CulminatingProject`, `Inbox`, `SelfDevelopmentPlans`,
`CompetencyGradebook`, and `FacultyWorklist` (below).

Left alone: pure filter selects, and the `v-if` stacks whose sections are a
**document read top to bottom** rather than areas switched between —
`CommunicationPreferences` (a settings page), `CourseStatus`, `ProgramAudit` (one
audit, read as a whole). A stack of sections all visible at once is a legitimate
layout when the sections are one continuous answer.

The rule binds all new pages from now on, so the tail converts as it is touched.

### Faculty Worklist is a set of queues, not a document

It was initially left stacked on the reasoning that ADR 074 built it to answer
"what needs me today", and that four visible sections *are* that answer. That
reasoning was wrong about how the page is used. Its sections are not one
continuous answer — they are **separate queues, worked at different times**:
entrance exams this afternoon, project reviews tomorrow. A stack asks the user
to re-find their place in a long scroll every time; it shows everything and
affords nothing.

So it becomes tabs, with **the outstanding count on each tab**. The count is what
preserves the overview — the whole picture stays visible at a glance in the tab
bar, exactly as the badges did — while the panel below gives one queue at a time
to actually work through. Overview and focus stop competing for the same space.

The default tab is **the first with outstanding items**, falling back to the
first tab when everything is clear, so landing on the page lands on work rather
than on an empty queue. `?tab=` still wins when present, so a link into a
specific queue survives.

This distinction — *queues you work* versus *a document you read* — is the test
for any future page, and it is why `ProgramAudit` stays stacked while this does
not.

## Alternatives considered

**`TabButtons` (segmented) as the primitive** — rejected. It reads as a filter or
mode switch rather than as page navigation, and degrades past three or four
options; several of these pages have five.

**Both primitives under a written rule** — rejected *for navigation*, as above: a
rule requiring a per-page judgement call is what failed here already. The toggle
exception is not that rule in disguise; it is scoped by a single decidable test
("would you link to this state?") and explicitly excludes area switching.

**Forcing toggles into tabs for uniformity** — rejected. Making the theme switch
a tab would put a presentation preference in the URL and in the page's navigation
structure, where it does not belong. Uniformity that ignores what a control
*means* is how a codebase ends up with a `<select>` for navigation.

**Leaving Faculty Worklist stacked** — reversed, having first been decided that
way here. The sections are queues worked at different times, not one answer read
in one sitting; tabs with counts keep the overview the badges gave while letting
the user work one queue at a time.

**Putting filters in the page header** (as `Jobs`, `Internships` and
`AlumniDirectory` do today) — rejected. It is what produced five of the nine
header variants, because filter rows wrap badly next to a title at phone width.

**Standardising on the back-link instead of breadcrumbs** — rejected. It is the
minority mechanism (9 uses against 40), it carries no location information beyond
one level, and it would mean deleting working breadcrumbs from 40 files to match
9.

**Keeping a back-link alongside breadcrumbs** for a bigger tap target — rejected.
Two controls for one destination in one header is the ambiguity this ADR exists
to remove, and the overflow behaviour already guarantees the parent crumb stays
reachable on a phone.

**Child routes for every tab** — rejected as the general answer, though it *is*
the route-backed binding where routes already exist. Restructuring every page's
router just to name a panel changes every existing link and redirect for no gain
over `?tab=`.

**Keeping the Partner sidebar swap** — rejected. It is defensible if Partner is
truly a separate audience, but it costs a full shell component per section,
strands the user inside it, and keeps three copies of the nav rules in sync by
hand.

**A full sweep of all ~25 pages** — deferred. It touches pages with no current
defect and produces a diff too large to browser-verify in one pass.

**Writing the rule with no migration** — rejected. The nine mechanisms would
stay live indefinitely, which is the complaint.

## Consequences

**Easier:** one answer to "how do I add a second area to this page", and one
answer to "how do I frame a page". Every converted area becomes linkable — the
Faculty Worklist's deep link into a specific culminating project (ADR 074) stops
being a special case and becomes the normal thing. Reload and Back behave.
Partner users keep their primary nav, the nav rules collapse from three copies to
one, and 68 copied class strings collapse to one component, so the divider stops
changing colour between pages.

**Harder / residual:**

- `PageTabs` is now a chokepoint: a bug or an accessibility regression in it
  reaches every converted page at once. That is the trade being made for
  consistency, and it argues for keeping the wrapper thin over frappe-ui's
  component rather than re-implementing behaviour in it.
- Tab labels enter the translation surface. They are UI strings like any other,
  but they are strings that did not exist before on pages that had a `<select>`.
- `?tab=` and the existing `?project=` / `?cohort=` / `?compose=` params now share
  the query string; the composable must not clobber params it does not own.
- `PageHeader` is a second chokepoint alongside `PageTabs`, and a larger one: it
  reaches ~50 pages. Keep it dumb — a frame with slots, no page logic — or every
  page inherits the next special case someone puts in it.
- Moving filter rows out of three page headers changes those pages' layout
  visibly. It is the right shape, but it is the part of this pass most likely to
  read as "you changed my page" rather than as a fix.
- Adding breadcrumbs to the partner/jobs/internship cluster means **writing the
  crumb trails**, which is per-page work and needs the route hierarchy to make
  sense. Where a page has two plausible parents (a job opening reached from the
  public board or from the partner's own postings), the trail has to be built
  from the route actually taken, not hardcoded — or it will lie about where the
  user came from.
- Breadcrumb labels for record pages need the record's name, which is often not
  loaded when the header first renders. Expect a crumb that fills in late, and
  decide per page whether to show a placeholder or hold the crumb back.
- Toggles remain hand-rolled and therefore still slightly inconsistent with each
  other. That is accepted: there are few, and the alternative is a component
  whose only job is to be a second thing that looks like tabs.
- **Left open — `SidebarLink` is a `<button>`, not a `router-link`.** It calls
  `router.push`, so middle-click and open-in-new-tab do not work anywhere in the
  sidebar. Adjacent to this decision and worth its own fix, but changing it
  touches both shells and is not bundled here.
- **Cleanup owed:** the dead `TabButtons` import in `InstructorProfile.vue` and
  the orphan `activeTab` ref in `stores/settings.js` are the residue of the two
  abandoned attempts; they should go with the first conversion so a future reader
  doesn't mistake them for the sanctioned pattern.
