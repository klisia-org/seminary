"""One-shot helper to create role-specific public Workspaces.

Frappe v16 (this build) has no working UI to create a Workspace *page*: the
in-page `.btn-new-workspace` / `.btn-edit-workspace` selectors are never
rendered, the sidebar editor's "+" only adds a *sidebar item* linking to an
existing workspace, and the Workspace doctype is `in_create=1` (no list "New").
So new workspaces have to be inserted programmatically.

Run manually, once, per site:

    bench --site <site> execute seminary.seminary.workspaces_bootstrap.run

Idempotent: skips a workspace that already exists. NOT wired into install or
migrate on purpose — re-importing would clobber any Desk edits (see the
"don't fixture user-configurable doctypes" rule). After creation, refine each
workspace via the sidebar editor or the Workspace form (editing existing
records works; only the New button is hidden).
"""

import json
import re

import frappe


def _shortcut(label, link_to, type_="DocType", color="Grey", doc_view="List"):
    row = {"label": label, "link_to": link_to, "type": type_, "color": color}
    if type_ == "DocType":
        row["doc_view"] = doc_view
    return row


def _card(label, items):
    """items: list of (label, link_to, link_type)."""
    rows = [
        {
            "label": label,
            "type": "Card Break",
            "link_type": items[0][2] if items else "DocType",
            "link_count": len(items),
            "hidden": 0,
            "onboard": 0,
            "is_query_report": 0,
        }
    ]
    for lbl, lt, ltype in items:
        rows.append(
            {
                "label": lbl,
                "link_to": lt,
                "link_type": ltype,
                "type": "Link",
                "hidden": 0,
                "onboard": 0,
                "is_query_report": 1 if ltype == "Report" else 0,
            }
        )
    return rows


def _content(title, shortcut_labels, card_labels):
    blocks = [
        {
            "id": frappe.generate_hash(length=10),
            "type": "header",
            "data": {"text": f'<span class="h4">{title}</span>', "col": 12},
        }
    ]
    for s in shortcut_labels:
        blocks.append(
            {
                "id": frappe.generate_hash(length=10),
                "type": "shortcut",
                "data": {"shortcut_name": s, "col": 3},
            }
        )
    if shortcut_labels and card_labels:
        blocks.append(
            {
                "id": frappe.generate_hash(length=10),
                "type": "spacer",
                "data": {"col": 12},
            }
        )
    for c in card_labels:
        blocks.append(
            {
                "id": frappe.generate_hash(length=10),
                "type": "card",
                "data": {"card_name": c, "col": 4},
            }
        )
    return frappe.as_json(blocks)


def _next_sequence_id():
    last = frappe.db.sql(
        "SELECT MAX(sequence_id) FROM `tabWorkspace` WHERE public = 1"
    )[0][0]
    return (last or 0) + 1


def create_workspace(title, icon, roles, shortcuts, cards):
    if frappe.db.exists("Workspace", title):
        print(f"  skip (exists): {title}")
        return
    links = []
    for c in cards:
        links += _card(c["label"], c["items"])
    doc = frappe.get_doc(
        {
            "doctype": "Workspace",
            "title": title,
            "label": title,
            "name": title,
            "public": 1,
            "for_user": "",
            "module": "Seminary",
            "type": "Workspace",
            "icon": icon,
            "sequence_id": _next_sequence_id(),
            "roles": [{"role": r} for r in roles],
            "shortcuts": shortcuts,
            "links": links,
            "content": _content(
                title, [s["label"] for s in shortcuts], [c["label"] for c in cards]
            ),
        }
    )
    doc.insert(ignore_permissions=True)
    print(f"  created: {title}")


