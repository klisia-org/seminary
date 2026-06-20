# 061 — Public website platform and branding

**Date:** 2026-06-19
**Status:** Implemented 2026-06-19 (Phases A & B)

## Context

The seminary needs a coherent, **unregistered-visitor-facing** marketing site — distinct from the
authenticated Vue SPAs ([ADR 011](011-multi-portal-frontend-cohesion-and-alumni-module.md)). The
intended scope is: **Home**, **Our Program(s)** (info-card list → **Program Detail** with an *Apply*
CTA on a dynamic route), **Who We Are / Our Team** (Academic Units ordered by `web_order`), **Our
History**, **What We Believe** (the Doctrinal Statement), **Contact**, and **Privacy**. Over time
seminaries (and we) will want to extend it — newsletter, blog, etc.

We prototyped pages in **both** Frappe Builder (pages stored as DB rows) and Frappe's **native
Website + Website Generator** (Jinja templates shipped in the app). Both render fine. The friction is
structural: **the navbar/header is independent between Builder and the native website.** Builder's
navbar templates are pleasant to edit, but a site that spans both platforms means maintaining two
separate chromes and copying the navbar back and forth — clanky and error-prone. We want the whole
public surface on **one** platform, with an easy path for a seminary to set its colour/font scheme,
without painting ourselves out of future capabilities.

Today, native Website Generator is already the working pattern: the **Program** doctype
(`program/program.py`) subclasses `WebsiteGenerator` (`has_web_view`, `is_published_field`,
`route`, `get_context`) with a Jinja template, and the apply route resolves through
`get_application_web_form_route()` (`seminary/api.py`). Builder is **not** integrated in the app at
all (it is not in `required_apps`; there is zero Builder code). The only Builder residue is a
defensive `head_html is None` guard in `update_website_context` (`seminary/overrides.py`).

## Decision

**Adopt Frappe's native Website + Website Generator (Jinja) as the single platform for the entire
unregistered-visitor surface. Do not use Frappe Builder for app-shipped public pages.**

Why native wins for *this* scope:

1. **One navbar/footer, one source of truth.** A single app `base_template` plus the **Website
   Settings** top-bar/footer drives every public page. The navbar independence between Builder and
   the website is precisely the clankiness we are resolving — choosing one platform removes it.
   Builder's navbar stays usable for any standalone Builder pages, but it is no longer the public
   site's chrome.
2. **The content is data-bound and dynamically routed.** Programs (cards → detail) and Team (units →
   detail) are *generated from doctypes*, not hand-drawn. Builder targets bespoke static layouts and
   cannot cleanly list/route over `Program` / `Academic Unit`; the Program generator already proves
   the native pattern.
3. **Git-versioned and reviewable.** Templates ship in the app and pass through PR review and
   `migrate`. Builder pages are DB rows: no git history, sync/clobber risk — the same hazard noted
   for fixturing user-configurable doctypes.
4. **Theming a seminary can own.** A small branding singleton emits CSS custom properties into the
   base template, so a seminary sets colours/fonts in Desk without touching code, and the *same*
   tokens feed the navbar and every page. This follows the CSS-variable / semantic-token philosophy
   of [ADR 003](003-dark-mode-and-visual%20standardization.md) rather than a separate SCSS theme.
5. **Extensible without a second platform.** Frappe-native **Blog Post**, **Web Page**, and
   **Newsletter** plug into the same navbar + theme when we want them later.

### 1. Authoring model — hybrid

- **Dynamic / structural pages** are git-versioned app `www/` Jinja templates or WebsiteGenerator
  views, controlled by developers: Home, Our Program(s) list, Program Detail, Our Team (list + unit
  detail).
- **Doctype-backed pages render live from data**: What We Believe ← Doctrinal Statement (`ds_web`);
  Programs ← Program; Team ← Academic Unit.
- **Freeform prose** is authored by staff in Desk as Frappe **Web Page** documents: Our History,
  Privacy, and the Contact copy. These are editable without a deploy yet still served under the same
  navbar and theme.

### 2. Branding — `Website Branding` single doctype

A new **`Website Branding`** singleton emits `--brand-*` CSS custom properties into the website
`base_template` via `update_website_context`. No SCSS compile.

