# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""One billing entry on the Seminary rail, whichever billing app is active.

oikonomos and tamias are companion apps: each ships a Dock mounted on seminary and a Sidebar
of its own, so both would put a "Billing" entry on the rail. At boot the retired app's entry is
marked hidden, and a "Previous billing" row pointing at its workspace is added to the active
app's sidebars, so its history stays reachable. Nothing is stored (decision 088 §6).
"""

import frappe
from frappe import _

from seminary.seminary.financial.backend import (
    active_financial_app,
    registered_financial_backends,
)

HOST_APP = "seminary"


def billing_sidebars() -> dict[str, list[str]]:
    """{billing app: the Sidebars it ships}, for every installed billing app."""
    apps = list(registered_financial_backends())
    if not apps:
        return {}
    out = {app: [] for app in apps}
    for row in frappe.get_all(
        "Sidebar",
        filters={"app": ("in", apps)},
        fields=["name", "app"],
        order_by="name",
    ):
        out[row.app].append(row.name)
    return out


def billing_workspaces() -> dict[str, list[str]]:
    """{billing app: the public workspaces this user may open}, for every billing app."""
    apps = list(registered_financial_backends())
    if not apps:
        return {}
    modules = frappe.get_all(
        "Module Def", filters={"app_name": ("in", apps)}, fields=["name", "app_name"]
    )
    app_of = {m.name: m.app_name for m in modules}
    out = {app: [] for app in apps}
    if not app_of:
        return out
    for ws in frappe.get_list(
        "Workspace",
        filters={"module": ("in", list(app_of)), "public": 1},
        fields=["name", "module"],
        order_by="sequence_id asc",
    ):
        out[app_of[ws.module]].append(ws.name)
    return out


def _retired(by_app: dict[str, list[str]]) -> list[str]:
    active = active_financial_app()
    return [name for app, names in by_app.items() if app != active for name in names]


def hide_inactive_billing(bootinfo):
    """Hide the retired billing apps' entries on the Seminary rail.

    An entry that no layer names is absent from `bootinfo.dock` and the desk keeps it in its
    app's own order, so a hidden row is added when there is none to flag.
    """
    by_app = billing_sidebars()
    if len(by_app) < 2:
        return
    rail = bootinfo.setdefault("dock", {}).setdefault(HOST_APP, [])
    for name in _retired(by_app):
        row = next(
            (
                r
                for r in rail
                if r.get("link_type") == "Sidebar" and r.get("link_to") == name
            ),
            None,
        )
        if row:
            row["hidden"] = 1
        else:
            rail.append(
                {
                    "link_type": "Sidebar",
                    "link_to": name,
                    "url": None,
                    "icon": "archive",
                    "title": name,
                    "hidden": 1,
                }
            )


def add_previous_billing_links(bootinfo):
    """Link each retired billing app's workspace from the active app's sidebars."""
    by_app = billing_workspaces()
    if len(by_app) < 2:
        return
    active = active_financial_app()
    retired = [ws for app, names in by_app.items() if app != active for ws in names]
    sidebars = bootinfo.get("module_sidebars") or {}
    for name in billing_sidebars().get(active) or []:
        sidebar = sidebars.get(name)
        if not sidebar or not retired:
            continue
        items = sidebar.setdefault("items", [])
        present = {item.get("link_to") for item in items}
        for target in retired:
            if target in present:
                continue
            items.append(
                {
                    "key": f"previous-billing-{target}",
                    "label": _("Previous billing"),
                    "type": "Link",
                    "link_type": "Workspace",
                    "link_to": target,
                    "icon": "archive",
                    "child": 0,
                    "collapsible": 1,
                    "indent": 0,
                    "keep_closed": 0,
                    "show_arrow": 0,
                }
            )


def boot_session(bootinfo):
    hide_inactive_billing(bootinfo)
    add_previous_billing_links(bootinfo)
