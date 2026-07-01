# Public Website

SeminaryERP ships a complete public, **unregistered-visitor** website — your marketing site — generated from the same data you already manage in Desk. Visitors browse your programs, meet your faculty, read what you believe, and apply, all without logging in.

## Overview

The website is **not** a separate site you build and keep in sync. Its pages are generated from your existing records (Programs, Academic Units, the Doctrinal Statement) plus a handful of staff-editable pages. Change a program in Desk and its public page updates automatically.

It is built on Frappe's native website, so every page is server-rendered (fast and search-engine friendly), lives under your own domain, and shares one navigation bar, footer, and color scheme.

The authenticated student/faculty portal and the Desk are completely separate — nothing here affects them.

## The pages

| Page                                | URL                                    | Content comes from                                                                          |
| ----------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------- |
| **Home**                            | `/`                                    | The Home Page Hero on Website Branding                                                      |
| **Our Programs**                    | `/programs`                            | Published Programs, grouped by Program Level                                                |
| **Program detail**                  | `/<program-slug>`                      | The Program record (blurb, description, image, apply CTA)                |
| **Who We Are / Our Team**           | `/our-team`                            | Published Academic Units and their faculty rosters                                          |
| **Unit detail**                     | `/team/<unit-slug>`                    | A single Academic Unit's roster                                                             |
| **What We Believe**                 | `/what-we-believe`                     | The Doctrinal Statement marked for the website                                              |
| **Our History / Privacy / Contact** | `/our-history`, `/privacy`, `/contact` | Editable Web Page documents                                                                 |
| **Apply**                           | the application form                   | The Student Applicant web form (reached from a program's _Apply_ button) |
| **Application received**            | `/applicant-payment`                   | Post-application thank-you + fee payment                                                    |

All of these share your branded navigation bar and footer — including the application form and the thank-you page.

## Branding

Open **Website Branding** (search for it in Desk) to control how the whole public site looks. Changes take effect on the next page load — no developer or deploy needed.

- **Colour Scheme** — Primary, Secondary, Tertiary, Accent, plus a Background and Text colour. Primary drives the navigation bar, links, and headings; Secondary/Tertiary/Accent are used for buttons and call-to-action highlights.
- **Typography** — choose a Heading Font and Body Font from the bundled set. Fonts are self-hosted, so pages load fast and no data is sent to external font services.
- **Website Logo** and **Favicon** — the logo shown in the navigation bar (use a transparent PNG/SVG, ~40px tall) and the browser-tab icon.
- **Social Links** — add a row per account (Facebook, Instagram, X, YouTube, LinkedIn, TikTok, Telegram, WhatsApp, or Email). They appear as icons in the footer.
- **Home Page Hero** — the headline, subtext, background image, and button (label + link) shown at the top of the Home page.
- **Display Options** — an optional override for the programs menu label, and a toggle to show salutations (Dr, Prof, Rev…) on the team roster.

**Note:** a dark logo on a dark Primary colour can be hard to see in the navigation bar. Pick a logo that reads well on your chosen Primary colour.

## Navigation and footer

The menu and footer are configured in **Website Settings** (the same place Frappe keeps site-wide website options):

- **Top Bar Items** — the navigation links. For a simple link, fill in the Label and URL. To group footer links into a titled column, add a parent row (Label only) and child rows whose **Parent Label** matches it.
- **Footer Items** — footer links, grouped or flat the same way.
- **Address** and **Copyright** — shown at the bottom of every page.
- **Home Page** — set to `home` so that `/` shows your marketing Home page.

The navigation bar and footer templates are pre-selected for you (Seminary Navbar / Seminary Footer); you normally don't need to touch them.

## Publishing content

Nothing is public until you publish it. Each kind of content has its own switch:

| To publish…                                        | Set…                   | On…                                                         |
| -------------------------------------------------- | ---------------------- | ----------------------------------------------------------- |
| A program (and its detail page) | **Published**          | the Program                                                 |
| An academic unit on Our Team                       | **Publish on Web**     | the Academic Unit                                           |
| Your doctrinal statement                           | **Use in the website** | the Doctrinal Statement (then submit it) |
| A prose page                                       | **Published**          | the Web Page                                                |

There is no single global on/off switch: to take the whole site down you would unpublish the content and point the Home Page elsewhere.

## Our Programs

Published programs are shown as cards, **grouped by Program Level** (for example _Master's_, _Bachelor's_, _Certificate_). Control the order the level sections appear by setting **Web Order** on each Program Level (lowest first). Within a level, programs follow their existing _Order in Programs and Degrees_.

The page heading is automatic: with one published program it reads _Our Program_, with several it reads _Our Programs_. Override it with **Programs Menu Label Override** on Website Branding if you prefer different wording.

Each card links to the program's detail page, which shows the blurb, description, requirements, enrollment windows, and an **Apply** button. See [Programs](program.md) for how to configure those fields and the application flow.

## Our Team

The Our Team page lists every Academic Unit marked **Publish on Web**. Each unit's **Web Order** decides how it appears:

- **Web Order = 0** — the unit's roster is shown **inline** on the page. Inline units appear first (good for a leadership group).
- **Web Order greater than 0** — the unit shows as a **card** that links to its own page, in the order you set.

### Faculty cards

Each member is shown with a photo, name, role, and a short bio. The information is pulled from the person's records:

- **Photo** — the Instructor's profile image, or the Person's image.
- **Role** — the person's **Position / Title** if set (for example _Board Member_, _President_); otherwise it is derived automatically (Chair, then their capability, then _Faculty_ or _Member_). Setting a Position is the way to label non-instructors such as board members.
- **Short bio** — the person's **Public Mini-Bio**; for instructors, the Instructor's shorter bio is used when that is blank.
- **Salutation** — shown before the name when _Show Salutations on Team Roster_ is on.

### Ordering members within a unit

To place people in a deliberate order (President, Vice-President, …), set **Web Order** on each **Academic Unit Membership** row (1 first, 2 next, and so on). Members left at 0 fall back to chair-first, then alphabetical, below the ordered ones.

### Hiding someone

Tick **Block from Public Website** on a Person to keep them off public rosters (useful for staff in security-sensitive or restricted-access contexts). It does not affect their Desk or portal access.

See [Academic Units & Faculty](academic-units.md) for how units and memberships are set up.

**Note:** faculty photos must be **public** images so visitors (who aren't logged in) can load them. A private attachment will not display on the public site.

## What We Believe

This page renders the **Doctrinal Statement** that has **Use in the website** ticked and is submitted. If more than one qualifies, the active one is shown, then the most recently updated. Edit the statement in Desk and the page updates.

## History, Privacy, and Contact

These are ordinary **Web Page** documents, seeded with starter text the first time the app runs. Edit them in Desk under _Website → Web Page_ — no developer needed. Use them for your story, your privacy policy, and your contact details (add your address, phone, and a `mailto:` email link on the Contact page).

## Search engines and sharing

Because the site is server-rendered, it is fully crawlable, and several SEO basics are handled for you:

- A **sitemap** is generated automatically at `/sitemap.xml`.
- **robots.txt** can be edited in Website Settings.
- Every page sets its **title**, a **meta description**, and **Open Graph / Twitter card** tags so links shared on social media show a proper title, description, and image (drawn from the page's hero or program image).

For page-specific tweaks without code, you can add a **Website Route Meta** record for any route to override its tags.