- Colours follow brand-manual convention: `primary_color`, `secondary_color`, `tertiary_color`,
  `accent_color`, plus a `background_color` / `text_color` surface↔ink pair (mirroring Frappe Website
  Theme's background/text and the semantic-token pairing of ADR 003). All are Frappe `Color` fields.
- Typography: `heading_font`, `body_font` — chosen from a small **self-hosted** curated set (no
  runtime Google-Fonts CDN call); plus `favicon`. Light-only.
- **`website_logo` moves here** (it is a public-site concern). **Seminary Settings keeps
  `logo_portal` / `logo_dark`** (portal-owned). A migration patch copies the existing `website_logo`
  value across.

### 3. Programs — singular/plural labels

Some seminaries publish only **one** program. The nav label and page heading are computed from the
published-program **count** in Jinja (1 → "Our Program", >1 → "Our Programs"), with an optional
override field on `Website Branding` for a seminary that wants custom wording.

### 4. Our Team — `web_order` and public-roster suppression

- Add **`web_order` (Int)** to `Academic Unit` and give it a web view (mirroring Program:
  `has_web_view`, `route`, `get_context`) whose roster is resolved transitively via the existing
  `faculty.get_unit_roster()` ([ADR 059](059-seminary-departments-and-faculty-capabilities.md)).
  `www/our-team` lists `publish_on_web=1` units ordered by `web_order`: `web_order == 0` renders the
  unit **inline** on the page; `> 0` renders a **card linking** to the unit's detail route.
- Add **`block_from_web` (Check, default 0)** to **Person**. Some staff work in restricted countries
  and must not appear on public rosters; `get_unit_roster()` (and any public person rendering)
  filters them out.

### 5. Extensibility — design-for-later

Blog and newsletter are **not** built now. They map onto Frappe's native Blog Post / Newsletter on
the same navbar + theme when wanted, so no second platform is needed to add them.

## Consequences

**Easier**
- A single navbar/footer/theme across the whole public site; no cross-platform copying.
- Programs and Team pages stay in sync with their doctypes automatically.
- Seminaries self-serve colour/font/logo in Desk; the public site rebrands without code.
- Public pages are reviewed and versioned like the rest of the app.

**Harder / cost**
- Freeform-prose edits go through Web Page docs in Desk, not a WYSIWYG canvas — less visually rich
  than Builder for one-off landing layouts.
- Developers own structural page layout (a Jinja edit + deploy), which is the deliberate trade for
  reviewability.

**Unchanged**
- The apply flow: Program detail keeps using `get_application_web_form_route()` and the anonymous
  `student-applicant` Web Form.
- Authenticated portals (the Vue SPAs) are untouched.
- The `head_html is None` guard stays (Builder pages, if any are created standalone, still initialise
  it that way).

**New surface**
- `Website Branding` doctype + base template; `web_order` on Academic Unit and its web view;
  `block_from_web` on Person; seeded Website Settings navbar/footer and starter Web Page rows
  (seeded via install hook, **not** fixtured, to avoid clobbering desk edits on migrate).

**Migration**
- One patch copies `Seminary Settings.website_logo` → `Website Branding.website_logo`.

## Alternatives considered

- **Frappe Builder for the public site.** Rejected: independent navbar from the native website (the
  core pain), DB-stored pages outside git, and potential maintenance headache.
- **All pages as Web Page docs (CMS-only).** Rejected: pushes structural/dynamic layout into the DB,
  loses review/versioning, and still can't data-bind the Program/Team catalogs.
- **All pages as dev-only Jinja (no Web Page docs).** Rejected: forces a developer + deploy for
  every prose tweak (History, Privacy, Contact copy) a seminary should own.
- **Frappe Website Theme doctype (SCSS) for branding.** Rejected in favour of a CSS-variable branding
  singleton, which is lighter, needs no SCSS compile, and matches ADR 003.

## Open questions

- Contact page mechanism: a simple Web Form submission vs. a `mailto:`/displayed address only.
- Whether `secondary`/`tertiary` brand colours need explicit semantic roles in the base template or
  are exposed purely as raw `--brand-*` variables for templates to use.
- Timing for blog/newsletter (design-for-later — revisit when content-marketing need is concrete).
