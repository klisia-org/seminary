# 093 — Turning the seminary's public pages off

**Date:** 2026-10-28
**Status:** Accepted 2026-10-28; implemented 2026-10-28 (20139261)
**Related:** 061 (public website platform and branding)

## Context

061 gives every site a public website: a home page, Programs, Our Team, What We Believe, and web
pages for each published Program and Academic Unit. On install it also sets the site's home page and
fills the top bar and footer with links to those pages. Some schools keep their website elsewhere
and want only the portal. Other apps installed with seminary, such as a publisher's, build their own
public site on the same Frappe site, and the seminary's pages then compete with theirs.

## Decision

1. **A *Public Website* switch in Seminary Settings,** on by default.
2. **When it is off, the seminary's public pages are gone:** home, Programs, Our Team, What We
   Believe, and the Program and Academic Unit web pages all return 404. Program and Academic Unit
   keep their published flags, so turning the switch back on restores the pages unchanged.
3. **Branding stays.** Website Branding's logo, favicon, colours and fonts, and the navbar and footer
   templates, keep serving every public page, whichever app owns it. Its fields that only the
   seminary's pages use (the hero, the programs label, team salutations) are hidden while the switch
   is off.
4. **Turning it off tidies Website Settings.** Seminary clears the home page if it is still `home`,
   and removes the top-bar and footer links it added that are still unchanged. It also unpublishes
   the starter Our History, Privacy and Contact web pages while their text is still the seeded
   placeholder. Anything staff changed is left alone. Turning it on again seeds only what is empty,
   as install does, and republishes those placeholders.
5. **The portal is untouched:** `/seminary`, sign-in, the application form, applicant payment and
   address verification keep working.
6. **The navbar's *Portal* link is a Website Branding field,** `/seminary` by default; when it is
   empty, the link is hidden. Another app's install points it at its own portal.
7. **`/` follows Website Settings' home page,** never a fixed route. An app that owns the site's
   public pages gives its home page its own route name and sets it there. It does not reuse
   `home`: Frappe serves a route from the last app installed, so a second `home` would hide the
   seminary's even with the switch on.

## Consequences

- Existing sites see no change.
- An app that owns the site's public pages turns the switch off in its own install, then sets the
  home page and links it wants.
- The seminary's navbar and footer serve any app's public pages, with no copy of their templates.
- Hiding pages through Website Route Redirects was rejected: they would still be built and reachable
  by their routes, and the redirects would be left for staff to keep.
