# Translations: how the pipeline works, and its quirks

Maintainer notes for the UI translations of the six apps on
[translate.seminaryerp.org](https://translate.seminaryerp.org): seminary,
oikonomos, aretenic, koinonia, tamias and klisia. Not published on the docs site. The
platform decision is [ADR 073](decisions/073-weblate-replaces-crowdin.md); the
Frappe v16 workspace gaps are [ADR 020](decisions/020-workspace-and-dashboard-localization-workaround.md).

## How a string gets translated

1. A developer adds `_("…")` (Python, Jinja) or `__("…")` (JS, Vue) and
   regenerates the template: `bench generate-pot-file --app <app>`, then
   commits `<app>/locale/main.pot`. **Nothing regenerates it automatically.**
   The `stabilize-pot` pre-commit hook throws away a regenerated POT whose
   msgids did not change, so timestamp-only rewrites never reach Weblate.
2. The push to the default branch fires a webhook. Weblate pulls, and its
   **msgmerge** add-on adds the new strings to every `<lang>.po`.
3. Two site-wide **automatic translation** add-ons run on every update and
   daily: one fills strings from other components' translations (≥ 80 %
   match, saved as translated); the other asks Anthropic (Claude) and saves
   **suggestions only**, which a translator accepts or edits.
4. Weblate commits to the `weblate-translations` branch and opens a PR.
   Merge it; nothing reaches the default branch unattended.
5. `bench build` compiles `.po` to `.mo` on deploy. Locally:
   `bench --site <site> compile-po-to-mo --app <app>` then `clear-cache`.

| App | Weblate project / component | Tracks |
|---|---|---|
| seminary, oikonomos | `klisia` (public) | `main` |
| aretenic, koinonia | `aretenic` (private; status widgets public) | `main` |
| tamias | `aretenic` | `develop` |
| klisia | `klisia-app` (private; status widgets public) | `develop` |

## Writing strings that extract correctly

Frappe extracts with Babel, which takes **the first string literal inside the
call** as the message. Every rule below follows from that.

- **No literal inside `_()` except the message.** `_(page["title"])` extracts
  `title` and never the real titles. Pass a variable:
  `title = page["title"]; _(title)`.
- **Never translate a key or identifier.** `key: __('question_detail')`
  breaks `column.key == 'question_detail'` in every translated language.
- **No concatenation or template literals in `__()`.** The runtime string
  never matches a msgid. Use placeholders:
  `__('{0} of {1}').format(a, b)` (JS), `_("{0} of {1}").format(a, b)` (Python).
- **No escaped quotes in `.vue`.** Frappe's Vue extractor skips
  `__('can\'t')`; write `__("can't")`.
- **Fixture strings Frappe does not extract** (Dashboard Chart, Number Card,
  Dock) are registered in `seminary/translatable_strings.py`.
- **The built bundle is extracted too.** `seminary/public/frontend/assets/*.js`
  is committed, so its strings land in the POT next to the `.vue` source.
  Rebuild the frontend before regenerating the POT, or strings fixed in the
  source keep their old form until the next build.

## Strings that look translatable but are not

Frappe puts **every Select option** in the POT. Where options are codes, mark
them read-only in Weblate rather than changing the field:

- *Reading Plan Step* From/To Book: the 66 OSIS codes (`GEN`, `1CH`…).
  Handled by a **Bulk edit** add-on on the seminary component (query
  `note:"Option for the 'From Book' (Select) field in DocType 'Reading Plan Step'"`,
  adds `read-only`). Read-only strings leave the to-do queue, get no
  suggestions and count as done.

For a new code-valued Select, add a Bulk edit add-on the same way. Snake-case
options that are shown to users (`term_start`, `linear_multiplier`) should be
translated: Frappe displays the translated label and stores the raw value.

## Adding a language

**Weblate** (admin)

- [ ] Add the language to every component in both projects. Each opens a PR
  with the new `<lang>.po`; merge them.
- [ ] Add the code to the Anthropic engine's *Language-specific instructions*
  (dialect and register, as for `es` and `pt`).

**Each site** (Desk)

- [ ] Enable the *Language* record. The portal's language pickers read the
  enabled languages; there is no list in code.
- [ ] *Bible API Settings → Language Defaults*: add a row for the language.
  Without one, Bible passages use the fallback Bible ID.
- [ ] *Communication Template*: add a version in the language for each system
  message. These are seeded in English only and are data, not `.po`.

**Code**

- [ ] `seminary/seminary/integrations/bible_books.py`: add the language's book
  names and abbreviations (today EN, PT and ES), adding only those that differ
  from an existing alias once accents are stripped. `test_bible_books.py` fails
  if an alias lands on another book; bare `jo` stays out because PT `Jó` and
  `Jo` collide.
- [ ] Docs site: add a locale block to `docs/.vitepress/config.mjs`, the pages
  under `docs/en/<lang>/`, and `docs/en/<lang>/_i18n/diagram-labels.json`
  (the lifecycle diagrams fall back to English without it). Update the language
  list in `docs/en/getting-started/translations.md` and its copies.

**Known gaps** (affect every non-English language, not just a new one; the
plan is aretenic decision 071)

- The koinonia and aretenic frontends and the shared portal shell have no
  translation plugin: `__` is a pass-through, so their portal UI is English.
- `frontend/src/utils/dayjs.js` loads no locale, so `fromNow()` is English;
  `formatTime` is fixed to `en-US` and `formatNumber` to `en-IN`
  (`frontend/src/utils/index.js`).
- `strftime("%B")` month names are English (oikonomos invoicing, tamias
  billing automation, aretenic partner reviews).

## Adding an app

1. Generate the POT, seed empty catalogs and add the hook:
   `bench generate-pot-file --app <app>`, create `<app>/locale/<lang>.po` for
   each language, and copy `scripts/stabilize-pot.py` plus its block in
   `.pre-commit-config.yaml`. Run `pre-commit install` in the clone.
2. In Weblate, create the component (copy seminary's settings: gettext,
   `<app>/locale/*.po`, new base `<app>/locale/main.pot`, push branch
   `weblate-translations`) and install the msgmerge add-on.
3. Add a GitHub push webhook to `https://translate.seminaryerp.org/hooks/github/`
   (content type JSON). Without it Weblate never hears about merges.
4. Add the status widget to the README (see this repo's README).
