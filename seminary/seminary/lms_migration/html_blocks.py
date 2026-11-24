"""HTML from another LMS -> EditorJS blocks for a lesson (decisions/108 §2).

Pages, books, assignment text and section summaries arrive as HTML. Lessons are
EditorJS JSON, so the HTML is cut into the block types the lesson editor has:
header, paragraph, list, image, table, codeBox, iframe and upload. Inline markup
is reduced to a short allow-list; anything else is unwrapped to its text.

``resolve(src)`` maps a reference in the HTML (an image, a link, a video) to a
URL on this site, or returns None to leave it as it is. The readers use it to
point package files at the pack's media and to drop the source LMS's
placeholders. Saving the lesson runs ``editorjs_safety`` over the blocks too.
"""

import html as htmllib
import json
import posixpath
import re

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

INLINE = {"b", "strong", "i", "em", "u", "a", "code", "br", "sup", "sub", "mark", "s"}
_INLINE_ALIASES = {"span": None, "font": None, "small": None, "big": None, "abbr": None, "cite": "i"}
_HEADERS = {"h1": 2, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_DROP = {"script", "style", "noscript", "object", "embed", "form", "input", "button", "select", "textarea"}
_MEDIA_TYPES = {"mp4", "mov", "webm", "mkv", "avi", "mp3", "wav", "ogg", "m4a"}
_SAFE_HREF = re.compile(r"^(https?:|mailto:|/|#)", re.I)


def _ext(url):
	return posixpath.splitext((url or "").split("?", 1)[0])[1].lstrip(".").lower()


class _Converter:
	def __init__(self, resolve):
		self.resolve = resolve or (lambda src: None)
		self.blocks = []
		self.missing = []

	# --- inline ---------------------------------------------------------------
	def _url(self, src):
		if not src:
			return src
		found = self.resolve(src.strip())
		return found if found is not None else src.strip()

	def inline(self, node):
		"""Inline HTML of a node's children, reduced to the allow-list."""
		out = []
		for child in node.children:
			if isinstance(child, Comment):
				continue
			if isinstance(child, NavigableString):
				out.append(htmllib.escape(str(child), quote=False))
				continue
			if not isinstance(child, Tag) or child.name in _DROP:
				continue
			name = child.name
			if name in _INLINE_ALIASES:
				name = _INLINE_ALIASES[name]
			if name == "br":
				out.append("<br>")
			elif name == "a":
				href = self._url(child.get("href") or "")
				text = self.inline(child)
				if href and _SAFE_HREF.match(href):
					out.append(f'<a href="{htmllib.escape(href)}">{text or htmllib.escape(href)}</a>')
				else:
					out.append(text)
			elif name in INLINE:
				out.append(f"<{name}>{self.inline(child)}</{name}>")
			else:
				out.append(self.inline(child))
		return "".join(out)

	# --- blocks ---------------------------------------------------------------
	def paragraph(self, text):
		text = re.sub(r"\s+", " ", text).strip()
		text = re.sub(r"^(<br>\s*)+|(\s*<br>)+$", "", text)
		if text:
			self.blocks.append({"type": "paragraph", "data": {"text": text}})

	def image(self, img):
		src = (img.get("src") or "").strip()
		if not src:
			return
		url = self._url(src)
		if not (url.startswith("/") or url.lower().startswith("https://")):
			self.missing.append(src)
			return
		alt = (img.get("alt") or "").strip()
		self.blocks.append(
			{
				"type": "image",
				"data": {
					"url": url,
					"caption": htmllib.escape(alt, quote=False),
					"withBorder": False,
					"withBackground": False,
					"stretched": False,
				},
			}
		)

	def media(self, el):
		src = el.get("src") or next((s.get("src") for s in el.find_all("source") if s.get("src")), "")
		url = self._url(src or "")
		if url and url.startswith("/"):
			self.blocks.append({"type": "upload", "data": {"file_url": url, "file_type": _ext(url) or "mp4"}})
		elif url:
			self.paragraph(f'<a href="{htmllib.escape(url)}">{htmllib.escape(url)}</a>')

	def iframe(self, el):
		src = (el.get("src") or "").strip()
		if src.startswith("//"):
			src = "https:" + src
		if src.lower().startswith("https://"):
			self.blocks.append({"type": "iframe", "data": {"html": src}})

	def list_items(self, el):
		items = []
		for li in el.find_all("li", recursive=False):
			nested = []
			for sub in li.find_all(["ul", "ol"], recursive=False):
				nested.extend(self.list_items(sub))
				sub.extract()
			items.append({"content": re.sub(r"\s+", " ", self.inline(li)).strip(), "items": nested})
		return items

	def table(self, el):
		rows, headings = [], False
		for tr in el.find_all("tr"):
			cells = tr.find_all(["td", "th"], recursive=False)
			if not cells:
				continue
			if not rows and all(c.name == "th" for c in cells):
				headings = True
			rows.append([re.sub(r"\s+", " ", self.inline(c)).strip() for c in cells])
		if rows:
			width = max(len(r) for r in rows)
			rows = [r + [""] * (width - len(r)) for r in rows]
			self.blocks.append({"type": "table", "data": {"withHeadings": headings, "content": rows}})

	def flow(self, node):
		"""Walk block-level content; runs of inline content become paragraphs."""
		run = []

		def flush():
			if run:
				holder = BeautifulSoup("<div></div>", "html.parser").div
				for piece in run:
					holder.append(piece)
				self.paragraph(self.inline(holder))
				run.clear()

		for child in list(node.children):
			if isinstance(child, Comment):
				continue
			if isinstance(child, NavigableString):
				if str(child).strip():
					run.append(child.extract())
				continue
			if not isinstance(child, Tag) or child.name in _DROP:
				continue
			name = child.name
			if name == "img":
				flush()
				self.image(child)
			elif name in ("video", "audio"):
				flush()
				self.media(child)
			elif name == "iframe":
				flush()
				self.iframe(child)
			elif (name in INLINE or name in _INLINE_ALIASES) and not child.find(
				["img", "iframe", "video", "audio", "table", "ul", "ol", "p", "div"]
			):
				run.append(child.extract())
			else:
				flush()
				self.block(child)
		flush()

	def block(self, el):
		name = el.name
		if name in _HEADERS:
			text = re.sub(r"\s+", " ", self.inline(el)).strip()
			if text:
				self.blocks.append({"type": "header", "data": {"text": text, "level": _HEADERS[name]}})
		elif name in ("ul", "ol"):
			items = self.list_items(el)
			if items:
				style = "ordered" if name == "ol" else "unordered"
				self.blocks.append({"type": "list", "data": {"style": style, "items": items}})
		elif name == "table":
			self.table(el)
		elif name == "pre":
			code = el.get_text()
			if code.strip():
				self.blocks.append(
					{"type": "codeBox", "data": {"code": code, "language": "Auto-detect", "theme": ""}}
				)
		elif name == "hr":
			return
		elif name == "p" and not el.find(["img", "iframe", "video", "audio", "table", "ul", "ol"]):
			self.paragraph(self.inline(el))
		else:
			# div, section, blockquote, figure, p holding media, li outside a list...
			self.flow(el)


def to_blocks(html, resolve=None):
	"""Return ``(blocks, missing)``: EditorJS blocks for ``html``, and the image
	references that pointed at nothing in the package."""
	soup = BeautifulSoup(html or "", "html.parser")
	for tag in soup.find_all(_DROP):
		tag.decompose()
	root = soup.body or soup
	conv = _Converter(resolve)
	conv.flow(root)
	return conv.blocks, conv.missing


def content_json(blocks):
	"""Lesson ``content`` for a list of blocks."""
	return json.dumps({"time": 0, "blocks": blocks, "version": "2.29.0"})


def link_paragraph(url, title=None):
	label = htmllib.escape(title or url, quote=False)
	return {"type": "paragraph", "data": {"text": f'<a href="{htmllib.escape(url)}">{label}</a>'}}


def blocks_to_html(blocks):
	"""The reverse, for the Common Cartridge export: a lesson's blocks as HTML.

	Activity, folder and reflection blocks have no HTML of their own; the export
	writes those as their own resources, so here they leave nothing."""
	out = []
	for b in blocks or []:
		if not isinstance(b, dict):
			continue
		t, d = b.get("type"), b.get("data") or {}
		if t == "header":
			level = min(max(int(d.get("level") or 2), 1), 6)
			out.append(f"<h{level}>{d.get('text') or ''}</h{level}>")
		elif t in ("paragraph", "markdown"):
			out.append(f"<p>{d.get('text') or ''}</p>")
		elif t == "list":
			out.append(_list_html(d.get("items") or [], d.get("style") == "ordered"))
		elif t == "image":
			alt = htmllib.escape(htmllib.unescape(re.sub(r"<[^>]+>", "", d.get("caption") or "")))
			out.append(f'<p><img src="{htmllib.escape(d.get("url") or "")}" alt="{alt}"></p>')
		elif t in ("upload", "recordVideo"):
			url = d.get("file_url") or ""
			if _ext(url) in _MEDIA_TYPES:
				tag = "audio" if _ext(url) in ("mp3", "wav", "ogg", "m4a") else "video"
				out.append(f'<p><{tag} controls src="{htmllib.escape(url)}"></{tag}></p>')
			else:
				out.append(
					f'<p><a href="{htmllib.escape(url)}">{htmllib.escape(posixpath.basename(url))}</a></p>'
				)
		elif t == "table":
			rows = d.get("content") or []
			body = []
			for i, row in enumerate(rows):
				cell = "th" if i == 0 and d.get("withHeadings") else "td"
				body.append("<tr>" + "".join(f"<{cell}>{c}</{cell}>" for c in row) + "</tr>")
			out.append("<table>" + "".join(body) + "</table>")
		elif t in ("codeBox", "code"):
			out.append(f"<pre>{htmllib.escape(d.get('code') or '')}</pre>")
		elif t == "iframe":
			out.append(f'<p><iframe src="{htmllib.escape(d.get("html") or "")}"></iframe></p>')
		elif t == "embed":
			src = d.get("source") or d.get("embed") or ""
			out.append(f'<p><a href="{htmllib.escape(src)}">{htmllib.escape(src)}</a></p>')
	return "\n".join(out)


def _list_html(items, ordered):
	tag = "ol" if ordered else "ul"
	parts = []
	for it in items:
		if isinstance(it, str):
			parts.append(f"<li>{it}</li>")
			continue
		inner = _list_html(it.get("items") or [], ordered) if it.get("items") else ""
		parts.append(f"<li>{it.get('content') or ''}{inner}</li>")
	return f"<{tag}>{''.join(parts)}</{tag}>"
