# Frappe workarounds registry

Patches and overrides this app carries **only because of an upstream Frappe
bug or gap**. Each is removable once Frappe fixes the underlying issue — this
file is the checklist to run that down.

> This is **not** for our intentional domain overrides (e.g.
> `SeminaryPaymentRequest`, the `Seminary Settings` / `Salary Slip` hooks,
> `Question` helper methods). Those are permanent by design and are out of
> scope here. Only entries that should *disappear when Frappe improves* belong
> in this table.

**After every `bench update`:** run the *Verify* command for each entry. If it
no longer matches (the upstream code changed), do the functional check, and if
the bug is gone, follow *Remove* and delete the entry from this table.

Last verified against **frappe `version-16` @ 16.18.2** (commit `e61c3950fa`).

| # | Workaround (ours) | Frappe target | Wired via | Upstream issue |
|---|---|---|---|---|
| 1 | `seminary/public/js/masked_fields_report_guard.js` | `query_report.js` `update_masked_fields_in_columns` | `app_include_js` | [frappe#39813](https://github.com/frappe/frappe/issues/39813) |
| 2 | `seminary/workspace_save_fix.py` | `workspace.py` `save_page` | `override_whitelisted_methods` | _(link)_ |
| 3 | `seminary/workspace_i18n.py` | `frappe.desk.desktop` translation pass | `override_whitelisted_methods` | ADR 020 _(link)_ |
| 4 | `seminary/seminary/overrides/web_form.py` `SeminaryWebForm` | `web_form.py` `add_custom_context_and_script` | `override_doctype_class` | _(link)_ |

---

## 1 — Query Report `masked_fields` crash guard

**Upstream:** [frappe/frappe#39813](https://github.com/frappe/frappe/issues/39813) (introduced by #32684).

**Bug.** `QueryReport.update_masked_fields_in_columns` reads
`frappe.get_meta(ref_doctype).masked_fields` and calls `.includes()` on it
**without** the `|| []` guard every sibling call site uses (`layout.js:252`,
`list_view.js:976`, `form.js:1214`, `formatters.js:423`). The lightweight
client meta does not carry `masked_fields` (only the full FormMeta does), so it
is `undefined` and the report blanks with *"Cannot read properties of undefined
(reading 'includes')"*. Hits every Script Report with a `ref_doctype`;
intermittent (depends on whether that doctype's full meta was loaded). See
`project_frappe_quirks.md`.

**Verify still needed:**
```bash
grep -n "masked_fields" apps/frappe/frappe/public/js/frappe/views/reports/query_report.js
```
Needed while the `update_masked_fields_in_columns` line reads
`...).masked_fields;` with no `|| []`. Functional check: in a fresh session
(don't open the ref doctype's form first), open **Courses to Offer** — if it
renders, the bug is fixed.

**Remove:** delete the file, drop its `app_include_js` entry in `hooks.py`,
`bench build --app seminary`.

## 2 — Workspace `save_page` AND/OR guard

**Bug.** `save_page` guards with
`if not (is_workspace_manager() and doc.for_user == frappe.session.user): return`.
For a **public** workspace `for_user` is empty, so the AND is always false and
the guard always returns — the save is a silent no-op, the desk editor hangs,
and edits vanish on reload. Intent is OR. Our copy fixes the operator.

**Verify still needed:**
```bash
grep -n "is_workspace_manager() and doc.for_user" apps/frappe/frappe/desk/doctype/workspace/workspace.py
```
Needed while that `... and doc.for_user ...` line exists in `save_page`.
Functional check: as a Workspace Manager, edit a **public** workspace and save —
if it persists across reload, fixed.

**Remove:** drop the `frappe.desk.doctype.workspace.workspace.save_page` entry
from `override_whitelisted_methods` in `hooks.py`; delete `workspace_save_fix.py`.

## 3 — Workspace i18n (title + content blob)

**Gap.** Frappe v16's workspace refactor omits a few user-facing strings from
the server-side translation pass in `frappe.desk.desktop`: `Workspace.title`
(sibling `label` is translated, `title` is not) and the `content` JSON
(`header`/`paragraph` text, `card`/`chart` block IDs). Our wrappers translate
them. `_()` is idempotent, so the wrapper is harmless once upstream translates
these. Full rationale in **ADR 020**.

**Verify still needed:** there is no single line to grep; check whether
`frappe.desk.desktop.get_desktop_page` / `get_workspace_sidebar_items` now pass
`Workspace.title` and the content blob through `_()`. Functional check: set the
desk language to pt/es and confirm a workspace **title** (not just its label)
and card/section headers render translated **without** our override (temporarily
comment the two `override_whitelisted_methods` entries on a scratch site).

**Remove:** drop the two `frappe.desk.desktop.*` entries from
`override_whitelisted_methods` in `hooks.py`; delete `workspace_i18n.py`.

## 4 — Web Form shared scripts for non-standard forms

**Gap.** `WebForm.add_custom_context_and_script` only wires up
`webform_include_js` inside an `if self.is_standard:` branch (`web_form.py:508`),
so custom, desk-built forms never receive shared scripts. We need it so a
seminary's own *Student Applicant* forms render the doctrinal statement etc.
without each author pasting a client script. `SeminaryWebForm` injects the hook
scripts for non-standard forms.

**Verify still needed:**
```bash
grep -n "webform_include_js\|is_standard" apps/frappe/frappe/website/doctype/web_form/web_form.py
```
Needed while the `webform_include_js` loop sits under `if self.is_standard:`.
Functional check: a non-standard Web Form with a matching `webform_include_js`
hook should load that script **without** our override.

**Remove:** drop the `"Web Form"` entry from `override_doctype_class` in
`hooks.py`; delete `overrides/web_form.py` (it holds only this one method).

---

## Adding a new entry

When you patch around a Frappe bug:

1. Put the patch where its kind belongs (`override_*` in `hooks.py`,
   `app_include_js`, etc.) and give the file a docstring stating the bug and
   how to remove it.
2. Add a row + section here, including a concrete **Verify** command.
3. Reference this file from the wire-up comment in `hooks.py`.
4. File the upstream issue and link it.
