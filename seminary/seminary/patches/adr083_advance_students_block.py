"""Point the Registrar's Advance Students block at the per-program dialog
(ADR 083 §4).

The old block called `api.roll_students`, which is gone: it advanced everyone
with no grade check and could be clicked twice. Blocks are created once and
never overwritten on migrate, so this one is rewritten here, only when it still
calls the retired method.
"""

import frappe

BLOCK = "Registrar - Advance Students"


def execute():
    script = frappe.db.get_value("Custom HTML Block", BLOCK, "script")
    if not script or "roll_students" not in script:
        return
    from seminary.seminary.workspaces_bootstrap import (
        REGISTRAR_TOOLS,
        _ensure_custom_html_block,
    )

    block = next(b for b in REGISTRAR_TOOLS if b["name"] == BLOCK)
    _ensure_custom_html_block(block, overwrite=True)
