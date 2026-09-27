# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""One billing entry on Desk, whichever billing app is active.

Each billing app ships its own workspace and desktop icon. When two are
installed, only the active app's icon shows; the retired app's workspace stays
open for its history, reached from a "Previous billing" link in the active
app's sidebar (aretenic decision 051 §4).
"""

import frappe
from frappe import _

from seminary.seminary.financial.backend import (
    active_financial_app,
    registered_financial_backends,
)


def billing_workspaces() -> dict[str, list[str]]:
    """{billing app: its public workspaces}, for every installed billing app."""
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
    for ws in frappe.get_all(
        "Workspace",
        filters={"module": ("in", list(app_of)), "public": 1},
        fields=["name", "module"],
        order_by="sequence_id asc",
    ):
        out[app_of[ws.module]].append(ws.name)
    return out


def sync_billing_entry():
    """Show the active billing app's desktop icons and hide the others'.

    Runs when Seminary Settings is saved and on every migrate, so a new billing
    app, or a change of active app, settles without anyone touching Desk.
    """
    active = active_financial_app()
    changed = False
    for app, workspaces in billing_workspaces().items():
        if not workspaces:
            continue
        hidden = 0 if app == active else 1
        for icon in frappe.get_all(
            "Desktop Icon",
            filters={
                "link_type": "Workspace Sidebar",
                "link_to": ("in", workspaces),
                "hidden": ("!=", hidden),
            },
            pluck="name",
        ):
            frappe.db.set_value(
                "Desktop Icon", icon, "hidden", hidden, update_modified=False
            )
            changed = True
    if changed:
        frappe.cache.delete_key("desktop_icons")


def add_previous_billing_links(bootinfo):
    """Link each retired billing app's workspace from the active app's sidebars."""
    by_app = billing_workspaces()
    if len(by_app) < 2:
        return
    active = active_financial_app()
    retired = [ws for app, names in by_app.items() if app != active for ws in names]
    sidebars = bootinfo.get("workspace_sidebar_item") or {}
    for ws in by_app.get(active) or []:
        sidebar = sidebars.get(ws.lower())
        if not sidebar or not retired:
            continue
        present = {item.get("link_to") for item in sidebar.get("items") or []}
        for target in retired:
            if target in present:
                continue
            sidebar.setdefault("items", []).append(
                {
                    "label": _("Previous billing"),
                    "type": "Link",
                    "link_type": "Workspace",
                    "link_to": target,
                    "icon": "archive",
                }
            )
