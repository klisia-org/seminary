"""Keep Desk tidy when a workspace points at an app that is missing or not in use.

A workspace names its cards, shortcuts, charts and blocks by label, and each one
targets a doctype, report, page or record that some app owns. When that app is
not installed, Frappe drops the item but keeps its place in the layout: a blank
gap in the grid, a header with nothing under it, and -- for Administrator, whose
items skip the permission filter -- one missing doctype blanks every card on the
page. Here those items are dropped when the page is served, along with the
headers and spacers they leave empty. Stored workspaces are never edited, so
installing the app later brings its blocks back (aretenic decision 051 §5).

An app can also hide a block whose target is installed but not in use, through
the `desk_block_gates` hook:

    desk_block_gates = {
        "<Workspace>": {"<kind>:<label>": "dotted.path.to.predicate"},
    }

`kind` is card, shortcut, chart, number_card, quick_list or custom_block; the
predicate takes no arguments and returns True to show the block.

`desk_target_gates` does the same for a target rather than a block, so a link is
hidden wherever it appears:

    desk_target_gates = {
        "<link type>": {"<name>": "dotted.path.to.predicate"},
    }

koinonia carries a copy of this module because it does not require seminary.
Keep the two in step: both are wired as `boot_session` hooks (every app's hook
runs, and pruning twice is harmless), and both back the `get_desktop_page`
override (only the last app's override runs).
"""

import copy
import html
import json

import frappe
from frappe.desk import desktop

# Content block type -> the key in its `data` that names the item.
BLOCK_KEYS = {
    "card": "card_name",
    "shortcut": "shortcut_name",
    "chart": "chart_name",
    "number_card": "number_card_name",
    "quick_list": "quick_list_name",
    "custom_block": "custom_block_name",
}

# Link types whose target is a record we can check for. Anything else (URL,
# a blank type) is left alone.
TARGET_DOCTYPES = {
    "DocType",
    "Report",
    "Page",
    "Dashboard",
    "Workspace",
    "Dashboard Chart",
    "Number Card",
    "Custom HTML Block",
}


def target_exists(link_type, name):
    if link_type not in TARGET_DOCTYPES:
        return True
    return bool(name) and name in _names(link_type) and target_open(link_type, name)


def target_open(link_type, name):
    """False when a `desk_target_gates` predicate hides this target. Where
    `desk_block_gates` hides one block on one workspace, this hides a target
    everywhere it is linked: cards, shortcuts and sidebars alike."""
    gates = frappe.get_hooks("desk_target_gates") or {}
    paths = (gates.get(link_type) or {}).get(name) or []
    if isinstance(paths, str):
        paths = [paths]
    return all(frappe.get_attr(path)() for path in paths)


def _names(doctype):
    cache = getattr(frappe.local, "desk_nav_names", None)
    if cache is None:
        cache = frappe.local.desk_nav_names = {}
    if doctype not in cache:
        cache[doctype] = set(frappe.get_all(doctype, pluck="name"))
    return cache[doctype]


def gate_open(workspace, kind, label):
    """False when an app's `desk_block_gates` predicate hides this block."""
    gates = frappe.get_hooks("desk_block_gates") or {}
    paths = (gates.get(workspace) or {}).get(f"{kind}:{label}") or []
    if isinstance(paths, str):
        paths = [paths]
    return all(frappe.get_attr(path)() for path in paths)


def pruned_workspace(doc):
    """A copy of the Workspace with every unreachable or gated item removed."""
    doc = copy.deepcopy(doc)
    name = doc.name

    links, card_open = [], True
    for row in doc.links:
        if row.type == "Card Break":
            card_open = gate_open(name, "card", row.label)
            links.append(row)
        elif card_open and target_exists(row.link_type, row.link_to):
            links.append(row)
    doc.links = [
        row
        for i, row in enumerate(links)
        if row.type != "Card Break"
        or (i + 1 < len(links) and links[i + 1].type != "Card Break")
    ]

    doc.shortcuts = [
        row
        for row in doc.shortcuts
        if gate_open(name, "shortcut", row.label)
        and target_exists(row.type, row.link_to)
    ]
    doc.charts = [
        row
        for row in doc.charts
        if gate_open(name, "chart", row.label or row.chart_name)
        and target_exists("Dashboard Chart", row.chart_name)
    ]
    doc.number_cards = [
        row
        for row in doc.number_cards
        if gate_open(name, "number_card", row.label or row.number_card_name)
        and target_exists("Number Card", row.number_card_name)
    ]
    doc.quick_lists = [
        row
        for row in doc.quick_lists
        if gate_open(name, "quick_list", row.label or row.document_type)
        and target_exists("DocType", row.document_type)
    ]
    doc.custom_blocks = [
        row
        for row in doc.custom_blocks
        if gate_open(name, "custom_block", row.label or row.custom_block_name)
        and gate_open(name, "custom_block", row.custom_block_name)
        and target_exists("Custom HTML Block", row.custom_block_name)
    ]
    return doc