# Action buttons that replace the retired Registrar Hub page. Each becomes a
# Custom HTML Block rendered on the workspace; `root_element` is the block's
# container, per the Custom HTML Block JS contract.
REGISTRAR_TOOLS = [
    {
        "name": "Registrar - Advance Students",
        "label": "Advance Students",
        "roles": ["Registrar", "Seminary Manager"],
        "html": (
            '<div class="rg-tool">\n'
            '  <button class="btn btn-primary btn-sm rg-advance-btn">Advance Students</button>\n'
            '  <div class="text-muted small" style="margin-top:6px;">Advance all active'
            " students to the next term. Confirm grades for the ending term are"
            " finalized first.</div>\n"
            "</div>"
        ),
        "script": (
            "root_element.querySelector('.rg-advance-btn').addEventListener('click', () => {\n"
            "    frappe.confirm(\n"
            "        __('Advance all active students to the next term? Confirm that grades"
            " for the ending term are finalized first.'),\n"
            "        () => {\n"
            "            frappe.call({\n"
            "                method: 'seminary.seminary.api.roll_students',\n"
            "                freeze: true,\n"
            "                freeze_message: __('Advancing students...'),\n"
            "                callback: (r) => frappe.show_alert({ message: r.message ||"
            " __('Done'), indicator: 'green' }),\n"
            "            });\n"
            "        }\n"
            "    );\n"
            "});"
        ),
    },
    {
        "name": "Registrar - Regenerate Current-Term Invoices",
        "label": "Regenerate Current-Term Invoices",
        "roles": ["Registrar", "Seminary Manager"],
        "html": (
            '<div class="rg-tool">\n'
            '  <button class="btn btn-default btn-sm rg-regen-btn">Regenerate'
            " Current-Term Invoices</button>\n"
            '  <div class="text-muted small" style="margin-top:6px;">Clear the current'
            " term's billing flag and regenerate its New-Academic-Term invoices."
            " Duplicates are prevented by the seminary_trigger check.</div>\n"
            "</div>"
        ),
        "script": (
            "root_element.querySelector('.rg-regen-btn').addEventListener('click', () => {\n"
            "    frappe.confirm(\n"
            "        __(\"Clear the current term's billing flag and regenerate its"
            " New-Academic-Term invoices? Duplicates are prevented by the"
            ' seminary_trigger check."),\n'
            "        () => {\n"
            "            frappe.call({\n"
            "                method: 'seminary.seminary.api.regenerate_current_term_invoices',\n"
            "                freeze: true,\n"
            "                freeze_message: __('Regenerating invoices...'),\n"
            "                callback: (r) => {\n"
            "                    const res = r.message || {};\n"
            "                    frappe.show_alert({\n"
            "                        message: __('Created {0}, skipped {1}, failed {2}.',"
            " [res.created || 0, res.skipped || 0, res.failed || 0]),\n"
            "                        indicator: res.failed ? 'orange' : 'green',\n"
            "                    });\n"
            "                },\n"
            "            });\n"
            "        }\n"
            "    );\n"
            "});"
        ),
    },
]


def _ensure_custom_html_block(block):
    name = block["name"]
    if frappe.db.exists("Custom HTML Block", name):
        doc = frappe.get_doc("Custom HTML Block", name)
    else:
        doc = frappe.new_doc("Custom HTML Block")
        doc.name = name  # autoname = prompt
    doc.html = block["html"]
    doc.script = block["script"]
    doc.private = 0
    doc.set("roles", [{"role": r} for r in block.get("roles", [])])
    doc.save(ignore_permissions=True)


def _attach_custom_blocks(workspace, blocks):
    ws = frappe.get_doc("Workspace", workspace)
    existing = {cb.custom_block_name for cb in (ws.custom_blocks or [])}
    content = frappe.parse_json(ws.content) or []
    added = []
    for b in blocks:
        _ensure_custom_html_block(b)
        if b["name"] in existing:
            continue
        ws.append(
            "custom_blocks", {"custom_block_name": b["name"], "label": b["label"]}
        )
        content.append(
            {
                "id": frappe.generate_hash(length=10),
                "type": "custom_block",
                "data": {"custom_block_name": b["name"], "col": 12},
            }
        )
        added.append(b["name"])
    if added:
        ws.content = frappe.as_json(content)
        ws.save(ignore_permissions=True)
        print(f"  attached custom blocks to {workspace}: {added}")
    else:
        print(f"  custom blocks already attached to {workspace}")


