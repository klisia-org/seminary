# 020 — Workspace and Dashboard Localization Workaround for Frappe v16

**Date:** 2026-05-19
**Status:** Accepted

## Context

Frappe v16 refactored Workspaces (JSON-content + visual-builder model) and
refreshed the Dashboard / Number Card surface, but shipped without fully
wiring server-side translation. For seminary — Portuguese and Spanish are
first-class, not afterthoughts — that broke localization on the desk for
strings the app itself owns.

Two distinct upstream gaps were validated against the v16 source tree
(`/home/drmrmelo/lms/apps/frappe`):

1. **Workspace serving omits several fields.** `frappe/desk/desktop.py`
   does translate Workspace Link, Card Break, Workspace Shortcut, chart,
   quick-list, number-card, and custom-block labels via `_()` at serve
   time (lines 199, 254, 268, 295, 311, 325, 344). What it does NOT
   translate:
   - `Workspace.title` (sidebar nav, page header, breadcrumbs) — the
     sibling `label` field IS translated at `desktop.py:437`, but the
     frontend reads `title`.
   - The `Workspace.content` JSON blob — the rich-text builder area
     stores blocks (`header`, `paragraph`, `card`, `chart`, `spacer`)
     and is returned to the client unchanged. So embedded HTML in
     headers and the `data.card_name` / `data.chart_name` keys that
     the renderer uses to title each visual card never pass through
     `_()`.

2. **No extractors for Dashboard / Dashboard Chart / Number Card.**
   `frappe/gettext/extractors/` ships extractors for Workspace, DocType,
   Report, Web Form, Custom Field, etc., but nothing for the dashboard
   family. Strings inside those fixture JSONs (`dashboard_name`,
   `chart_name`, Number Card `label`) never make it into `main.pot`, so
   they never reach Crowdin, never compile into `.mo`, and never
   translate on the desk — even though the frontend's client-side
   `__()` calls (e.g. `frappe/public/js/frappe/widgets/base_widget.js:102`)
   are ready to render them.

A smaller issue worth noting: custom **Dashboard Chart Source** Python
files often return hardcoded English data labels. The chart library
does not translate data labels client-side, so these stay in source
language even when the surrounding widget chrome localizes correctly.
Seminary's existing chart source (`students_per_current_courses.py`)
already wraps its dataset name in `_()` and pulls `labels` from the
database (course titles, user data) — so this third gap is not a
concern for seminary today but is documented for future chart sources.

The v15 → v16 transition obviously missed all three; upstream is likely
to patch incrementally. We needed translations to work *now*, without
forking Frappe, with a clean exit path once upstream catches up.

## Decision

