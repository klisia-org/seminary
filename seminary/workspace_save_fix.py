"""Fix Frappe v16's broken public-workspace save guard.

`frappe.desk.doctype.workspace.workspace.save_page` guards with:

    if not (is_workspace_manager() and doc.for_user == frappe.session.user):
        return

For a *public* workspace `for_user` is empty, so the equality is always
False and the whole guard is always True -- the method returns without
saving anything. The save XHR succeeds with a null payload, so the desk
editor hangs (it expects ``{name, public, label}``), no error is logged,
and the edits vanish on reload. This hits everyone, including
Administrator, since the role half can never rescue the empty `for_user`.

The intent is OR, not AND: you may save if you are a Workspace Manager
*or* the workspace is your own private one. Wired up via
`override_whitelisted_methods` in `hooks.py`. Remove that entry and delete
this file once upstream fixes the operator.
"""

import frappe
from frappe.desk.desktop import save_new_widget
from frappe.desk.doctype.workspace.workspace import is_workspace_manager


@frappe.whitelist()
def save_page(name, public, new_widgets, blocks):
    public = frappe.parse_json(public)

    doc = frappe.get_doc("Workspace", name)
    if not (is_workspace_manager() or doc.for_user == frappe.session.user):
        return

    if not doc.type:
        doc.type = "Workspace"

    doc.content = blocks

    save_new_widget(doc, name, blocks, new_widgets)

    return {"name": name, "public": public, "label": doc.label}
