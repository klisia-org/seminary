"""Build a Course Pack manifest from another LMS's course (decisions/108 §1-2).

The readers (``common_cartridge``, ``moodle``) walk their format and call this
builder; it knows only the pack's shape. Files are stored by content hash, so a
file used twice is one File, and references in HTML point at placeholder URLs
the pack importer rewrites to the new Files.

What the readers could not carry is recorded in ``skipped`` with the reason, and
becomes the import report (§4)."""

import hashlib
import html as htmllib
import posixpath
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, strip_html
from frappe.utils.html_utils import sanitize_html

from seminary.seminary import qti

from . import html_blocks

_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]+")

CRITERIA_TYPES = {
	"Quiz": "Quiz",
	"Exam Activity": "Exam",
	"Assignment Activity": "Assignment",
	"Discussion Activity": "Discussion",
}
_SCAC_FIELD = {
	"Quiz": "quiz",
	"Exam Activity": "exam",
	"Assignment Activity": "assignment",
	"Discussion Activity": "discussion",
}
_LESSON_LINK = {
	"Quiz": "assessment_criteria_quiz",
	"Exam Activity": "assessment_criteria_exam",
	"Assignment Activity": "assessment_criteria_assignment",
	"Discussion Activity": "assessment_criteria_discussion",
}
_BLOCK = {
	"Quiz": ("quiz", "quiz"),
	"Exam Activity": ("exam", "exam"),
	"Assignment Activity": ("assignment", "assignment"),
	"Discussion Activity": ("discussionActivity", "discussion"),
}
TITLE_MAX = 140


def short(title, fallback=None):
	t = re.sub(r"\s+", " ", htmllib.unescape(strip_html(title or ""))).strip()
	return t[:TITLE_MAX].rstrip() or fallback or _("Untitled")


def safe_name(name):
	base = posixpath.basename((name or "").replace("\\", "/")) or "file"
	return _UNSAFE_NAME.sub("_", base)[:120] or "file"


class FakeZip:
	"""What the pack importer reads media from: ``read("media/<key>")``."""

	def __init__(self, blobs):
		self.blobs = blobs

	def read(self, name):
		return self.blobs[name.split("media/", 1)[1]]


