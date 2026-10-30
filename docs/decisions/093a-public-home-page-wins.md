# 093a — The public home page wins over role portals

**Date:** 2026-10-30
**Status:** Accepted 2026-10-30; implemented 2026-10-30
**Amends:** [093](093-public-website-switch.md)

## Context

Frappe sends a logged-in user to an app's role home page (Student → `/seminary/courses`, koinonia's
Donor → `/donate/donorportal`) before Website Settings' home page. On a site whose public pages
belong to another app, such as Klisia's, a student or donor who opens `/` never sees them.

## Decision

1. **When Website Settings has a home page, `/` shows it to everyone.** Seminary's
   `get_website_user_home_page` hook returns it, so Frappe never reaches the role maps.
2. **Without one, the role maps apply as before:** a school with no public pages still opens
   each portal at `/`.
3. **Login still lands people in their portal** (seminary's `after_login`), and the navbar's
   Portal link takes them back.

## Consequences

Seminary and koinonia keep their `role_home_page` maps. A Role's own Home Page and Portal
Settings' default still come first, as Frappe orders them. Frappe calls only the last app's
`get_website_user_home_page`, so a site that also installs Builder after seminary gets
Builder's instead.
