"""PDFs through Chrome (ADR 099), tagged for screen readers (ADR 104).

`render` replaces `frappe.utils.pdf.get_pdf`, which always uses wkhtmltopdf. Callers keep the
wkhtmltopdf-style options they already pass: page size, orientation, margins, and a centred header
or footer whose `[page]` and `[topage]` become page numbers.

Every PDF comes out tagged, with bookmarks for its headings, a language and a title. The
bookmarks are made here, from the tagged headings and the HTML's texts. A header or
footer is printed in the page margin by Chrome itself (CSS page-margin boxes): Frappe's separate
header and footer bands rebuild the file and lose its tags.
"""

import io
import re
from itertools import pairwise

import frappe
from frappe.utils import strip_html

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
# Where each margin box sits, and the page margin it needs to show.
BOXES = {"header": ("top-center", "margin-top"), "footer": ("bottom-center", "margin-bottom")}
# A margin box needs a margin to sit in: this is room for one line of small text.
BAND_MARGIN = "10mm"


def render(html, options=None, header=None, footer=None, title=None) -> bytes:
	"""HTML to tagged PDF bytes through Frappe's Chrome generator.

	`header` and `footer` are plain text repeated on every page, where `[page]` and `[topage]`
	become the page number and the page count. wkhtmltopdf's `header-center` / `footer-center`
	options mean the same. `title` names the document; without one, its first heading does."""
	from frappe.utils.pdf import get_chrome_pdf, scrub_urls

	options = dict(options or {})
	bands = {}
	for where in BOXES:
		text, size = _band(options, where)
		text = {"header": header, "footer": footer}[where] or text
		if text:
			bands[where] = (text, size)
			options.setdefault(BOXES[where][1], BAND_MARGIN)
	if not options.get("page-size") and not options.get("page-height"):
		options["page-size"] = frappe.db.get_single_value("Print Settings", "pdf_page_size") or "A4"
	password = options.pop("password", None)

	html, numbered = _inline_bands(_heading_levels(html))
	if numbered and not bands:
		bands["footer"] = (frappe._("Page {0} of {1}").format("[page]", "[topage]"), 8)
		options.setdefault("margin-bottom", BAND_MARGIN)
	document = _document(scrub_urls(html), _page_rule(options, bands), title)
	chrome = {k: v for k, v in options.items() if k in PAGE_KEYS}
	chrome["generate-tagged-pdf"] = True
	pdf = get_chrome_pdf(
		print_format=None, html=document, options=chrome, output=None, pdf_generator="chrome"
	)
	if not pdf:
		frappe.throw(frappe._("The PDF could not be made: Chrome did not return one."))
	return _finish(pdf, password, _headings(document))


def _inline_bands(html):
	"""Print a print view's repeated letter head and footer in the page itself.

	With "Repeat Header and Footer" on, the print view puts them in `#header-html` and
	`#footer-html`, which Frappe prints as separate bands and rebuilds the file to place: the tags
	are lost. Here they print once, at the top and the foot of the receipt, and the page numbers
	they carried go in the page margin instead. Returns the HTML and whether it had page numbers."""
	if "header-html" not in html and "footer-html" not in html:
		return html, False
	from bs4 import BeautifulSoup

	soup = BeautifulSoup(html, "html.parser")
	numbered = False
	for band in soup.find_all(id=["header-html", "footer-html"]):
		for counter in band.find_all(class_=["page", "topage"]):
			numbered = True
			holder = counter.find_parent(class_="page-number") or counter.parent
			if holder is not None and holder is not band:
				holder.extract()
			elif counter.parent is not None:
				counter.extract()
		# What the band showed in a PDF, it shows in the page.
		for hidden in band.find_all(class_="hidden-pdf"):
			hidden.extract()
		for shown in band.find_all(class_="visible-pdf"):
			shown["class"].remove("visible-pdf")
		del band["id"]
		band["class"] = [c for c in band.get("class", []) if c not in ("hidden-pdf", "visible-pdf")]
	return str(soup), numbered


