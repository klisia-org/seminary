# 102 — Accessibility: scope, automated checks and a conformance file

**Date:** 2026-11-22
**Status:** Accepted 2026-11-22; implemented 2026-11-22
**Amended by:** 102a (screen-reader journeys), 102b (themed colours, a sample for every route)
**Delivers:** LMS-ACC-01 (Partial; Yes once the manual review in docs/accessibility/manual.yaml is done)
**Related:** 061a (bar colours from WCAG luminance), 075 (`PageTabs`), 093a (public home page)

## Context

Schools buying an LMS are asked to show WCAG 2.1 AA conformance, usually as an Accessibility
Conformance Report (ACR). Seminary has no statement, no test and no audit. A quick count of the
portal finds few ARIA attributes, no skip link, no live region for toasts, clickable `div`s,
`outline-none` without a focus replacement, titles set on only a few routes, and lesson videos
with no captions. The editors don't warn an instructor about missing alt text. Seminary doesn't
control Frappe Desk, and it doesn't control what schools upload. A report written by hand goes
stale with the first release after it.

## Decision

1. **Scope: what Seminary draws.** In scope: the portal SPA (`frontend/`) for every role, and
   the public pages Seminary renders (`www/`, `templates/pages/`, its web forms). Out of scope,
   and named as such in the report: Frappe Desk and its sign-in page, files and packages schools upload (SCORM,
   PDF, video), and third-party pages (payment gateways, meeting providers).
2. **Target WCAG 2.2 AA.** It contains 2.1 AA, which is what buyers ask for, and costs little
   more: target size, focus not obscured, no drag-only actions, accessible sign-in.
3. **axe-core runs in the test suite.** A test signs in as a student, an instructor and a
   registrar on the test site, visits each route in `docs/accessibility/routes.yaml`, and runs
   axe-core in Chromium with the WCAG A and AA tags. A *serious* or *critical* violation fails
   the test. A new portal route must be added to the file, and a test fails if the router has
   one that isn't.
4. **What a machine can't check is kept by hand.** `docs/accessibility/manual.yaml` has one row
   per criterion axe can't decide (captions, reading order, meaningful link text, keyboard
   traps, reflow at 320 px): the result, remarks, who checked and the date. A row older than
   12 months counts as not checked.
5. **The test writes the conformance file.** `docs/accessibility/conformance.json` lists every
   2.2 A/AA criterion with its result, in the four ACR terms (*Supports*, *Partially Supports*,
   *Does Not Support*, *Not Applicable*), the evidence (axe rules and routes, or the manual row)
   and remarks. It also gives the version, commit, date and scope. A criterion *Supports* only
   when its axe rules pass on every route and any manual row says *Supports*; an unchecked
   manual row makes it *Partially Supports*. The file is regenerated and committed at each
   release to `main`.
6. **Captions.** Course Lesson gets a **Captions** table (language, WebVTT file). The player
   renders each as a `<track>`. A transcript file is optional.
7. **A checker before publishing.** The lesson, page and assignment editors list issues as the
   instructor works and again on publish: an image with no alt text, a skipped heading level,
   an empty or "click here" link, a table with no header row, a video with no captions. It
   warns; it doesn't block.
8. **School colours are checked.** Saving the bar colours (061a) or theme colours whose text
   and background pair falls below 4.5:1 is refused with the ratio shown.
9. **The first pass fixes the portal shell**: a skip link and a `<main>` landmark, a title on
   every route, an `aria-live` region for toasts and errors, keyboard access for clickable
   elements, visible focus, and labels on form controls.

## Consequences

The claim becomes something the tests keep true, not a document someone remembers to update.
The report will show Desk as out of scope, and staff-heavy schools may ask about it. Uploaded
content stays the school's responsibility: the checker helps instructors, but it can't fix a
PDF. axe catches roughly a third of WCAG issues, so the manual rows are real work, and someone
has to redo them each year. The route list adds a step to every new portal page. The colour
check can refuse a colour that a school already uses; the patch reports those colours and
leaves them unchanged.

## Rejected alternatives

- **Include Desk.** Its markup is Frappe's, and fixing it means a fork or upstream work we don't
  schedule. Better to say so plainly in the report.
- **A paid audit instead of tests.** Worth doing once before a large RFP, but on its own it
  describes one release and is stale after the next.
