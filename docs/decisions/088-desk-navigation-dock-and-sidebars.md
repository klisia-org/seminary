# 088 — Desk navigation: dock and sidebars

**Date:** 2026-10-15
**Status:** Accepted 2026-10-15; implemented 2026-10-15 (aa7c4611); §1–§3, §5 and §8 amended by [088a](088a-desk-navigation-setup-first.md)
**Related:** aretenic 069 (the same change in Aretenic, validated first), aretenic 051 (Workspaces stay;
pruning at render time), 020 (workspace translation)

## Context

Seminary's Desk navigation is the retiring Frappe 16 model: one Desktop Icon and three Workspace
Sidebars of 7–8 flat rows. Behind that is one module, Seminary, with about 125 top-level doctypes
and 24 reports, plus the Partner and Alumni modules. Registrars and chairs reach most of them
through four Workspaces and a search box. ERPNext, and now Aretenic (069), show the better
pattern: a rail of areas, each with a sidebar of collapsible sections.

## Decision

1. **One Dock** (`dock/seminary/seminary.json`) replaces the Desktop Icon. It starts with the role
   homes as Workspace pins (Seminary, Registrar, Getting Started), then one entry per area:
   Admissions, Students, Curriculum, Schedule, Teaching, Graduation, Internships, Community and
   Setup.
2. **One Sidebar per area**, titled "Seminary Admissions" and so on, because sidebar names are
   global. They belong to the module that owns most of their doctypes; Partner and Alumni
   doctypes are listed in Internships and Graduation. Each starts with Home, then collapsible
   sections of records, registers and reports. Child tables are never listed.
3. **Areas follow the work, not the role.** Roles reach their areas through permissions: Frappe
   shows an entry only when the user can open something in it. Role-shaped homes stay as
   Workspaces (Registrar), pinned in the dock and gated by the Workspace's roles.
4. **Targets stay inside Seminary** (aretenic 051 §2). No billing doctype appears in a Seminary
   sidebar, because oikonomos (with ERPNext) or tamias (with logistes) may be the active backend,
   or neither.
5. **Billing apps are companions.** oikonomos and tamias each ship a Dock with `mount_on:
   seminary` and their own Sidebar ("Student Billing", "Billing"), so their entry sits on the
   Seminary rail under one title, "Billing". Each sidebar holds that app's whole setup (fees,
   scholarships, payment methods, settings); tamias adds a Ledger section for logistes (QBO
   connection, mappings, drift), which it requires. Setup is not duplicated in Seminary's Setup area.
6. **Only the active backend's entry shows.** A `boot_session` hook marks the inactive app's rail
   entry hidden and adds a "Previous billing" row to the active sidebar, from
   `active_financial_app()`. Nothing is stored (051 §5). This replaces `sync_billing_entry`, which
   toggled Desktop Icons, and `add_previous_billing_links`, which patches a boot key that no longer
   exists and so does nothing today.
7. **Choosing and starting.** The choice stays `Seminary Settings.financial_backend`, in the
   Setup area. A new `FinancialBackend.setup_route()` returns the active backend's first setup
   page, and the Getting Started step "Set up how you get paid" opens it. With no backend it
   explains that billing is optional.
8. **The three Workspace Sidebars and the Desktop Icon are deleted** in the same change, and the
   Workspaces' card groups are brought in line with the sidebars.
9. **Guard.** As in 069: a test fails when a dock entry opens nothing we ship, a sidebar targets a
   missing object or another app, or a top-level doctype or report is in no sidebar.

*Rejected: sidebars by role.* A registrar who is also an instructor would meet two overlapping
trees.

## Consequences

Every doctype is reachable in two clicks, and a school sees one Billing entry whichever ledger it
chose. oikonomos and tamias each need a Dock and Sidebar, and a change in their own repos.
Sidebar labels pass through `_()`, so they must reach Weblate. Open: whether
`workspace_i18n.get_workspace_sidebar_items` (020) is still needed; the boot payload shapes, to
confirm when building; the area split; and Koinonia.