def _band(options, where):
	"""wkhtmltopdf's `<where>-center` text and font size, taken out of `options`."""
	text = options.pop(f"{where}-center", None)
	size = options.pop(f"{where}-font-size", None) or 8
	for key in [k for k in options if k.startswith(f"{where}-")]:
		options.pop(key)
	return (str(text) if text else None), size


def _css_text(text):
	"""Band text as a CSS `content` value: `[page]` and `[topage]` become page counters."""

	def quoted(part):
		part = " ".join(part.split())
		return '"' + part.replace("\\", "\\\\").replace('"', '\\"') + '"' if part else ""

	parts = re.split(r"(\[page\]|\[topage\])", text)
	out = [{"[page]": "counter(page)", "[topage]": "counter(pages)"}.get(p) or quoted(p) for p in parts]
	return " ".join(p for p in out if p) or '""'


def _page_rule(options, bands):
	"""The `@page` rule: the margins the caller asked for, and the header and footer in them.

	Frappe gives Chrome the same margins, so they agree whichever one Chrome reads."""
	rule = "".join(
		f"margin-{side}:{options[f'margin-{side}']};"
		for side in ("top", "right", "bottom", "left")
		if options.get(f"margin-{side}")
	)
	for where, (text, size) in bands.items():
		box = BOXES[where][0]
		rule += f"@{box}{{content:{_css_text(text)};font-family:sans-serif;font-size:{size}pt;}}"
	return f"<style>@page{{{rule}}}</style>" if rule else ""


def _document(html, style, title=None):
	"""A whole HTML document with a language, a title and the page rule in its head."""
	if not re.search(r"<html[\s>]", html, re.IGNORECASE):
		html = f"<!DOCTYPE html><html><head></head><body>{html}</body></html>"
	if not re.search(r"<head[\s>]", html, re.IGNORECASE):
		html = re.sub(r"(<html[^>]*>)", r"\1<head></head>", html, count=1, flags=re.IGNORECASE)
	tag = re.search(r"<html[^>]*>", html, re.IGNORECASE).group(0)
	if not re.search(r"\slang\s*=", tag, re.IGNORECASE):
		lang = (frappe.local.lang or "en").replace("_", "-")
		html = html.replace(tag, tag[:-1] + f' lang="{lang}">', 1)
	head = ""
	if not re.search(r"<meta[^>]+charset", html, re.IGNORECASE):
		head += '<meta charset="utf-8">'
	if not re.search(r"<title[\s>]", html, re.IGNORECASE):
		title = title or _first_heading(html)
		if title:
			head += f"<title>{frappe.utils.escape_html(title)}</title>"
	head += style
	return re.sub(r"(<head[^>]*>)", lambda m: m.group(1) + head, html, count=1, flags=re.IGNORECASE)


def _first_heading(html):
	match = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, re.IGNORECASE | re.DOTALL)
	return " ".join(strip_html(match.group(1)).split()) if match else None


_HEADING_TAG = re.compile(r"<h([1-6])\b([^>]*)>", re.IGNORECASE)
_ARIA_LEVEL = re.compile(r"""\saria-level\s*=\s*["']?(\d)["']?""", re.IGNORECASE)


def _heading_levels(html):
	"""The headings as a screen reader should hear them (ADR 104 §5): from level 1, never skipping one.

	A PDF often starts at an h2, or puts an h4 under an h2, because the text inside it was written
	for a page around it. The tags stay as they are, so the print looks the same; an `aria-level`
	gives the level Chrome tags and bookmarks."""
	open_levels = []

	def level(match):
		tag, attrs = int(match.group(1)), match.group(2)
		given = _ARIA_LEVEL.search(attrs)
		actual = int(given.group(1)) if given else tag
		while open_levels and open_levels[-1] >= actual:
			open_levels.pop()
		heard = min(len(open_levels) + 1, 6)
		open_levels.append(actual)
		attrs = _ARIA_LEVEL.sub("", attrs)
		if heard != tag:
			attrs += f' aria-level="{heard}"'
		return f"<h{match.group(1)}{attrs}>"

	return _HEADING_TAG.sub(level, html or "")


