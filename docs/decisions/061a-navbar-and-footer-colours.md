# 061a — Navbar and footer colours

**Date:** 2026-10-30
**Status:** Accepted 2026-10-30; implemented 2026-10-30
**Amends:** [061](061-public-website-platform-and-branding.md) (colour scheme)

## Context

The public navbar and footer are painted in the Primary colour with white text. Primary is the
school's brand colour, and most logos are drawn in it or for a white background, so a logo placed
in the navbar clashes with the bar or disappears. Schools want their main logo there.

## Decision

1. **Two optional Colour fields** in Website Branding's Colour Scheme: Navbar Background and
   Footer Background. Blank means Primary, so every site looks the same until a school sets one.
2. **Text colour is derived, not entered.** The server compares each bar's background against
   WCAG relative luminance and emits a light or dark ink: white on a dark bar, the school's Text
   colour (or near-black) on a light one. Links, the menu toggle, the login button, hover tints,
   dividers and the social icons follow that ink instead of hard-coded white.
3. **The public site only.** The portal header belongs to the paid Portal Theme (aretenic 068).

## Consequences

A school can put a white navbar over a brand-coloured footer, and no combination makes the menu
unreadable. No migration is needed. The navbar's Apply button keeps the Tertiary colour.