def _available(doc):
    """{block kind: labels a content block may name} for a pruned Workspace."""
    return {
        "card": {row.label for row in doc.links if row.type == "Card Break"},
        "shortcut": {row.label for row in doc.shortcuts},
        "chart": {row.label or row.chart_name for row in doc.charts},
        "number_card": {row.label or row.number_card_name for row in doc.number_cards},
        "quick_list": {row.label or row.document_type for row in doc.quick_lists},
        "custom_block": {row.label for row in doc.custom_blocks}
        | {row.custom_block_name for row in doc.custom_blocks},
    }


def prune_content(workspace, blocks):
    """The content blocks that will render, with emptied sections tidied away.

    Returns `blocks` itself when nothing was dropped, so a page no app touches
    renders exactly as authored.
    """
    try:
        doc = frappe.get_cached_doc("Workspace", workspace)
    except frappe.DoesNotExistError:
        frappe.clear_last_message()
        return blocks
    available = {
        kind: {html.unescape(label or "") for label in labels}
        for kind, labels in _available(pruned_workspace(doc)).items()
    }

    kept, dropped = [], set()
    for i, block in enumerate(blocks):
        key = BLOCK_KEYS.get(block.get("type"))
        if key:
            label = html.unescape((block.get("data") or {}).get(key) or "")
            if label not in available[block["type"]]:
                dropped.add(i)
                continue
        kept.append((i, block))
    if not dropped:
        return blocks
    return _tidy(kept, dropped)


def _tidy(kept, dropped):
    """Drop a header whose section lost blocks and has nothing left, then the
    spacers that run together or trail at the end."""
    out = []
    for n, (i, block) in enumerate(kept):
        if block.get("type") == "header":
            nxt = next(
                (
                    j
                    for j, (_, b) in enumerate(kept[n + 1 :], n + 1)
                    if b.get("type") == "header"
                ),
                len(kept),
            )
            end = kept[nxt][0] if nxt < len(kept) else float("inf")
            lost = any(i < d < end for d in dropped)
            has_content = any(b.get("type") != "spacer" for _, b in kept[n + 1 : nxt])
            if lost and not has_content:
                continue
        if block.get("type") == "spacer" and out and out[-1].get("type") == "spacer":
            continue
        out.append(block)
    while out and out[-1].get("type") == "spacer":
        out.pop()
    return out


def prune_sidebar_items(sidebars):
    """Drop sidebar links to missing targets, then section breaks left empty.

    Frappe already hides unreadable links from everyone but Administrator; this
    covers Administrator and keeps the section headers honest.
    """
    for sidebar in (sidebars or {}).values():
        items = [
            item
            for item in sidebar.get("items") or []
            if item.get("type") == "Section Break"
            or target_exists(item.get("link_type"), item.get("link_to"))
        ]
        sidebar["items"] = [
            item
            for i, item in enumerate(items)
            if item.get("type") != "Section Break"
            or (i + 1 < len(items) and items[i + 1].get("type") != "Section Break")
        ]


def boot_session(bootinfo):
    for page in (bootinfo.get("workspaces") or {}).get("pages") or []:
        content = page.get("content")
        if not content:
            continue
        blocks = json.loads(content) if isinstance(content, str) else content
        if not isinstance(blocks, list):
            continue
        pruned = prune_content(page.get("name"), blocks)
        if pruned is not blocks:
            page["content"] = json.dumps(pruned)
    prune_sidebar_items(bootinfo.get("workspace_sidebar_item"))


def get_desktop_page(page):
    """`frappe.desk.desktop.get_desktop_page`, built from the pruned Workspace."""
    try:
        workspace = desktop.Workspace(
            json.loads(page) if isinstance(page, str) else page
        )
        workspace.doc = pruned_workspace(workspace.doc)
        workspace.build_workspace()
        return {
            "charts": workspace.charts,
            "shortcuts": workspace.shortcuts,
            "cards": workspace.cards,
            "onboardings": workspace.onboardings,
            "quick_lists": workspace.quick_lists,
            "number_cards": workspace.number_cards,
            "custom_blocks": workspace.custom_blocks,
        }
    except frappe.DoesNotExistError:
        frappe.log_error("Workspace Missing")
        return {}
