# Accessibility conformance

Seminary targets WCAG 2.2 Level AA in the portal and the public pages it renders. Decision 102
covers the scope and how it is checked.

| File | Kept by | What it holds |
|---|---|---|
| `routes.yaml` | contributors | every portal route, the role that visits it and the sample record it opens |
| `manual.yaml` | a person | one row per criterion that axe-core can't decide, with what to check |
| `conformance.json` | the test suite | the result, written by `seminary.seminary.tests.test_accessibility` |

The criteria list is `CRITERIA` in `seminary/seminary/accessibility.py`; axe-core's own
tags map its rules to criteria. The browser side is `scripts/axe/check.mjs`, whose
packages (`puppeteer-core`, `axe-core`) install into `scripts/axe` on the first run,
never with the app.

Regenerate the report on a test site before each release to `main`:

```
SEMINARY_WRITE_CONFORMANCE=1 bench --site testable.localhost run-tests \
  --module seminary.seminary.tests.test_accessibility
```

The bench must be serving the site. The test signs in as people it finds on the site
(see `routes.yaml`) through sessions it removes afterwards, switches the public website
on for the run if it is off, and leaves a school's portal theme out of the measurement:
themes are checked when they are saved.

## `conformance.json`

```json
{
  "format": 1,
  "product": "Seminary",
  "version": "1.4.0",
  "commit": "0c6f6ade…",
  "date": "2026-11-22",
  "standard": "WCAG 2.2 Level AA",
  "scope": "The student, instructor and staff portal and the public website pages Seminary renders.",
  "out_of_scope": "Frappe Desk and its sign-in page; files and packages schools upload (SCORM, PDF, video) and the content instructors write; third-party pages such as payment gateways and meeting providers.",
  "evaluation_methods": "axe-core 4.13.0 in Chromium on 72 pages, signed in as a student, an instructor and a registrar, and signed out on the public pages; manual review of the criteria axe-core can't decide.",
  "not_visited": [{"route": "/mock", "why": "A developer page that isn't linked from the portal."}],
  "criteria": [
    {
      "id": "1.1.1",
      "name": "Non-text Content",
      "level": "A",
      "since": "2.0",
      "result": "Supports",
      "remarks": "",
      "evidence": "axe: image-alt, input-image-alt, svg-img-alt on 31 routes; manual: checked 2026-11-22"
    }
  ]
}
```

- `result` is one of `Supports`, `Partially Supports`, `Does Not Support`, `Not Applicable`.
- `level` is `A` or `AA`; `since` is the WCAG version that added the criterion (`2.0`, `2.1`,
  `2.2`). 4.1.1 Parsing is left out, as WCAG 2.2 removed it.
- A criterion supports only when its axe rules pass on every route and its manual row, if it has
  one, says so. A manual row older than 12 months, or missing, makes it `Partially Supports`.