Three small pieces, all surgically removable. Pattern is identical to
[frappe_giving's ADR 0006](https://github.com/klisia-org/frappe_giving)
— validated there first against a single workspace + dashboard, then
ported here.

### 1. `seminary/workspace_i18n.py` — server-side post-processor for the workspace endpoints

Two whitelisted wrappers, wired into `hooks.py`:

```python
override_whitelisted_methods = {
    "frappe.desk.desktop.get_desktop_page":
        "seminary.workspace_i18n.get_desktop_page",
    "frappe.desk.desktop.get_workspace_sidebar_items":
        "seminary.workspace_i18n.get_workspace_sidebar_items",
}
```

- `get_desktop_page(page)` defensively re-applies `_()` to label fields
  on `cards / charts / shortcuts / quick_lists / number_cards / custom_blocks`
  items. Most are already translated by upstream — this is belt-and-braces
  in case a regression sneaks through during v16's incremental patches.
- `get_workspace_sidebar_items()` translates each page's `title` and walks
  the `content` JSON. For each block: `header`/`paragraph` → translate
  `data.text`; `card` → translate `data.card_name`; `chart` → translate
  `data.chart_name`. Falls back to leaving content untouched if the JSON
  is malformed (defensive `try/except`).

Both wrappers call `frappe.desk.desktop.X` directly (not via `frappe.call`)
so the override doesn't recurse infinitely.

### 2. `seminary/translatable_strings.py` — POT registration for fixture-only strings

A never-imported module that exists solely to hold `_()` calls for the
strings that live only in fixture JSON:

```python
# Dashboard Chart names
_("Enrolled Students")
_("Students per current course")
_("Students per current courses")

# Number Card labels
_("Active Scholarships")
_("Courses Open for Enrollment")
_("Outstanding Student Balance")
```

(`"Enrolled Students"` doubles as a Number Card label — gettext dedupes
by msgid. `"Seminary"` as `dashboard_name` already matches the Workspace
label and is picked up by Frappe's workspace extractor, so no entry
needed.)

Frappe's `**.py` Babel extractor walks this file like any other, picks
up the calls, and emits them into `main.pot`. From there the strings
flow through the normal Crowdin → PO → MO pipeline and the frontend's
client-side `__()` translates them at render time.

### 3. Chart Source `_()` at the API boundary (pattern, not currently needed)

Seminary's only dashboard chart source today (`students_per_current_courses.py`)
already wraps its dataset name in `_()` and reads `labels` from the
database (course titles), so no labels are hardcoded and no `_translate`
edge function is needed.

For any FUTURE chart source that hardcodes English data labels, follow
the frappe_giving pattern: cache the source-language result, translate
at the response edge so the cache key stays language-agnostic:

```python
def get(...):
    # ... cache lookup / compute ...
    return _translate(result)

def _translate(result):
    return {
        "labels": [_(label) for label in result["labels"]],
        "datasets": [{**ds, "name": _(ds["name"])} for ds in result["datasets"]],
    }
```

## Operational notes

- `bench migrate` does NOT compile `.po` → `.mo`. The compile is a
  separate Frappe v16 command:
  ```
  bench --site <site> compile-po-to-mo --app seminary
  bench --site <site> clear-cache
  ```
  Run after every PO update pulled from Crowdin.
- Frappe Cloud runs `bench build` on deploy, which calls
  `compile_translations` at `frappe/commands/utils.py:109` — so
  production is fine without manual intervention. The manual step is
  local-dev only.
- The compiled MO lives under `<bench>/sites/assets/locale/<lang>/LC_MESSAGES/seminary.mo`
  — outside the app source tree, so it can't accidentally pollute git.

## What needs manual editing as the app grows

This workaround does not auto-discover new fixture strings. Whenever you
add or rename a:

- **Dashboard Chart** (new file under `seminary/dashboard_chart/`)
  → add `_("<chart_name>")` to `translatable_strings.py`.
- **Number Card** (new file under `seminary/number_card/`)
  → add `_("<label>")` to `translatable_strings.py`.
- **Dashboard** with a `dashboard_name` that DOES NOT match an existing
  Workspace label → add `_("<dashboard_name>")` to `translatable_strings.py`.
  (If it matches a Workspace label, the workspace extractor already
  picked it up — see the comment in the file.)
- **Dashboard Chart Source Python** file with hardcoded data labels →
  wrap each label in `_()` at the API boundary (AFTER any cache lookup
  so the cache stays language-agnostic).

A reasonable PR-review checklist item: "added a dashboard/chart/card
fixture → updated `translatable_strings.py`?"

## What to watch upstream to know when to revert

Check `frappe/develop` periodically for any of the following:

- **`frappe/desk/desktop.py`** — if `Workspace.build_workspace`,
  `get_desktop_page`, or `get_workspace_sidebar_items` start translating
  `title` (grep for `_(page["title"])` or `_(self.doc.title)`) and the
  `content` blob (grep for walking the JSON), the workspace_i18n.py
  wrapper becomes unnecessary.
- **`frappe/gettext/extractors/`** — if new files appear named
  `dashboard.py`, `dashboard_chart.py`, or `number_card.py`, the
  fixture-string registration becomes unnecessary.
- **`frappe/babel_extractors.csv`** — if entries appear matching
  `**/dashboard/**/*.json`, `**/dashboard_chart/**/*.json`, or
  `**/number_card/**/*.json`, same as above.

Frappe issue tracker and PR titles worth watching: anything mentioning
"workspace translation", "dashboard i18n", "Number Card label
translatable".

## How to revert (in order)

1. Remove the two entries from `override_whitelisted_methods` in
   `hooks.py` and delete `seminary/workspace_i18n.py`.
2. Delete `seminary/translatable_strings.py`. The registered strings
   fall out of `main.pot` on the next `bench generate-pot-file`;
   stale PO entries can be cleaned via Crowdin's UI ("hide
   untranslated" or purge unused).
3. Keep the chart-source `_()` pattern documented here for any future
   chart source — it's good practice regardless of whether upstream
   wraps anywhere else.

Existing pt.po / es.po translations remain valid through and after
revert — the msgids are the same, only the code path that consumes them
changes.

## Consequences

- All workspace and dashboard strings translate via the standard
  Crowdin → PO → MO pipeline, including the previously-untranslatable
  workspace titles, content HTML, card titles, chart segment labels,
  and Number Card / Dashboard Chart names — in both pt and es.
- The two wrapper functions and the registration module add ~100 lines
  of Python total, all isolated to files that can be deleted in one
  commit.
- `_()` is idempotent: if upstream eventually translates a field we
  already wrap, the double-call is a no-op (translation tables look
  up the source string; the second call sees a target string, finds
  no entry, returns it unchanged). No correctness risk.
- Manual maintenance: every new dashboard fixture needs a manual
  `_()` entry in `translatable_strings.py` until upstream ships
  extractors. PR-review checklist item, not a silent footgun.
- The pattern was validated end-to-end in `frappe_giving` first (single
  workspace, single dashboard, pt locale) before being ported here,
  reducing the risk of surprises with seminary's larger surface
  (3 workspaces, 1 dashboard, 3 charts, 4 number cards, pt + es).
