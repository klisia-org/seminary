"""Mailing-label sheets for Seminary Announcements sent on the Print channel
(ADR 045). Renders recipient postal addresses onto a standard Avery-style label
grid as a PDF, attached to the announcement.

Only recipients with a usable street address are placed; the rest are reported
as omitted. Today that means Students (which carry a full address) — Alumni hold
only city/country and Persons hold none, so they're skipped until those records
grow a street address.
"""

import frappe
from frappe.utils import escape_html
from frappe.utils.pdf import get_pdf

DEFAULT_MODEL = "Avery 5160"


def _spec(model):
    """Geometry dict for a Mailing Label Format, falling back to the default."""
    name = model if frappe.db.exists("Mailing Label Format", model) else DEFAULT_MODEL
    f = frappe.get_doc("Mailing Label Format", name)
    return {
        "page": f.page_size or "Letter",
        "margin_top": f.margin_top or 0,
        "margin_left": f.margin_left or 0,
        "cols": int(f.columns or 1),
        "rows": int(f.rows or 1),
        "cell_w": f.label_width or 60,
        "cell_h": f.label_height or 25,
    }


def recipient_address(recipient):
    """Resolve a mailable postal address for a recipient (a dict with email /
    user / party / party_type), or None when no street address is on file.
    Prefers the Person spine, falls back to the Student record. Returns
    {name, lines:[...]}."""
    from seminary.seminary.person import find_person

    name = recipient.get("party_name")

    person_name = find_person(email=recipient.get("email"), user=recipient.get("user"))
    if person_name:
        p = frappe.db.get_value(
            "Person",
            person_name,
            [
                "full_name",
                "address_line_1",
                "address_line_2",
                "city",
                "state",
                "pincode",
                "country",
            ],
            as_dict=True,
        )
        block = _address_block(p, name)
        if block:
            return block

    if recipient.get("party_type") == "Student" and recipient.get("party"):
        s = frappe.db.get_value(
            "Student",
            recipient["party"],
            [
                "student_name",
                "address_line_1",
                "address_line_2",
                "city",
                "state",
                "pincode",
                "country",
            ],
            as_dict=True,
        )
        block = _address_block(s, name, name_field="student_name")
        if block:
            return block
    return None


def _address_block(rec, fallback_name, name_field="full_name"):
    """Build {name, lines} from a record with address_line_1/2, city, state,
    pincode, country. Returns None when there is no street line."""
    if not rec or not rec.get("address_line_1"):
        return None
    locality = ", ".join(p for p in (rec.get("city"), rec.get("state")) if p)
    if rec.get("pincode"):
        locality = f"{locality} {rec['pincode']}".strip()
    lines = [
        rec.get(name_field) or fallback_name,
        rec.get("address_line_1"),
        rec.get("address_line_2"),
        locality or None,
        rec.get("country"),
    ]
    return {
        "name": rec.get(name_field) or fallback_name,
        "lines": [l for l in lines if l],
    }


def render_labels_pdf(recipients, model=None):
    """recipients: list of dicts with party_type / party / party_name / email / user.
    Returns (pdf_bytes, placed_count, omitted_names)."""
    spec = _spec(model)
    placed, omitted = [], []
    for r in recipients:
        addr = recipient_address(r)
        if addr:
            placed.append(addr)
        else:
            omitted.append(r.get("party_name") or r.get("email") or r.get("party"))

    html = _labels_html(placed, spec)
    options = {
        "page-size": spec["page"],
        "margin-top": f"{spec['margin_top']}mm",
        "margin-left": f"{spec['margin_left']}mm",
        "margin-right": "0mm",
        "margin-bottom": "0mm",
    }
    return get_pdf(html, options=options), len(placed), omitted


def _labels_html(entries, spec):
    per_page = spec["cols"] * spec["rows"]
    cell_w, cell_h = spec["cell_w"], spec["cell_h"]
    css = f"""
    <style>
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; font-family: Arial, sans-serif; }}
      table.labels {{ border-collapse: collapse; table-layout: fixed; }}
      table.labels td {{
        width: {cell_w}mm; height: {cell_h}mm;
        padding: 3mm 4mm; overflow: hidden; vertical-align: middle;
        font-size: 10pt; line-height: 1.25;
      }}
      .page {{ page-break-after: always; }}
      .page:last-child {{ page-break-after: auto; }}
    </style>
    """
    if not entries:
        return (
            css
            + f"<p>{escape_html(frappe._('No recipients with a postal address.'))}</p>"
        )

    pages = []
    for start in range(0, len(entries), per_page):
        chunk = entries[start : start + per_page]
        cells = []
        for e in chunk:
            block = "<br>".join(escape_html(line) for line in e["lines"])
            cells.append(f"<td>{block}</td>")
        # pad the final page so the grid stays rectangular
        while len(cells) % spec["cols"]:
            cells.append("<td></td>")
        rows_html = ""
        for i in range(0, len(cells), spec["cols"]):
            rows_html += "<tr>" + "".join(cells[i : i + spec["cols"]]) + "</tr>"
        pages.append(
            f'<div class="page"><table class="labels">{rows_html}</table></div>'
        )
    return css + "".join(pages)


def attach_labels_for_announcement(doc):
    """Render the announcement's mailing labels and attach the PDF to it.
    Returns {file_url, placed, omitted}."""
    recipients = [
        {
            "party_type": r.party_type,
            "party": r.party,
            "party_name": r.party_name,
            "email": r.email,
            "user": r.user,
        }
        for r in doc.recipients
    ]
    return _render_and_attach(doc.name, recipients, doc.label_format)


def _render_and_attach(announcement, recipients, model):
    pdf, placed, omitted = render_labels_pdf(recipients, model)
    # Replace any prior label sheet so re-runs don't pile up.
    for old in frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Seminary Announcement",
            "attached_to_name": announcement,
            "file_name": ("like", "labels-%"),
        },
        pluck="name",
    ):
        frappe.delete_doc("File", old, ignore_permissions=True, force=True)

    f = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": f"labels-{announcement}.pdf",
            "attached_to_doctype": "Seminary Announcement",
            "attached_to_name": announcement,
            "is_private": 1,
            "content": pdf,
        }
    ).insert(ignore_permissions=True)
    return {"file_url": f.file_url, "placed": placed, "omitted": omitted}