def _headings(html):
	"""(level, text) of each heading in the HTML, in order, as Chrome tags them: an `aria-level`
	wins over the tag's own."""
	found = []
	for level, attrs, text in re.findall(r"<h([1-6])([^>]*)>(.*?)</h\1>", html, re.IGNORECASE | re.DOTALL):
		aria = re.search(r"""aria-level\s*=\s*["']?(\d)""", attrs)
		found.append((int(aria.group(1) if aria else level), " ".join(strip_html(text).split())))
	return found


# Operators that put something on the page, and those that build a path for a painting one.
_PAINT = {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*", b"n"}
_PATH = {b"m", b"l", b"c", b"v", b"y", b"h", b"re", b"W", b"W*"}
_SINGLE = {b"Do", b"sh", b"INLINE IMAGE"}


def _finish(pdf, password=None, headings=()):
	"""Mark what Chrome left untagged (the margin text, page backgrounds) as an artifact, so a
	PDF/UA checker accepts it and a screen reader skips it; then encrypt if asked."""
	from pypdf import PdfReader, PdfWriter
	from pypdf.generic import ContentStream, NameObject

	writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
	for page in writer.pages:
		contents = page.get_contents()
		if contents is None:
			continue
		stream = ContentStream(contents, writer)
		out, depth, unit = [], 0, None
		for operands, op in stream.operations:
			if op in (b"BDC", b"BMC"):
				# Tagged content starts: anything half-gathered stays as it was.
				out += unit or []
				unit = None
				depth += 1
			elif op == b"EMC":
				depth -= 1
			if depth or (unit is None and op not in (b"BT", *_PATH, *_SINGLE)):
				out.append((operands, op))
				continue
			if unit is None:
				unit = []
			unit.append((operands, op))
			if op in (b"ET", *_PAINT, *_SINGLE):
				out += [([NameObject("/Artifact")], b"BMC"), *unit, ([], b"EMC")]
				unit = None
		out += unit or []
		stream.operations = out
		page.replace_contents(stream)
	_add_metadata(writer)
	_add_bookmarks(writer, headings)
	if password:
		writer.encrypt(password)
	buffer = io.BytesIO()
	writer.write(buffer)
	return buffer.getvalue()


def _add_metadata(writer):
	"""The XMP metadata PDF/UA asks for: the title again, and the PDF/UA identifier. Chrome
	writes only the older document info dictionary."""
	from pypdf.generic import NameObject, StreamObject

	title = frappe.utils.escape_html(str((writer.metadata or {}).get("/Title") or ""))
	xmp = (
		'<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
		'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
		'<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/"'
		' xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/">'
		f'<dc:title><rdf:Alt><rdf:li xml:lang="x-default">{title}</rdf:li></rdf:Alt></dc:title>'
		"<pdfuaid:part>1</pdfuaid:part>"
		"</rdf:Description></rdf:RDF></x:xmpmeta>"
		'<?xpacket end="w"?>'
	)
	stream = StreamObject()
	stream.set_data(xmp.encode("utf-8"))
	stream[NameObject("/Type")] = NameObject("/Metadata")
	stream[NameObject("/Subtype")] = NameObject("/XML")
	writer._root_object[NameObject("/Metadata")] = writer._add_object(stream)


def _add_bookmarks(writer, headings):
	"""A bookmark for each heading, nested by level, at the page Chrome tagged it on.

	Chrome tags every heading as H1-H6 in document order, so the tagged headings and the HTML's
	pair up one to one; their texts come from the HTML. Frappe asks Chrome for bookmarks under a
	name Chrome doesn't know, so Chrome makes none itself. If the two lists differ (a heading
	hidden in print), there are no bookmarks rather than wrong ones."""
	root = writer._root_object.get("/StructTreeRoot")
	if not headings or root is None:
		return
	pages = {page.indirect_reference.idnum: number for number, page in enumerate(writer.pages)}
	tagged = []

	def page_of(node):
		ref = node.get("/Pg")
		if ref is not None:
			return pages.get(ref.idnum)
		for kid in _children(node):
			if hasattr(kid, "get") and (found := page_of(kid)) is not None:
				return found
		return None

	def walk(node):
		for kid in _children(node):
			if not hasattr(kid, "get"):
				continue
			kind = str(kid.get("/S") or "")
			if re.fullmatch(r"/H[1-6]", kind):
				tagged.append(page_of(kid))
			else:
				walk(kid)

	walk(root.get_object())
	if len(tagged) != len(headings) or None in tagged:
		return
	parents = []
	for (level, text), page in zip(headings, tagged, strict=True):
		while parents and parents[-1][0] >= level:
			parents.pop()
		item = writer.add_outline_item(text or "-", page, parent=parents[-1][1] if parents else None)
		parents.append((level, item))


def problems(pdf) -> list[str]:
	"""What keeps a PDF from being read with a screen reader (ADR 104 §5), for tests."""
	from pypdf import PdfReader
	from pypdf.generic import ContentStream

	reader = PdfReader(io.BytesIO(pdf))
	root = reader.trailer["/Root"]
	found = []
	if "/StructTreeRoot" not in root:
		return ["untagged: no structure tree"]
	if not root.get("/Lang"):
		found.append("no language")
	if not (reader.metadata or {}).get("/Title"):
		found.append("no title")

	tags, figures, tables = [], [], []

	def walk(node):
		node = node.get_object() if hasattr(node, "get_object") else node
		if isinstance(node, list):
			for child in node:
				walk(child)
			return
		if not hasattr(node, "get"):
			return
		kind = node.get("/S")
		if kind:
			tags.append(str(kind))
			if kind == "/Figure":
				figures.append(node)
			elif kind == "/Table":
				tables.append(node)
		kids = node.get("/K")
		if kids is not None:
			walk(kids)

	walk(root["/StructTreeRoot"])
	levels = [int(t[2]) for t in tags if re.fullmatch(r"/H[1-6]", t)]
	if levels and (levels[0] != 1 or any(b > a + 1 for a, b in pairwise(levels))):
		found.append(f"heading levels skip: {levels[:12]}")
	headings = sum(1 for t in tags if re.fullmatch(r"/H[1-6]?", t))
	if headings > 1 and not reader.outline:
		found.append(f"{headings} headings but no bookmarks")
	uneven = sum(1 for table in tables if len(set(_row_widths(table))) > 1)
	if uneven:
		found.append(f"{uneven} table(s) with rows of different widths (an empty cell is dropped)")
	missing_alt = sum(1 for f in figures if not f.get("/Alt") and not f.get("/ActualText"))
	if missing_alt:
		found.append(f"{missing_alt} figure(s) without alt text")

	painting = {b"Tj", b"TJ", b"'", b'"', b"Do", b"sh", b"INLINE IMAGE", *_PAINT} - {b"n"}
	for number, page in enumerate(reader.pages, 1):
		contents = page.get_contents()
		if contents is None:
			continue
		depth = loose = 0
		for _operands, op in ContentStream(contents, reader).operations:
			if op in (b"BDC", b"BMC"):
				depth += 1
			elif op == b"EMC":
				depth -= 1
			elif not depth and op in painting:
				loose += 1
		if loose:
			found.append(f"page {number}: {loose} untagged drawing operation(s)")
	return found


def _children(node):
	kids = node.get("/K")
	kids = kids.get_object() if hasattr(kids, "get_object") else kids
	kids = kids if isinstance(kids, list) else [kids] if kids is not None else []
	return [k.get_object() if hasattr(k, "get_object") else k for k in kids]


def _row_widths(table):
	"""How many columns each row of a tagged table spans."""
	widths = []

	def span(cell):
		attrs = cell.get("/A")
		attrs = attrs.get_object() if hasattr(attrs, "get_object") else attrs
		for a in attrs if isinstance(attrs, list) else [attrs] if attrs else []:
			a = a.get_object() if hasattr(a, "get_object") else a
			if hasattr(a, "get") and a.get("/ColSpan"):
				return int(a["/ColSpan"])
		return 1

	def visit(node):
		for kid in _children(node):
			if not hasattr(kid, "get"):
				continue
			if kid.get("/S") == "/TR":
				widths.append(
					sum(
						span(c) for c in _children(kid) if hasattr(c, "get") and c.get("/S") in ("/TH", "/TD")
					)
				)
			elif kid.get("/S") in ("/THead", "/TBody", "/TFoot"):
				visit(kid)

	visit(table)
	return widths