def _ensure_sidebars():
    """Generate the per-workspace Workspace Sidebar records.

    A workspace's left sidebar comes from a `Workspace Sidebar` record named
    after the workspace (Home item + its shortcuts). Frappe only generates these
    at site install, so a workspace added later shows a blank sidebar until this
    runs. Idempotent — skips workspaces that already have a sidebar.
    """
    from frappe.desk.doctype.workspace_sidebar.workspace_sidebar import (
        create_workspace_sidebar_for_workspaces,
    )

    create_workspace_sidebar_for_workspaces()


_STEP_NUM = re.compile(r"^\s*(\d+)([a-z]?)\s*\.\s*")


def renumber_getting_started(workspace="Getting Started SeminaryERP"):
    """Resequence the numbered setup-step labels to contiguous 1..N.

    Order is taken from the existing numbers, treating letter-suffixed
    insertions (11a, 17b, ...) as falling right after their base number. Labels
    in both `shortcuts` and `links`, and the `shortcut_name` references in the
    workspace content, are kept in sync. `**`-prefixed (non-numbered) items are
    left untouched. Run:

        bench --site <site> execute \
            seminary.seminary.workspaces_bootstrap.renumber_getting_started
    """

    def key(label):
        m = _STEP_NUM.match(label or "")
        return (int(m.group(1)), m.group(2)) if m else None

    doc = frappe.get_doc("Workspace", workspace)
    rows = [r for r in doc.shortcuts if key(r.label)]
    rows += [r for r in doc.links if r.type == "Link" and key(r.label)]
    rows.sort(key=lambda r: key(r.label))

    remap = {}
    for i, row in enumerate(rows, start=1):
        new_label = _STEP_NUM.sub(f"{i}. ", row.label, count=1)
        if new_label != row.label:
            remap[row.label] = new_label
            row.label = new_label

    content = frappe.parse_json(doc.content) or []
    for block in content:
        if block.get("type") == "shortcut":
            sn = (block.get("data") or {}).get("shortcut_name")
            if sn in remap:
                block["data"]["shortcut_name"] = remap[sn]
    doc.content = json.dumps(content, separators=(",", ":"))

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"Renumbered {len(rows)} items; {len(remap)} labels changed.")


def run():
    create_workspace(
        title="Registrar",
        icon="users",
        roles=["Registrar", "Seminary Manager"],
        shortcuts=[
            _shortcut("Registrar Hub", "registrar-hub", "Page"),
            _shortcut("Students", "Student"),
            _shortcut("Program Enrollment", "Program Enrollment"),
            _shortcut("Term Admission", "Term Admission"),
            _shortcut("Graduation Request", "Graduation Request"),
        ],
        cards=[
            {
                "label": "Records",
                "items": [
                    ("Student", "Student", "DocType"),
                    ("Program Enrollment", "Program Enrollment", "DocType"),
                    (
                        "Course Enrollment Individual",
                        "Course Enrollment Individual",
                        "DocType",
                    ),
                    ("Academic Term", "Academic Term", "DocType"),
                    ("Term Admission", "Term Admission", "DocType"),
                ],
            },
            {
                "label": "Graduation",
                "items": [
                    ("Graduation Request", "Graduation Request", "DocType"),
                    ("Diploma", "Diploma", "DocType"),
                    ("Recommendation Letter", "Recommendation Letter", "DocType"),
                    ("Culminating Project", "Culminating Project", "DocType"),
                ],
            },
            {
                "label": "Discipline & Withdrawals",
                "items": [
                    ("Disciplinary Incident", "Disciplinary Incident", "DocType"),
                    (
                        "Withdrawal Request",
                        "Withdrawal Request",
                        "DocType",
                    ),
                ],
            },
        ],
    )

    _attach_custom_blocks("Registrar", REGISTRAR_TOOLS)
    _ensure_sidebars()
    frappe.db.commit()
    print("Done.")