class PackBuilder:
	def __init__(self, source_format):
		self.source_format = source_format
		self.media, self.blobs, self._by_hash = {}, {}, {}
		self.used = set()
		self.folder = []  # [(path inside the folder, url)]
		self.questions, self.activities = {}, {}
		self.chapters, self.lessons = [], {}
		self.scac = []
		self.rubrics = []
		self.skipped = []
		self.notes = []
		self.criteria = {}
		self.course_title = None
		self.course_code = None
		self._n = 0

	# --- identities and files ----------------------------------------------
	def uid(self, prefix):
		self._n += 1
		return f"migr-{prefix}-{self._n}"

	def add_file(self, name, blob, used=True):
		"""A package file as a placeholder URL the import rewrites, or None when
		this site would refuse the file (a damaged PDF, or one with scripts)."""
		digest = hashlib.sha256(blob).hexdigest()
		url = self._by_hash.get(digest)
		if not url:
			fname = safe_name(name)
			if not self._acceptable(fname, blob):
				return None
			ext = posixpath.splitext(fname)[1].lower()[:10]
			key = f"private/{digest[:16]}{ext}"
			url = f"/private/files/lms-migration-{digest[:16]}{ext}"
			self.media[url] = {"key": key, "sha256": digest, "file_name": fname}
			self.blobs[key] = blob
			self._by_hash[digest] = url
		if used:
			self.used.add(url)
		return url

	def add_folder_file(self, path, blob):
		url = self.add_file(path, blob, used=False)
		if url:
			self.folder.append((path, url))
		return url

	def _acceptable(self, fname, blob):
		"""Frappe refuses a PDF it cannot read or that carries JavaScript, and the
		refusal would end the whole import; such a file is reported instead."""
		if not fname.lower().endswith(".pdf"):
			return True
		from frappe.utils.pdf import pdf_contains_js

		try:
			unsafe = pdf_contains_js(blob)
		except Exception:
			self.skip(fname, _("damaged PDF"))
			return False
		if unsafe:
			self.skip(fname, _("PDF with scripts"))
			return False
		return True

	FOLDER_KEY = "migr-folder"

	def folder_block(self):
		"""A lesson block showing the course folder the import creates."""
		return {"type": "folder", "data": {"folder_ref": self.FOLDER_KEY, "folder": _("Imported files")}}

	def skip(self, title, reason):
		self.skipped.append({"title": short(title), "reason": str(reason)})

	def note(self, title, note):
		self.notes.append({"title": short(title), "note": str(note)})

	# --- outline -----------------------------------------------------------
	def chapter(self, title):
		rec = {
			"src_name": self.uid("chapter"),
			"fields": {"chapter_title": short(title, _("Chapter"))},
			"lessons": [],
		}
		self.chapters.append(rec)
		return rec

	def lesson(self, chapter, title, blocks, scac_links=None):
		src = self.uid("lesson")
		self.lessons[src] = {
			"fields": {
				"lesson_title": short(title, _("Lesson")),
				"content": html_blocks.content_json(blocks),
			},
			"scac_links": scac_links or {},
		}
		chapter["lessons"].append(src)
		return src

	def lti_lesson(self, chapter, title, launch_url, custom=None, description=""):
		"""An LTI link, as an LTI lesson when this site has registered a tool on
		the link's host (decisions/108 §4, amended by 110). Its grade mapping
		does not come across: a weighted row is the instructor's to set."""
		from urllib.parse import urlparse

		from seminary.seminary.doctype.lti_tool.lti_tool import tool_for_url

		launch_url = (launch_url or "").strip()
		if not launch_url:
			self.skip(title, _("external tool (LTI) with no launch URL"))
			return None
		tool = tool_for_url(launch_url)
		if not tool:
			host = urlparse(launch_url).hostname or launch_url
			self.skip(
				title, _("external tool (LTI): register a tool for {0}, then import again").format(host)
			)
			return None
		blocks = [{"type": "paragraph", "data": {"text": htmllib.escape(description)}}] if description else []
		src = self.lesson(chapter, title, blocks)
		lines = [f"{k}={v}" for k, v in (custom or {}).items() if k and "\n" not in f"{k}{v}"]
		self.lessons[src]["fields"].update(
			{"lti_tool": tool, "lti_url": launch_url, "lti_custom": "\n".join(lines)}
		)
		return src

	def html_lesson(self, chapter, title, html, resolve):
		blocks, missing = html_blocks.to_blocks(html, resolve)
		for src in missing:
			self.note(title, _("image not in the package: {0}").format(src))
		if not blocks:
			self.skip(title, _("empty page"))
			return None
		return self.lesson(chapter, title, blocks)

	def activity_lesson(self, chapter, title, doctype, src, intro_blocks=None):
		btype, key = _BLOCK[doctype]
		blocks = [*list(intro_blocks or []), {"type": btype, "data": {key: src}}]
		links = {}
		scac = self._scac_for(doctype, src)
		if scac:
			links[_LESSON_LINK[doctype]] = scac
		return self.lesson(chapter, title, blocks, links)

	# --- grading -----------------------------------------------------------
	def _criteria(self, doctype):
		ctype = CRITERIA_TYPES[doctype]
		if ctype not in self.criteria:
			existing = frappe.get_all(
				"Assessment Criteria", filters={"type": ctype}, pluck="name", order_by="name asc", limit=1
			)
			self.criteria[ctype] = existing[0] if existing else ctype
		return self.criteria[ctype]

	def grade(self, doctype, src, title):
		"""An assessment row for the activity, with no weight: weights are rebuilt
		by hand (§4)."""
		row = {
			"src_name": self.uid("scac"),
			"fields": {"title": short(title), "weight_scac": 0, "extracredit_scac": 0},
			"assesscriteria_scac": self._criteria(doctype),
			_SCAC_FIELD[doctype]: src,
		}
		self.scac.append(row)
		return row["src_name"]

	def _scac_for(self, doctype, src):
		field = _SCAC_FIELD[doctype]
		return next((r["src_name"] for r in self.scac if r.get(field) == src), None)

	# --- activities --------------------------------------------------------
	def rich(self, html, resolve):
		"""Text Editor HTML: placeholders resolved, then sanitised."""
		if not html:
			return ""

		def swap(match):
			found = resolve(htmllib.unescape(match.group(2)))
			return f'{match.group(1)}"{htmllib.escape(found)}"' if found else match.group(0)

		html = re.sub(r"""(\b(?:src|href)=)["']([^"']+)["']""", swap, html, flags=re.I)
		return sanitize_html(html)

	def quiz(self, title, items, resolve, settings=None, graded=True):
		"""A quiz from parsed QTI items (``qti.Item``). Choice and short-answer
		items make the quiz; essays make an exam beside it, as seminary keeps
		them apart. Returns ``[(doctype, src)]`` for what was created."""
		title = short(title, _("Quiz"))
		quiz_rows, exam_rows = [], []
		for item in items:
			label = f"{title}: {item.label()}"
			reason = item.skip
			if not reason and item.kind == qti.CHOICE:
				reason = qti.check_choice(item)
			if not reason and not strip_html(item.html).strip() and "<img" not in item.html.lower():
				reason = _("no question text")
			if reason:
				self.skip(label, reason)
				continue
			html = self.rich(item.html, resolve)
			qsrc = self.uid("question")
			if item.kind == qti.ESSAY:
				self.questions[qsrc] = {"doctype": "Open Question", "fields": {"question": html}}
				exam_rows.append({"fields": {"points": flt(item.points) or 1}, "question": qsrc})
				continue
			rec = {"doctype": "Question", "fields": {"question": html}}
			if item.kind == qti.CHOICE:
				rec["fields"].update(type="Choices", multiple=1 if item.multiple else 0)
				rec["choices"] = [{"option": t, "is_correct": 1 if c else 0} for t, c in item.options]
			else:
				rec["fields"].update(type="User Input")
				rec["accepted_answers"] = [{"answer": a} for a in item.answers]
			self.questions[qsrc] = rec
			quiz_rows.append({"fields": {"points": max(1, round(flt(item.points) or 1))}, "question": qsrc})

		settings = settings or {}
		made = []
		if quiz_rows:
			src = self.uid("quiz")
			fields = {"title": title, "shuffle_questions": cint(settings.get("shuffle"))}
			if cint(settings.get("attempts")) > 0:
				fields["max_attempts"] = cint(settings["attempts"])
			if cint(settings.get("duration")) > 0:
				fields["duration"] = cint(settings["duration"])
			if settings.get("grading_basis"):
				fields["grading_basis"] = settings["grading_basis"]
			self.activities[src] = {"doctype": "Quiz", "fields": fields, "questions": quiz_rows}
			made.append(("Quiz", src))
		if exam_rows:
			src = self.uid("exam")
			etitle = short(f"{title} ({_('written')})") if quiz_rows else title
			fields = {"title": etitle}
			if cint(settings.get("duration")) > 0:
				fields["duration"] = cint(settings["duration"]) / 60
			self.activities[src] = {"doctype": "Exam Activity", "fields": fields, "questions": exam_rows}
			made.append(("Exam Activity", src))
			if quiz_rows:
				self.note(title, _("its essay questions became the exam '{0}'").format(etitle))
		if not made:
			self.skip(title, _("no question could be imported"))
		if graded:
			for doctype, src in made:
				self.grade(doctype, src, self.activities[src]["fields"]["title"])
		return made

	def assignment(self, title, html, resolve, submission="Document", graded=True):
		src = self.uid("assignment")
		title = short(title, _("Assignment"))
		self.activities[src] = {
			"doctype": "Assignment Activity",
			"fields": {
				"title": title,
				"question": self.rich(html, resolve),
				"type": submission
				if submission in ("PDF", "Document", "Image", "URL", "Text")
				else "Document",
				"grade_assignment": 1 if graded else 0,
			},
		}
		if graded:
			self.grade("Assignment Activity", src, title)
		return src

	def discussion(self, title, html, resolve, graded=False):
		src = self.uid("discussion")
		title = short(title, _("Discussion"))
		self.activities[src] = {
			"doctype": "Discussion Activity",
			"fields": {"discussion_name": title, "prompt": self.rich(html, resolve)},
		}
		if graded:
			self.grade("Discussion Activity", src, title)
		return src

	def rubric(self, doctype, src, title, criteria):
		"""``criteria``: ``[{title, description, points, ratings: [(points, text)]}]``."""
		if criteria:
			self.rubrics.append({"doctype": doctype, "src": src, "title": short(title), "criteria": criteria})

	# --- manifest ----------------------------------------------------------
	def _folder_tree(self):
		root = []
		dirs = {"": root}
		for path, url in sorted(self.folder):
			if url in self.used:
				continue
			parts = [p for p in path.split("/") if p]
			if not parts:
				continue
			parent = ""
			for part in parts[:-1]:
				key = f"{parent}/{part}"
				if key not in dirs:
					node = {"type": "folder", "file_name": safe_name(part), "children": []}
					dirs[parent].append(node)
					dirs[key] = node["children"]
				parent = key
			dirs[parent].append({"type": "file", "file_name": safe_name(parts[-1]), "media": url})
		return root

	def manifest(self):
		folders = {}
		tree = self._folder_tree()
		if tree:
			folders[self.FOLDER_KEY] = {"foldername": _("Imported files"), "scope": "Course", "files": tree}
		media = {
			u: m for u, m in self.media.items() if u in self.used or any(u == f for _p, f in self.folder)
		}
		return {
			"pack_format_version": 1,
			"source": {
				"course": self.course_title,
				"course_code": self.course_code,
				"title": self.course_title,
			},
			"institution_deps": {
				"assessment_criteria": {name: {"type": ctype} for ctype, name in self.criteria.items()},
			},
			"media": media,
			"questions": self.questions,
			"activities": self.activities,
			"folders": folders,
			"chapters": self.chapters,
			"lessons": self.lessons,
			"scac": self.scac,
			"competencies": [],
		}
