# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""One set of billing entries on the Seminary rail, whichever billing app is active.

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


SETUP_SIDEBAR = "Seminary Setup"


def setup_sections() -> list[tuple[str, dict]]:
    """[(app, section spec)] from `seminary_setup_sections`, skipping retired billing apps.

    A spec is {"section": label, "after": label, "icon": name, "links": [{"label",
    "link_type", "link_to"}]}. It adds rows to the Setup section it names, or a new section
    placed after `after` (decision 088a §4).
    """
    billing = set(registered_financial_backends())
    active = active_financial_app()
    return [
        (app, spec)
        for app in frappe.get_installed_apps()
        if app not in billing or app == active
        for spec in frappe.get_hooks("seminary_setup_sections", app_name=app)
    ]


def _section_end(items, label):
    """Index just past the section labelled `label`, or None when it is absent."""
    start = next(
        (
            i
            for i, item in enumerate(items)
            if item.get("type") == "Section Break" and item.get("label") == label
        ),
        None,
    )
    if start is None:
        return None
    end = start + 1
    while end < len(items) and items[end].get("child"):
        end += 1
    return end


def _setup_row(app, link):
    link_type = link.get("link_type") or "DocType"
    label = link["label"]  # via a variable, or the key "label" lands in the POT
    return {
        "key": f"setup-{app}-{link_type}-{link['link_to']}",
        "label": _(label),
        "type": "Link",
        "link_type": link_type,
        "link_to": link["link_to"],
        "icon": None,
        "child": 1,
        "collapsible": 1,
        "indent": 0,
        "keep_closed": 0,
        "show_arrow": 0,
    }


def add_setup_sections(bootinfo):
    """Merge companion apps' Setup rows into the Setup sidebar, as this user may see them.

    `boot_session` runs after Frappe has permission-filtered the sidebars, so each row is
    checked here.
    """
    sidebar = (bootinfo.get("module_sidebars") or {}).get(SETUP_SIDEBAR)
    if not sidebar:
        return
    specs = setup_sections()
    if not specs:
        return

    from frappe.desk.desk_views import DeskViews
    from frappe.desk.utils import is_item_allowed

    context = DeskViews()
    items = sidebar.setdefault("items", [])
    for app, spec in specs:
        present = {item.get("link_to") for item in items if item.get("child")}
        rows = [
            _setup_row(app, link)
            for link in spec.get("links") or []
            if link["link_to"] not in present
            and is_item_allowed(
                link["link_to"], link.get("link_type") or "DocType", context
            )
        ]
        if not rows:
            continue
        section = spec["section"]
        at = _section_end(items, section)
        if at is None:
            after = _section_end(items, spec.get("after"))
            at = len(items) if after is None else after
            rows.insert(
                0,
                {
                    "key": f"setup-{app}-{section}",
                    "label": _(section),
                    "type": "Section Break",
                    "link_type": "DocType",
                    "link_to": None,
                    "icon": spec.get("icon"),
                    "child": 0,
                    "collapsible": 1,
                    "indent": 1,
                    "keep_closed": 1,
                    "show_arrow": 0,
                },
            )
        items[at:at] = rows


def boot_session(bootinfo):
    hide_inactive_billing(bootinfo)
    add_previous_billing_links(bootinfo)
    add_setup_sections(bootinfo)
