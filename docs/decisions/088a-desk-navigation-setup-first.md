# 088a — Desk navigation: setup first, then the offices

**Date:** 2026-10-17
**Status:** Accepted 2026-10-17; implemented 2026-10-17 (bc8055b5)
**Amends:** [088](088-desk-navigation-dock-and-sidebars.md) §1–§3, §5 and §8

## Context

088's nine work areas mix configuration with operations, and they list records that instructors
only touch in the portal (activities, submissions, gradebooks, posts). Getting Started grew into a
long page and lost its billing steps when fees moved to oikonomos and tamias. Frappe and ERPNext
both open with Setup (or Build), so a school configures the system before running it.

## Decision

1. **Rail:** Setup, Registrar, Teaching, Internships, Community and Chapel, then the active billing
   app's Scholarships and Billing (mounted). Workspaces are no longer pinned on the rail. A
   Workspace is listed in one sidebar only, because its route opens the sidebar that lists it:
   the Seminary dashboard is Setup's Home (as ERPNext's Home is in its Setup), Registrar opens its
   Workspace, and the other areas open on their first record. Partner and Alumni are code-only
   modules, so they get no sidebar of their own, and the sidebars Frappe converted from the old
   Workspace Sidebars are deleted.
2. **Setup holds configuration only**, plus Academic Year and Term so they are created before
   anything needs them. It opens with Portal, Home (Seminary) and Seminary Settings, then these
   sections, in setup order: Academic setup, Competency-based education, Community setup, Fees
   setup, People setup, Web and communications, Campus setup, Withdrawal and discipline setup, and
   Integrations.
3. **Registrar, Teaching and Chapel are offices.** Registrar opens with the Registrar Workspace. A
   record may appear in more than one sidebar (Academic Year, Graduation Request, Room
   Utilization). This reverses 088 §3: the overlap is small and each office has a single home.
4. **Companion rows in Setup.** A `seminary_setup_sections` hook lets another app add a section to
   Setup, or rows to one of its sections: the billing apps add "Fees setup", and Aretenic adds its
   portal theme under Web and communications. Seminary merges these at boot, applies the user's
   permissions, and skips a billing app that is not active, so a school sees one Fees setup.
5. **Scholarships is its own entry.** Each billing app ships a Scholarships sidebar beside Billing,
   holding its scholarship records and Seminary's Sources of Funding report. Billing keeps
   operations only; Trigger Fee Events and Fee Trigger are internal and come off it.
6. **Portal-only records leave the Desk.** Activities, submissions, gradebooks, posts and similar
   records stay reachable through search and links, but no sidebar lists them. The guard takes
   an explicit `PORTAL_ONLY` list, so each new doctype is either placed or named there.
7. **Frappe targets are allowed** (User, Website Settings, the Student Applicant web form), since
   every site has them.
8. **Getting Started loses its pin.** Setup's sections replace it as the checklist, and the
   Workspace is deleted once Setup is validated.

## Consequences

Setup is the first thing a new school sees, and it reads in order. Billing setup lives in one
place whichever ledger the school chose. oikonomos, tamias and aretenic each declare the hook.
Sources of Funding is on the rail only when a billing app is installed; without one it is reached
by search.
