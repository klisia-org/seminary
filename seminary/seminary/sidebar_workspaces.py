# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Give each workspace one sidebar when a module has several (decision 088a §1).

Frappe hands every sidebar of a module the module's whole workspace list, and the desk opens a
workspace in the first sidebar whose list has it. Seminary has six sidebars in one module, so
`/desk/registrar` opened inside Chapel. At boot a workspace is kept only on the sidebars that
link it; one that no sidebar links stays on the module's fallback sidebar. Nothing is stored.
"""

# The sidebar that keeps a module's workspaces when no sidebar links them.
FALLBACK = {"Seminary": "Seminary Setup"}


def _linked(sidebar) -> set[str]:
    return {
        item.get("link_to")
        for item in sidebar.get("items") or []
        if item.get("type") == "Link" and item.get("link_type") == "Workspace"
    }


def boot_session(bootinfo):
    by_module = {}
    for name, sidebar in (bootinfo.get("module_sidebars") or {}).items():
        by_module.setdefault(sidebar.get("module"), []).append(name)

    sidebars = bootinfo.module_sidebars
    for module, names in by_module.items():
        if len(names) < 2:
            continue
        linked = {name: _linked(sidebars[name]) for name in names}
        fallback = FALLBACK.get(module)
        if fallback not in names:
            fallback = names[0]
        for name in names:
            sidebars[name]["workspaces"] = [
                ws
                for ws in sidebars[name].get("workspaces") or []
                if ws in linked[name]
                or (
                    name == fallback
                    and not any(ws in links for links in linked.values())
                )
            ]
