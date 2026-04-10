# 003 — Dark Mode & Visual Standardization

**Date:** 2026-04-10
**Status:** Accepted

## Context

The Seminary portal frontend (Vue 3 + Frappe UI + Tailwind) had no theme support. Every component used raw Tailwind color utilities (`bg-white`, `text-gray-900`, `border-gray-200`, occasional `bg-[#f8f8f8]` / `bg-[#E6F4FF]` arbitrary values) that resolve to hard-coded light-mode hex values at build time and do not flip under any theme system. Additionally, visual conventions had drifted: three student-facing tables used Frappe UI's `ListView` with 6–7 columns (requiring heavy horizontal scroll on mobile), while others used plain HTML `<table>` with 4 columns; status badge color mappings were inlined per-file with divergent rules; form control text color was inconsistent depending on which ancestor had set `text-*`. The goal was to ship a low-cost dark mode **and** establish the conventions that prevent this drift from reappearing.

Discovery during Phase 1: the `frappe-ui/tailwind` preset that Seminary already depends on ships with `darkMode: ['selector', '[data-theme="dark"]']` pre-configured and exposes a full palette of semantic tokens — `bg-surface-*`, `text-ink-*`, `border-outline-*`, `ring-outline-*`, `divide-outline-*`, `fill-ink-*`, `stroke-ink-*`, `placeholder-ink-*` — each backed by CSS variables that the preset defines at `:root` (light values) and `[data-theme="dark"]` (dark values). The frappe/lms portal uses these tokens exclusively. Seminary had been ignoring the semantic layer and going raw, which is why the initial "just add a dark stylesheet" attempt (a hand-rolled `dark-theme.css` with CSS specificity overrides on common Tailwind classes) fought the Frappe UI system and produced "works mostly but visual issues" results.

## Decision

1. **Dark mode rides on Frappe UI's existing token system.** Seminary flips a single `data-theme="dark"` attribute on `<html>`, which the Frappe UI preset's CSS variables already listen for. No custom `tailwind.config.js` change, no `dark:` variant sweep, no hand-rolled override stylesheet. Any element using a semantic token flips automatically; any element using raw Tailwind colors stays light — which is the migration signal.

2. **Persistence is `localStorage` only.** The `useTheme` composable at [frontend/src/composables/useTheme.js](../../frontend/src/composables/useTheme.js) resolves the initial theme (stored value → `prefers-color-scheme` fallback), writes `data-theme` on `<html>` **synchronously at module load** before Vue mounts (prevents flash of wrong theme), and exposes a shared reactive `theme` ref plus `setTheme` / `toggleTheme`. Rejected: persisting to the Frappe User doctype, because it would require a backend roundtrip, risk flash-of-wrong-theme on reload, and provide cross-device sync value we did not need.

3. **Two toggle surfaces, one state.**
   - **Desktop**: a persistent sun/moon icon button in [AppSidebar.vue](../../frontend/src/components/AppSidebar.vue), placed above the Collapse button in the bottom section. One click, always visible, follows the VitePress convention where the icon shows the *target* state (moon in light mode = "click to go dark"). Works in both expanded (`w-64`) and collapsed (`w-16`) sidebar states.
   - **Mobile**: Appearance toggle in [ProfileModal.vue](../../frontend/src/components/ProfileModal.vue) alongside the Language selector. Mobile chrome has no room for a persistent header toggle — bottom nav is full and each page owns its own sticky `<header>` (no shared component). ProfileModal is reachable in one tap from the bottom nav.
   - Both surfaces consume the same `useTheme` composable so state stays in sync — clicking the sidebar toggle updates the ProfileModal's selected state instantly.

