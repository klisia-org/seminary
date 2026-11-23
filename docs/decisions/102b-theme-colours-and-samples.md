# 102b — Every themed text colour is checked, and the check has a sample for every page

**Date:** 2026-11-23
**Status:** Accepted 2026-11-23; implemented 2026-11-23
**Amends:** 102 §3 (the pages the check visits), §8 (which colours a school's save is checked for)
**Related:** 102a (screen-reader journeys), 061a (bar colours)

## Context

A school's theme sets frappe-ui's text and surface colours, and §8 checks six of the pairs
when it is saved. The muted and faintest text (`--ink-gray-5`, `--ink-gray-4`) aren't among
them, nor the sidebar and soft-fill backgrounds. The page check removes the school's theme
before measuring, so a derived colour at 3.16:1 passed both. The page check also skips every
route whose sample record the test site lacks: 28 of seminary's on testable.

## Decision

1. **The save check covers every themed text colour on every themed background** it is drawn
   on: the six pairs of §8, plus muted and faint text on the page, the cards, the sidebar and
   the soft fill.
2. **The page check also runs with the active theme.** A few pages (the portal shell and a form)
   are checked a second time with the school's theme kept. Their serious violations fail the
   test, so a colour the save check can't see still can't pass.
3. **The test site holds a sample for every route.** `seminary.seminary.accessibility_seed.seed`
   adds the records the routes need: a partner with postings and applicants, a discussion with
   a submission, a quiz submission, a recommendation request. It runs again safely: it finds
   what it made before, and it marks everything it makes, so it can be told apart from real
   data. It sends no email and queues none. An app that uses the check can ship its own seed.

## Consequences

One test site is enough. The seed has to grow with the routes, and a route with no sample is
still listed as not visited, so a gap shows. The themed pass adds a few pages to each run.

## As built

- §1 also covers blue badge and note text on frappe-ui's blue fill, which no theme sets.
- §2: `themed` in routes.yaml lists the pages. The first run found blue badge text below 4.5:1,
  and the theme now keeps it readable.
- §3: the seed tags its rows `a11y-seed` and matches the tag whole, through Tag Link, so another
  app's seed with a longer tag is never mistaken for it. It turns off the school's communication
  triggers and the gradebook update while it inserts. It refuses to keep anything if a message
  table changes; that check caught an internship trigger on the first try. Six routes still
  can't be visited: Desk, three redirects, a developer page and two duplicate edit forms.
- A sample alumnus has an Alumni Profile, which grants the role, so the alumni pages are also
  visited as an alumnus.
- A portal route can be visited as `guest`. The recommender form is: its emailed link carried no
  `/seminary` prefix, so it answered 404, and the portal turned every guest away. The email now
  links to `/seminary/recommender-form/…`, older links redirect with their token, and a guest
  with a token may open that one route. Guest routes render without the portal's navigation.
