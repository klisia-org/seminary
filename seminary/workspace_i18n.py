"""Translate workspace strings that Frappe v16 misses.

Frappe v16's workspace refactor left a few user-facing fields out of the
server-side translation pass in `frappe.desk.desktop`:

  - `Workspace.title` — rendered in the sidebar / page header / breadcrumbs
    (sibling `label` is translated; `title` is not).
  - The `content` JSON blob — `header` / `paragraph` text and `card` /
    `chart` block IDs (`data.card_name`, `data.chart_name`) are sent to
    the client unchanged.

Wired up via `override_whitelisted_methods` in `hooks.py`. `_()` is
idempotent on already-translated strings, so when Frappe ships a fix
this wrapper becomes harmless. To remove, drop the two entries from
`override_whitelisted_methods` and delete this file.
"""

import json

import frappe
from frappe import _
from frappe.desk import desktop

from seminary import desk_nav

# Block type → the data key holding its user-facing text. Values reach `_()`
# through a variable: a literal key inside `_()` would be extracted into the POT.
_CONTENT_TEXT_KEYS = {
    "header": "text",
    "paragraph": "text",
    "card": "card_name",
    "chart": "chart_name",
}


@frappe.whitelist()
def get_desktop_page(page: str):
    response = desk_nav.get_desktop_page(page) or {}
    for key in (
        "cards",
        "charts",
        "shortcuts",
        "quick_lists",
        "number_cards",
        "custom_blocks",
    ):
        section = response.get(key) or {}
        for item in section.get("items") or []:
            label = (
                item.get("label")
                if isinstance(item, dict)
                else getattr(item, "label", None)
            )
            if label:
                translated = _(label)
                if isinstance(item, dict):
                    item["label"] = translated
                else:
                    item.label = translated
    return response


@frappe.whitelist()
def get_workspace_sidebar_items():
    response = desktop.get_workspace_sidebar_items() or {}
    for page in response.get("pages") or []:
        if title := page.get("title"):
            page["title"] = _(title)
        page["content"] = _translate_content(page.get("content"))
    return response


def _translate_content(content):
    if not content:
        return content
    try:
        blocks = json.loads(content) if isinstance(content, str) else content
    except (json.JSONDecodeError, TypeError):
        return content
    if not isinstance(blocks, list):
        return content

    for block in blocks:
        if not isinstance(block, dict):
            continue
        data = block.get("data") or {}
        key = _CONTENT_TEXT_KEYS.get(block.get("type"))
        if key and (value := data.get(key)):
            data[key] = _(value)

    return json.dumps(blocks)
