"""Read an IMS Common Cartridge 1.1-1.3 (decisions/108 §1-2).

Canvas, Blackboard, Brightspace, Schoology and Moodle export one. The
organisation's modules become chapters and their items lessons; quizzes,
assignments and discussion topics become activities, each with a lesson that
shows it. Canvas adds its own files beside the standard ones (quiz settings, the
full QTI, assignment settings, rubrics) and they are read when present.

Resources no module points at are not lost: pages and activities go into a last
chapter, and the remaining files into the course folder."""

import posixpath
import re
from urllib.parse import unquote

from frappe import _
from frappe.utils import cint, flt

from seminary.seminary import qti

from . import html_blocks
from .archive import desc, first, kid, kid_text, kids, ln, text
from .builder import PackBuilder, short

_PLACEHOLDER_LINK = re.compile(r"^\$(WIKI_REFERENCE|CANVAS_OBJECT_REFERENCE|CANVAS_COURSE_REFERENCE)\$", re.I)
_FILEBASE = re.compile(r"^\$IMS[-_]CC[-_]FILEBASE\$/?", re.I)


class Resource:
	def __init__(self, el):
		self.id = el.get("identifier")
		self.type = (el.get("type") or "").lower()
		self.href = el.get("href") or ""
		self.files = [f.get("href") for f in kids(el, "file") if f.get("href")]
		self.deps = [d.get("identifierref") for d in kids(el, "dependency") if d.get("identifierref")]
		if self.href and self.href not in self.files:
			self.files.insert(0, self.href)

	def main(self):
		return self.href or (self.files[0] if self.files else "")


