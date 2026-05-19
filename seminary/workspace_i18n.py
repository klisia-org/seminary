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

_CONTENT_TEXT_TYPES = {"header", "paragraph"}


@frappe.whitelist()
def get_desktop_page(page: str):
    response = desktop.get_desktop_page(page) or {}
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
        if page.get("title"):
            page["title"] = _(page["title"])
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
        btype = block.get("type")
        if btype in _CONTENT_TEXT_TYPES and data.get("text"):
            data["text"] = _(data["text"])
        elif btype == "card" and data.get("card_name"):
            data["card_name"] = _(data["card_name"])
        elif btype == "chart" and data.get("chart_name"):
            data["chart_name"] = _(data["chart_name"])

    return json.dumps(blocks)
