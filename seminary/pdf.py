"""PDFs through Chrome (ADR 099).

`render` replaces `frappe.utils.pdf.get_pdf`, which always uses wkhtmltopdf. Callers keep the
wkhtmltopdf-style options they already pass: page size, orientation, margins, and a centred header
or footer whose `[page]` and `[topage]` become page numbers.
"""

import re

import frappe
from frappe.utils import escape_html

PAGE_KEYS = (
    "margin-top",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "page-size",
    "orientation",
    "page-width",
    "page-height",
)


def render(html, options=None, header=None, footer=None) -> bytes:
    """HTML to PDF bytes through Frappe's Chrome generator.

    `header` and `footer` are HTML repeated on every page; inside them `<span class="page">` and
    `<span class="topage">` become the page number and the page count. wkhtmltopdf's
    `header-center` / `footer-center` text options are turned into the same thing."""
    from frappe.utils.pdf import get_chrome_pdf, scrub_urls

    options = dict(options or {})
    header = header or _band(options, "header")
    footer = footer or _band(options, "footer")
    if not options.get("page-size") and not options.get("page-height"):
        options["page-size"] = (
            frappe.db.get_single_value("Print Settings", "pdf_page_size") or "A4"
        )
    # Without a header or footer Frappe's Chrome path forces 15mm margins; margins stated in the
    # document's own `.print-format` rule are read after that, so they win.
    page_rule = "".join(f"{k}:{options[k]};" for k in PAGE_KEYS if options.get(k))
    # A band of empty page-number spans measures zero high, and a band with no margin on its side
    # leaves Chrome a zero paper height: give both a floor.
    if header:
        header = f'<div style="min-height:6mm">{header}</div>'
        options.setdefault("margin-top", "5mm")
    if footer:
        footer = f'<div style="min-height:6mm">{footer}</div>'
        options.setdefault("margin-bottom", "5mm")
    bands = ""
    if header:
        bands += f'<div id="header-html">{header}</div>'
    if footer:
        bands += f'<div id="footer-html">{footer}</div>'
    # Frappe copies the styles into the header and footer pages, where `.print-format` wraps the
    # band: there the rule must not move it.
    style = (
        f"<style>.print-format{{{page_rule}}}"
        ".print-format:has(> .wrapper){margin:0 !important}</style>"
        if page_rule
        else ""
    )
    document = _document(scrub_urls(html), style, bands)
    pdf = get_chrome_pdf(
        print_format=None,
        html=document,
        options={k: v for k, v in options.items() if k in PAGE_KEYS or k == "password"},
        output=None,
        pdf_generator="chrome",
    )
    if not pdf:
        frappe.throw(frappe._("The PDF could not be made: Chrome did not return one."))
    return pdf


def _band(options, where):
    """wkhtmltopdf's `<where>-center` text, with `[page]` and `[topage]`, as HTML."""
    text = options.pop(f"{where}-center", None)
    size = options.pop(f"{where}-font-size", None) or 8
    for key in [k for k in options if k.startswith(f"{where}-")]:
        options.pop(key)
    if not text:
        return None
    text = escape_html(str(text))
    text = text.replace("[page]", '<span class="page"></span>').replace(
        "[topage]", '<span class="topage"></span>'
    )
    return f'<div style="text-align:center;font-size:{size}pt;font-family:sans-serif">{text}</div>'


def _document(html, style, bands):
    """A whole HTML document, with the page rule in its head and the bands first in its body."""
    if not re.search(r"<html[\s>]", html, re.IGNORECASE):
        html = f'<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>{html}</body></html>'
    if not re.search(r"<head[\s>]", html, re.IGNORECASE):
        html = re.sub(
            r"(<html[^>]*>)",
            r'\1<head><meta charset="utf-8"></head>',
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    html = re.sub(r"(</head>)", style + r"\1", html, count=1, flags=re.IGNORECASE)
    if re.search(r"<body[^>]*>", html, re.IGNORECASE):
        html = re.sub(
            r"(<body[^>]*>)",
            r"\1" + bands.replace("\\", "\\\\"),
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        html = html.replace("</html>", f"<body>{bands}</body></html>")
    return html