4. **Semantic token mapping (the canonical table).** Raw Tailwind color utilities are banned from new code. Use the Frappe UI equivalents:

   | Raw (banned) | Semantic (use this) |
   |---|---|
   | `bg-white` | `bg-surface-white` |
   | `bg-gray-50` | `bg-surface-gray-1` |
   | `bg-gray-100` | `bg-surface-gray-2` |
   | `bg-gray-200` | `bg-surface-gray-3` |
   | `text-gray-{4,5,6,7,8,9}` | `text-ink-gray-{4,5,6,7,8,9}` |
   | `border-gray-200` | `border-outline-gray-1` |
   | `border-gray-300` | `border-outline-gray-2` |
   | `hover:border-gray-400` | `hover:border-outline-gray-3` |
   | `bg-blue-50` | `bg-surface-blue-1` |
   | `bg-blue-100` | `bg-surface-blue-2` |
   | `text-blue-600 hover:text-blue-800` (links) | `text-ink-blue-link hover:text-ink-blue-3` |
   | `text-blue-400 hover:text-blue-600` (action icons) | `text-ink-blue-2 hover:text-ink-blue-3` |
   | `bg-green-50 text-green-700` (success states) | `bg-surface-green-1 text-ink-green-3` |
   | Arbitrary hex values (`bg-[#E6F4FF]`, etc.) | Map to the nearest semantic surface/ink token |

   The full list of available semantic token names lives in `node_modules/frappe-ui/tailwind/colors.json` under `themedVariables`.

5. **Layout roots declare the default text color.** Both [DesktopLayout.vue](../../frontend/src/components/DesktopLayout.vue) and [MobileLayout.vue](../../frontend/src/components/MobileLayout.vue) set `bg-surface-white text-ink-gray-9` on their root container. Any descendant element that does not explicitly declare its own text color inherits a theme-aware one. This is the mechanism that makes `<td>` cells, `<p>` paragraphs, and unstyled `<div>` content in unmigrated pages survive a theme flip without per-element annotation.

6. **Form controls need explicit `bg-surface-white text-ink-gray-9`.** Browsers do not reliably inherit `color` into `<input>`, `<select>`, or `<button>` elements, and their default `background-color` is transparent (which reveals browser UA defaults, not the page background). Inputs/selects on a dark page render as white-on-white without explicit classes. **Every new form control must declare both the surface and ink classes explicitly**, regardless of what ancestors declare.

7. **Global body background follows the theme.** [frontend/src/index.css](../../frontend/src/index.css) sets `html, body { background-color: var(--surface-white); }` so any layout that doesn't fill the viewport (e.g. MobileLayout's `h-full` collapsing on short content) shows the theme-aware body instead of the browser's default white.

8. **Tables follow one pattern: plain HTML, four columns, muted subtitles.** Frappe UI's `ListView` is not used in student-facing pages. The canonical pattern is:

   ```vue
   <table class="w-full text-sm">
     <thead>
       <tr class="border-b text-left text-ink-gray-6">
         <th class="py-2 px-3 font-medium">Primary</th>
         <th class="py-2 px-3 font-medium">Secondary</th>
         <th class="py-2 px-3 font-medium">Status</th>
         <th class="py-2 px-3 font-medium text-right">Action</th>
       </tr>
     </thead>
     <tbody>
       <tr class="border-b">
         <td class="py-2 px-3">
           <div class="text-ink-gray-9">{{ primary }}</div>
           <div class="text-xs text-ink-gray-5">{{ subtitle }}</div>
         </td>
         ...
       </tr>
     </tbody>
   </table>
   ```

   Used by ProgramAudit, Enrollment, Grades, and Fees. Rule: **if a table has more than four columns on mobile, collapse secondary info into muted subtitles under the primary cell** rather than adding horizontal scroll.

9. **Status badge colors come from a single helper.** [frontend/src/utils/statusTheme.js](../../frontend/src/utils/statusTheme.js) normalizes the status string (trim + lowercase) and returns a Frappe UI Badge theme. The canonical mapping:

   - **green**: `pass`, `passed`, `completed`, `paid`
   - **blue**: `enrolled`, `in progress`
   - **red**: `fail`, `failed`, `overdue`
   - **orange**: `withdrawn`, `draft`, `pending`, `unpaid`
   - **gray**: anything else (fallback)

   All `<Badge>` usages in status columns must call `statusTheme(row.status)` rather than inlining ternaries. New statuses extend the Sets in that file, nowhere else.

10. **Logos support a dark variant.** Seminary Settings has `logo_portal` (light) and `logo_dark` (dark) fields. [UserDropdown.vue](../../frontend/src/components/UserDropdown.vue) picks the active logo based on the `theme` ref, falling back to `logo_portal` when no dark variant is uploaded. The logo wrapper carries a `.seminary-logo` class and a small unscoped style block disables Frappe UI's global `[data-theme="dark"] img { filter: brightness(.8) contrast(1.2) }` rule for this specific image — schools that upload a dark variant get it rendered at full fidelity, every other image on the page keeps Frappe's softening.