class Reader:
	def __init__(self, archive):
		self.a = archive
		self.b = PackBuilder("Common Cartridge")
		self.resources = {}
		self.done = set()
		self.rubrics = {}
		self._loose = None

	# --- references in HTML ---------------------------------------------------
	def resolver(self, base):
		def resolve(src):
			if not src:
				return None
			path = unquote(src.split("#", 1)[0].split("?", 1)[0])
			if _PLACEHOLDER_LINK.match(path):
				return "#"
			if _FILEBASE.match(path):
				path = "web_resources/" + _FILEBASE.sub("", path)
			elif re.match(r"^[a-z][a-z0-9+.-]*:", path, re.I) or path.startswith("//"):
				return None
			else:
				path = posixpath.normpath(posixpath.join(posixpath.dirname(base), path)).lstrip("/")
			if self.a.has(path):
				return self.b.add_file(path, self.a.read(path))
			return None

		return resolve

	def html_of(self, path):
		raw = self.a.read(path)
		if raw is None:
			return ""
		return raw.decode("utf-8", errors="replace")

	# --- the cartridge ----------------------------------------------------------
	def read(self):
		root = self.a.xml("imsmanifest.xml")
		if root is None:
			raise_bad()
		for el in desc(root, "resource"):
			r = Resource(el)
			if r.id:
				self.resources[r.id] = r
		self._course_meta(root)
		self._read_rubrics()

		org = first(root, "organization")
		top = kids(org, "item") if org is not None else []
		# Most exporters wrap the modules in one root item with no resource.
		if len(top) == 1 and not top[0].get("identifierref") and kids(top[0], "item"):
			top = kids(top[0], "item")
		for item in top:
			if kids(item, "item"):
				chapter = self.b.chapter(kid_text(item, "title"))
				for leaf in self._leaves(item):
					self.item(chapter, leaf)
			elif item.get("identifierref"):
				self.item(self.loose(), item)
		self._unplaced()
		self._files()
		return self.b

	def _course_meta(self, root):
		settings = self.a.xml("course_settings/course_settings.xml")
		if settings is not None:
			self.b.course_title = kid_text(settings, "title") or None
			self.b.course_code = kid_text(settings, "course_code") or None
		if not self.b.course_title:
			general = first(first(root, "metadata"), "general")
			self.b.course_title = text(first(first(general, "title"), "string")) or None

	def _read_rubrics(self):
		root = self.a.xml("course_settings/rubrics.xml")
		for rub in kids(root, "rubric"):
			criteria = []
			for crit in desc(rub, "criterion"):
				ratings = [
					(flt(kid_text(r, "points")), kid_text(r, "description")) for r in desc(crit, "rating")
				]
				criteria.append(
					{
						"title": kid_text(crit, "description"),
						"description": kid_text(crit, "long_description"),
						"points": flt(kid_text(crit, "points")),
						"ratings": ratings,
					}
				)
			self.rubrics[rub.get("identifier")] = criteria

	def _leaves(self, item):
		for child in kids(item, "item"):
			if kids(child, "item"):
				yield from self._leaves(child)
			else:
				yield child

	def loose(self):
		if self._loose is None:
			self._loose = self.b.chapter(_("Course content"))
		return self._loose

	# --- one module item --------------------------------------------------------
	def item(self, chapter, el):
		ref = el.get("identifierref")
		title = kid_text(el, "title")
		if not ref:
			return  # a text heading inside a module
		r = self.resources.get(ref)
		if r is None:
			self.b.skip(title, _("the item points at nothing in the package"))
			return
		self.resource(chapter, r, title)

	def resource(self, chapter, r, title=None):
		if r.id in self.done:
			return
		self.done.add(r.id)
		t = r.type
		if t.startswith("imsqti_item"):
			return  # a question bank's items, not an assessment of the course
		if "imsbasiclti" in t or "lti" in t.split("/")[0]:
			self.b.skip(title or r.id, _("external tool (LTI)"))
		elif "imswl" in t:
			self.weblink(chapter, r, title)
		elif "imsdt" in t:
			self.topic(chapter, r, title)
		elif "imsqti" in t or t.endswith("/assessment"):
			self.assessment(chapter, r, title)
		elif "assignment" in t:
			self.cc_assignment(chapter, r, title)
		elif self._canvas_assignment_settings(r):
			self.canvas_assignment(chapter, r, title)
		elif t == "webcontent" or "learning-application-resource" in t:
			self.webcontent(chapter, r, title)
		else:
			self.b.skip(title or r.id, _("unsupported item ({0})").format(r.type))

	def webcontent(self, chapter, r, title):
		path = r.main()
		if not path or not self.a.has(path):
			self.b.skip(title or r.id, _("the file is not in the package"))
			return
		if path.lower().startswith("wiki_content/") and path.lower().endswith(".json"):
			self.b.skip(title or path, _("a page made with Canvas's block editor"))
			return
		if path.lower().endswith((".html", ".htm")):
			html = self.html_of(path)
			title = title or _html_title(html) or posixpath.basename(path)
			self.b.html_lesson(chapter, title, html, self.resolver(path))
			return
		url = self.b.add_file(path, self.a.read(path))
		name = posixpath.basename(path)
		if not url:
			return
		ext = posixpath.splitext(name)[1].lstrip(".").lower()
		self.b.lesson(
			chapter, title or name, [{"type": "upload", "data": {"file_url": url, "file_type": ext}}]
		)

	def weblink(self, chapter, r, title):
		root = self.a.xml(r.main())
		url_el = first(root, "url")
		href = url_el.get("href") if url_el is not None else ""
		title = title or kid_text(root, "title") or href
		if not href:
			self.b.skip(title, _("web link with no address"))
			return
		self.b.lesson(chapter, title, [html_blocks.link_paragraph(href, title)])

	def topic(self, chapter, r, title):
		root = self.a.xml(r.main())
		if root is None:
			self.b.skip(title or r.id, _("discussion topic could not be read"))
			return
		title = title or kid_text(root, "title")
		graded = False
		for dep in r.deps:
			meta = self._dep_xml(dep, "topicMeta")
			if meta is not None:
				if kid_text(meta, "type").lower() == "announcement":
					self.b.skip(title, _("announcement, left out on purpose"))
					return
				graded = kid(meta, "assignment") is not None
		src = self.b.discussion(title, text_html(kid(root, "text")), self.resolver(r.main()), graded=graded)
		self.b.activity_lesson(chapter, title, "Discussion Activity", src)

	def _dep_xml(self, dep_id, root_name):
		dep = self.resources.get(dep_id)
		if not dep:
			return None
		for f in dep.files:
			if f.lower().endswith(".xml"):
				root = self.a.xml(f)
				if root is not None and ln(root.tag) == root_name:
					return root
		return None

	# --- quizzes ------------------------------------------------------------------
	def assessment(self, chapter, r, title):
		qti_path, meta = r.main(), None
		folder = posixpath.dirname(r.main())
		meta_path = f"{folder}/assessment_meta.xml" if folder else "assessment_meta.xml"
		candidates = [meta_path] + [
			f for d in r.deps for f in (self.resources.get(d).files if d in self.resources else [])
		]
		for path in candidates:
			if path.endswith("assessment_meta.xml") and self.a.has(path):
				meta = self.a.xml(path)
			if path.startswith("non_cc_assessments/") and self.a.has(path):
				qti_path = path  # Canvas's full QTI keeps every question type
		root = self.a.xml(qti_path)
		if root is None:
			self.b.skip(title or r.id, _("quiz could not be read"))
			return
		items = qti.parse_document(qti_path, root)
		assessment = first(root, "assessment")
		title = (
			title
			or (meta is not None and kid_text(meta, "title"))
			or (assessment.get("title") if assessment is not None else None)
		)
		settings, graded = {}, True
		if meta is not None:
			settings["duration"] = cint(flt(kid_text(meta, "time_limit")) * 60)
			settings["attempts"] = cint(kid_text(meta, "allowed_attempts"))
			settings["shuffle"] = kid_text(meta, "shuffle_answers").lower() == "true"
			policy = kid_text(meta, "scoring_policy").lower()
			settings["grading_basis"] = "Latest Attempt" if policy == "keep_latest" else "Highest Score"
			graded = kid_text(meta, "quiz_type").lower() not in ("practice_quiz", "survey")
		else:
			for f in desc(root, "qtimetadatafield"):
				if kid_text(f, "fieldlabel") == "cc_maxattempts":
					value = kid_text(f, "fieldentry")
					settings["attempts"] = 0 if value.lower() == "unlimited" else cint(value)
		for item in items:
			item.source = qti_path
		made = self.b.quiz(title, items, self._qti_resolver(qti_path), settings, graded=graded)
		for doctype, src in made:
			self.b.activity_lesson(chapter, self.b.activities[src]["fields"]["title"], doctype, src)

	def _qti_resolver(self, base):
		resolve = self.resolver(base)

		def qti_resolve(src):
			found = resolve(src)
			if found is None and not re.match(r"^[a-z][a-z0-9+.-]*:", src, re.I):
				# Canvas writes quiz images relative to the cartridge root.
				path = posixpath.normpath(unquote(src.split("?", 1)[0])).lstrip("/")
				if self.a.has(path):
					return self.b.add_file(path, self.a.read(path))
			return found

		return qti_resolve

	# --- assignments ----------------------------------------------------------------
	def cc_assignment(self, chapter, r, title):
		"""The Common Cartridge 1.3 assignment extension."""
		root = self.a.xml(r.main())
		if root is None or ln(root.tag) != "assignment":
			if self._canvas_assignment_settings(r):
				self.canvas_assignment(chapter, r, title)
			else:
				self.b.skip(title or r.id, _("assignment could not be read"))
			return
		title = title or kid_text(root, "title")
		gradable = kid(root, "gradable")
		graded = gradable is None or text(gradable).lower() != "false"
		formats = [f.get("type", "").lower() for f in desc(root, "format")]
		src = self.b.assignment(
			title, text_html(kid(root, "text")), self.resolver(r.main()), _submission(formats), graded=graded
		)
		canvas = kid(kid(root, "extensions"), "assignment")
		rubric = kid_text(canvas, "rubric_identifierref")
		if rubric and rubric in self.rubrics:
			self.b.rubric("Assignment Activity", src, title, self.rubrics[rubric])
		self.b.activity_lesson(chapter, title, "Assignment Activity", src)

	def _canvas_assignment_settings(self, r):
		for f in r.files:
			if f.endswith("assignment_settings.xml") and self.a.has(f):
				return f
		return None

	def canvas_assignment(self, chapter, r, title):
		settings = self.a.xml(self._canvas_assignment_settings(r))
		html_path = next((f for f in r.files if f.lower().endswith((".html", ".htm"))), None)
		html = self.html_of(html_path) if html_path else ""
		title = title or kid_text(settings, "title") or _html_title(html)
		kinds = [k.strip() for k in kid_text(settings, "submission_types").split(",")]
		formats = []
		for k in kinds:
			formats.append(
				{"online_upload": "file", "online_text_entry": "text", "online_url": "url"}.get(k, k)
			)
		graded = kid_text(settings, "grading_type").lower() != "not_graded" and "not_graded" not in kinds
		body = _body(html)
		src = self.b.assignment(
			title, body, self.resolver(html_path or r.main()), _submission(formats), graded
		)
		rubric = kid_text(settings, "rubric_identifierref")
		if rubric and rubric in self.rubrics:
			self.b.rubric("Assignment Activity", src, title, self.rubrics[rubric])
		self.b.activity_lesson(chapter, title, "Assignment Activity", src)

	# --- what no module points at -----------------------------------------------------
	def _unplaced(self):
		chapter = None
		for r in self.resources.values():
			if r.id in self.done:
				continue
			main = r.main().lower()
			if r.type.startswith("imsqti_item"):
				continue
			activity = any(k in r.type for k in ("imsdt", "imsqti", "assignment")) or bool(
				self._canvas_assignment_settings(r)
			)
			page = r.type == "webcontent" and main.startswith("wiki_content/") and main.endswith(".html")
			if not (activity or page):
				continue
			if self._is_dependency(r.id):
				continue
			if chapter is None:
				chapter = self.b.chapter(_("Not in a module"))
			self.resource(chapter, r)

	def _is_dependency(self, rid):
		return any(rid in r.deps for r in self.resources.values() if r.id != rid)

	def _files(self):
		for name in self.a.names():
			if name.startswith("web_resources/"):
				self.b.add_folder_file(name[len("web_resources/") :], self.a.read(name))


def text_html(el):
	"""The HTML of a ``<text texttype=...>`` element."""
	if el is None:
		return ""
	raw = text(el)
	if "html" in (el.get("texttype") or "").lower():
		return raw
	import html as htmllib

	return "<p>" + htmllib.escape(raw).replace("\n", "<br>") + "</p>"


def _submission(formats):
	if "file" in formats:
		return "Document"
	if "url" in formats:
		return "URL"
	if "text" in formats or "html" in formats:
		return "Text"
	return "Document"


def _html_title(html):
	m = re.search(r"<title>(.*?)</title>", html or "", re.I | re.S)
	return short(m.group(1)) if m else None


def _body(html):
	m = re.search(r"<body[^>]*>(.*)</body>", html or "", re.I | re.S)
	return m.group(1) if m else (html or "")


def raise_bad():
	import frappe

	frappe.throw(_("The cartridge's imsmanifest.xml could not be read."))


def read(archive):
	return Reader(archive).read()