11. **Migration is opportunistic, not a big bang.** The initial rollout converted the highest-traffic screens (DesktopLayout, MobileLayout, AppSidebar, SidebarLink, UserDropdown, Home, Courses, CourseDetail, ProfileModal, CourseCardToDo) and expanded as bugs surfaced (ProgramAudit, Enrollment, Grades, Fees, Gradebook, CourseOutline). Remaining pages are migrated when touched for feature work or when a dark-mode contrast bug is reported against them. No codemod was written — the mapping table above is simple enough for manual replace-all, and each page benefits from the judgment call of whether `bg-gray-50` should map to `surface-gray-1` or `surface-menu-bar` depending on usage context.

## Consequences

- **Adding dark mode support to a new page is now mechanical**: use semantic tokens from the table in Decision 4, declare `bg-surface-white text-ink-gray-9` on any `<input>`/`<select>`, call `statusTheme()` for any Badge, use the table pattern from Decision 8 when rendering tabular data. No theme-specific code paths, no `dark:` variants, no watchers on the `theme` ref.
- **The flash-of-wrong-theme problem is architectural, not cosmetic.** Any future theme-related ref or DOM mutation must happen at module load in `useTheme.js` (synchronous, before Vue mounts) — not inside `onMounted`, not inside App.vue, not inside a route guard. An earlier version of `useTheme.js` created the ref *before* applying the initial theme to the DOM; the ref read back `null` and got stuck at `'light'`, and clicking the Light button became a no-op because `ref.value = 'light'` on top of `'light'` triggered no reactivity. The fix was to resolve + apply + create-ref in that order at the top of the module. Documented here because the bug is subtle and will recur if anyone refactors the composable without understanding the ordering requirement.
- **Raw Tailwind color classes in untouched pages are not a bug, they are a backlog.** Anything in `frontend/src/pages/` or `frontend/src/components/` that hasn't been touched since 2026-04 may still use `bg-white` and friends. Do not treat these as regressions; convert them when you touch the file or when a user reports a contrast issue.
- **The `statusTheme` helper is the single source of truth for Badge color semantics.** Inline theme ternaries in Badges (`:theme="s === 'Paid' ? 'green' : 'red'"`) are a code smell and should be converted on sight. New domain statuses get added to the Sets in [statusTheme.js](../../frontend/src/utils/statusTheme.js), nowhere else.
- **Mobile tables are capped at 4 columns.** Any new feature that wants to show a tabular view on a page students use must either fit in 4 columns or collapse secondary info into muted subtitles. The ListView component is still appropriate for instructor/admin desktop-only views where horizontal real estate is abundant.
- **Logo uploads to Seminary Settings are now a two-variant workflow.** School admins who care about branding upload both `logo_portal` and `logo_dark`. Schools that upload only one get graceful fallback (light variant used for both themes), so the feature degrades safely.
- **Opted out of `darkMode: 'class'` Tailwind variants.** Tailwind's `dark:bg-gray-900`-style variants do work alongside Frappe UI's preset, but using them would create a second parallel theming system with its own rules for which class wins. We chose to stay inside Frappe UI's semantic tokens as the single source of truth. If a future need arises that semantic tokens cannot express (e.g. a very specific hover state palette), prefer adding a new semantic token via a scoped CSS variable over introducing `dark:` variants.
- **Deferred:** a `PageHeader` component that de-duplicates the sticky `<header>` pattern currently copy-pasted across ~8 student-facing pages. Each page's header is nearly identical (`sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5`), and a shared component would also provide a clean slot for page-specific secondary actions. Not scoped in this ADR to avoid bundling refactoring with the theming work; tracked for a future decision.
- **Deferred:** a codemod to convert the remaining ~28 unmigrated files in one pass. Not written because the manual mapping has been fast in practice and mechanical replacement risks mis-mapping intentional color choices (e.g. a `bg-green-50` that's a success badge vs. one that's a decorative surface). Revisit if the volume of bug reports against unmigrated pages grows.
- **Unaddressed:** right-to-left language support, which would interact with the sidebar icon placement and the table subtitle pattern. No RTL locales are currently enabled in Seminary; revisit when one is added.
