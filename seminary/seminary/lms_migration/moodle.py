"""Read a Moodle 5.0–5.3 course backup (.mbz) (decisions/108 §1-2).

A backup is a gzipped tar of XML: ``moodle_backup.xml`` lists the sections and
activities, each activity has its own directory, ``questions.xml`` holds the
question banks and ``files.xml`` indexes the files, which are stored by content
hash under ``files/``. Moodle's backup format changes between releases, so only
the releases checked against Moodle's backup code are read (5.0–5.3, which differ
only by fields this reader ignores); anything else is refused with its release
named (§1).

Sections become chapters. Pages, books, labels, URLs and files become lessons;
assignments, forums and quizzes become activities with a lesson each. The
announcements forum is left out: it is the course's notice board, not content.
"""

import html as htmllib
import posixpath
import re
from urllib.parse import unquote

import frappe
from frappe import _
from frappe.utils import cint, flt, strip_html

from seminary.seminary import qti

from . import html_blocks
from .archive import desc, first, kid, kid_text, kids, text
from .builder import PackBuilder, short

SUPPORTED_RELEASES = ("5.0", "5.1", "5.2", "5.3")
NULL = "$@NULL@$"
_PLUGINFILE = "@@PLUGINFILE@@"
_MOODLE_LINK = re.compile(r"^\$@[A-Z]+\*?[^@]*@\$")

_QTYPE_SKIP = {
	"match": "matching",
	"randomsamatch": "matching",
	"ddmatch": "matching",
	"numerical": "numeric",
	"calculated": "numeric",
	"calculatedsimple": "numeric",
	"calculatedmulti": "numeric",
	"multianswer": "several blanks",
	"ddwtos": "several blanks",
	"gapselect": "several drop-downs",
	"ddimageortext": "hot spot",
	"ddmarker": "hot spot",
	"ordering": "ordering",
	"description": "text only, no question",
	"random": "random question from a category",
}

_UNSUPPORTED_MODULES = {
	"scorm": "SCORM package",
	"h5pactivity": "H5P",
	"hvp": "H5P",
	"workshop": "workshop",
	"lesson": "Moodle lesson",
	"glossary": "glossary",
	"choice": "choice",
	"feedback": "feedback",
	"survey": "survey",
	"wiki": "wiki",
	"data": "database",
	"chat": "chat",
	"bigbluebuttonbn": "BigBlueButton room",
	"imscp": "IMS content package",
}


def release_branch(release):
	"""``"5.3"`` for a release string such as ``"5.3.1+ (Build: 20261124)"``."""
	m = re.match(r"^\s*(\d+)\.(\d+)", release or "")
	return f"{m.group(1)}.{m.group(2)}" if m else ""


def _v(el, name, default=""):
	value = kid_text(el, name, default)
	return default if value == NULL else value


class Reader:
	def __init__(self, archive):
		self.a = archive
		self.b = PackBuilder("Moodle")
		self.files = {}  # (contextid, component, filearea, itemid) -> {"/path/name": contenthash}
		self.entries = {}  # question bank entry id -> [(version, question element)]
		self.sections = {}  # section id -> section.xml root
		self.subsections = {}  # mod_subsection instance id -> section id

	# --- the backup -------------------------------------------------------------
	def read(self):
		root = self.a.xml("moodle_backup.xml")
		if root is None:
			frappe.throw(_("The backup's moodle_backup.xml could not be read."))
		info = first(root, "information")
		release = _v(info, "moodle_release")
		if release_branch(release) not in SUPPORTED_RELEASES:
			frappe.throw(
				_(
					"This backup comes from Moodle {0}. Only backups from Moodle {1} to {2} can be imported: "
					"upgrade Moodle first, or export the course as a Common Cartridge."
				).format(
					release.split(" (")[0] or _("an unknown release"),
					SUPPORTED_RELEASES[0],
					SUPPORTED_RELEASES[-1],
				),
				title=_("Moodle release not supported"),
			)
		self.b.course_title = _v(info, "original_course_fullname") or None
		self.b.course_code = _v(info, "original_course_shortname") or None
		self._index_files()
		self._index_questions()

		contents = first(info, "contents")
		activities = {}
		for act in desc(first(contents, "activities"), "activity"):
			activities[_v(act, "moduleid")] = act
		section_list = []
		for sec in desc(first(contents, "sections"), "section"):
			sroot = self.a.xml(f"{_v(sec, 'directory')}/section.xml")
			if sroot is None:
				continue
			self.sections[sroot.get("id") or _v(sec, "sectionid")] = sroot
			if _v(sroot, "component") == "mod_subsection":
				self.subsections[_v(sroot, "itemid")] = sroot.get("id")
				continue
			section_list.append(sroot)
		section_list.sort(key=lambda s: cint(_v(s, "number")))

		for sroot in section_list:
			number = cint(_v(sroot, "number"))
			name = _v(sroot, "name") or (_("General") if number == 0 else _("Topic {0}").format(number))
			chapter = self.b.chapter(name)
			summary = _v(sroot, "summary")
			if html_blocks.to_blocks(summary)[0]:
				resolve = self.resolver(None, "course", "section", sroot.get("id"))
				self.b.html_lesson(chapter, name, summary, resolve)
			self._sequence(chapter, sroot, activities)
			if not chapter["lessons"]:
				self.b.chapters.remove(chapter)
		return self.b

	def _sequence(self, chapter, sroot, activities):
		for cmid in [c for c in _v(sroot, "sequence").split(",") if c.strip()]:
			act = activities.get(cmid.strip())
			if act is None:
				continue
			modname = _v(act, "modulename")
			if modname == "subsection":
				self._subsection(chapter, act, activities)
				continue
			try:
				self.module(chapter, act)
			except frappe.ValidationError:
				raise
			except Exception:
				frappe.log_error(title="lms_migration: Moodle activity", message=frappe.get_traceback())
				self.b.skip(_v(act, "title"), _("could not be read"))

	def _subsection(self, chapter, act, activities):
		"""A 4.5+ subsection: its activities join the section it sits in."""
		root = self._activity_xml(act, "subsection")
		instance = first(root, "subsection")
		section_id = self.subsections.get(instance.get("id") if instance is not None else "")
		sroot = self.sections.get(section_id)
		if sroot is not None:
			self._sequence(chapter, sroot, activities)

	# --- files ------------------------------------------------------------------
	def _index_files(self):
		root = self.a.xml("files.xml")
		for f in kids(root, "file"):
			name = _v(f, "filename")
			if not name or name == ".":
				continue
			key = (_v(f, "contextid"), _v(f, "component"), _v(f, "filearea"), _v(f, "itemid") or "0")
			path = (_v(f, "filepath") or "/") + name
			self.files.setdefault(key, {})[path] = (
				_v(f, "contenthash"),
				_v(f, "mimetype"),
				cint(_v(f, "sortorder")),
			)

	def _blob(self, contenthash):
		return self.a.read(f"files/{contenthash[:2]}/{contenthash}") if contenthash else None

	def area(self, contextid, component, filearea, itemid="0"):
		return self.files.get((str(contextid or ""), component, filearea, str(itemid or "0")), {})

	def resolver(self, contextid, component, filearea, itemid="0"):
		"""Resolve @@PLUGINFILE@@ references in one file area."""

		def resolve(src):
			if _MOODLE_LINK.match(src or ""):
				return "#"
			if not (src or "").startswith(_PLUGINFILE):
				return None
			path = "/" + unquote(src[len(_PLUGINFILE) :].split("?", 1)[0]).lstrip("/")
			found = None
			if contextid is not None:
				found = self.area(contextid, component, filearea, itemid).get(path)
			else:  # section summaries: the course context, whatever its id
				for (_ctx, comp, area, item), files in self.files.items():
					if comp == component and area == filearea and item == str(itemid) and path in files:
						found = files[path]
						break
			blob = self._blob(found[0]) if found else None
			if blob is None:
				return None
			return self.b.add_file(posixpath.basename(path), blob)

		return resolve

	# --- one activity -------------------------------------------------------------------
	def _activity_xml(self, act, modname):
		return self.a.xml(f"{_v(act, 'directory')}/{modname}.xml")

	def module(self, chapter, act):
		modname = _v(act, "modulename")
		title = _v(act, "title")
		mod = self.a.xml(f"{_v(act, 'directory')}/module.xml")
		if mod is not None and _v(mod, "deletioninprogress") == "1":
			return
		if modname in _UNSUPPORTED_MODULES:
			self.b.skip(title, _(_UNSUPPORTED_MODULES[modname]))
			return
		handler = getattr(self, f"mod_{modname}", None)
		root = self._activity_xml(act, modname)
		if handler is None or root is None:
			self.b.skip(title, _("Moodle activity type {0}").format(modname))
			return
		ctx = root.get("contextid")
		handler(chapter, title, kid(root, modname), ctx)

	def intro_blocks(self, el, ctx, component):
		blocks, _missing = html_blocks.to_blocks(_v(el, "intro"), self.resolver(ctx, component, "intro"))
		return blocks

	def mod_page(self, chapter, title, el, ctx):
		self.b.html_lesson(
			chapter, _v(el, "name") or title, _v(el, "content"), self.resolver(ctx, "mod_page", "content")
		)

	def mod_label(self, chapter, title, el, ctx):
		intro = _v(el, "intro")
		name = _v(el, "name") or title
		self.b.html_lesson(
			chapter, short(name, _("Note"))[:80], intro, self.resolver(ctx, "mod_label", "intro")
		)

	def mod_book(self, chapter, title, el, ctx):
		chapters = sorted(desc(first(el, "chapters"), "chapter"), key=lambda c: cint(_v(c, "pagenum")))
		shown = [c for c in chapters if _v(c, "hidden") != "1"]
		if not shown:
			self.b.skip(title, _("empty book"))
			return
		book = _v(el, "name") or title
		for c in shown:
			name = _v(c, "title")
			label = f"{book}: {name}" if len(shown) > 1 else (name or book)
			resolve = self.resolver(ctx, "mod_book", "chapter", c.get("id"))
			self.b.html_lesson(chapter, label, _v(c, "content"), resolve)

	def mod_url(self, chapter, title, el, ctx):
		url = _v(el, "externalurl")
		name = _v(el, "name") or title
		if not url:
			self.b.skip(name, _("web link with no address"))
			return
		blocks = [*self.intro_blocks(el, ctx, "mod_url"), html_blocks.link_paragraph(url, name)]
		self.b.lesson(chapter, name, blocks)

	def mod_lti(self, chapter, title, el, ctx):
		"""An external tool. A site-level tool type keeps its URL in `ltitype`."""
		name = _v(el, "name") or title
		launch = _v(el, "securetoolurl") or _v(el, "toolurl") or text(first(el, "baseurl"))
		custom = {}
		for line in (_v(el, "instructorcustomparameters") or "").splitlines():
			if "=" in line:
				key, value = line.split("=", 1)
				custom[key.strip()] = value.strip()
		description = " ".join(strip_html(_v(el, "intro") or "").split())[:2000]
		self.b.lti_lesson(chapter, name, launch, custom, description)

	def mod_resource(self, chapter, title, el, ctx):
		name = _v(el, "name") or title
		files = self.area(ctx, "mod_resource", "content")
		if not files:
			self.b.skip(name, _("the file is not in the backup"))
			return
		path, (contenthash, mimetype, _order) = max(sorted(files.items()), key=lambda kv: kv[1][2])
		blob = self._blob(contenthash)
		if blob is None:
			self.b.skip(name, _("the file is not in the backup"))
			return
		url = self.b.add_file(posixpath.basename(path), blob)
		if not url:
			return
		if (mimetype or "").startswith("image/"):
			block = {
				"type": "image",
				"data": {
					"url": url,
					"caption": htmllib.escape(name),
					"withBorder": False,
					"withBackground": False,
					"stretched": False,
				},
			}
		else:
			ext = posixpath.splitext(path)[1].lstrip(".").lower()
			block = {"type": "upload", "data": {"file_url": url, "file_type": ext}}
		self.b.lesson(chapter, name, [*self.intro_blocks(el, ctx, "mod_resource"), block])

	def mod_folder(self, chapter, title, el, ctx):
		name = _v(el, "name") or title
		files = self.area(ctx, "mod_folder", "content")
		added = 0
		for path, (contenthash, _mime, _order) in sorted(files.items()):
			blob = self._blob(contenthash)
			if blob is not None and self.b.add_folder_file(f"{short(name)}/{path.lstrip('/')}", blob):
				added += 1
		if not added:
			self.b.skip(name, _("empty folder"))
			return
		blocks = [*self.intro_blocks(el, ctx, "mod_folder"), self.b.folder_block()]
		self.b.lesson(chapter, name, blocks)

	def mod_assign(self, chapter, title, el, ctx):
		name = _v(el, "name") or title
		enabled = set()
		for pc in desc(el, "plugin_config"):
			if (
				_v(pc, "subtype") == "assignsubmission"
				and _v(pc, "name") == "enabled"
				and _v(pc, "value") == "1"
			):
				enabled.add(_v(pc, "plugin"))
		submission = "Document" if "file" in enabled else ("Text" if "onlinetext" in enabled else "Document")
		graded = flt(_v(el, "grade")) != 0
		resolve = self.resolver(ctx, "mod_assign", "intro")
		src = self.b.assignment(name, _v(el, "intro"), resolve, submission, graded=graded)
		self.b.activity_lesson(chapter, name, "Assignment Activity", src)

	def mod_forum(self, chapter, title, el, ctx):
		name = _v(el, "name") or title
		if _v(el, "type") == "news":
			self.b.skip(name, _("announcements forum, left out on purpose"))
			return
		graded = cint(_v(el, "assessed")) > 0 or flt(_v(el, "grade_forum")) > 0
		resolve = self.resolver(ctx, "mod_forum", "intro")
		src = self.b.discussion(name, _v(el, "intro"), resolve, graded=graded)
		self.b.activity_lesson(chapter, name, "Discussion Activity", src)

	def mod_quiz(self, chapter, title, el, ctx):
		name = _v(el, "name") or title
		items = []
		instances = sorted(
			desc(first(el, "question_instances"), "question_instance"), key=lambda q: cint(_v(q, "slot"))
		)
		for qi in instances:
			if first(qi, "question_set_reference") is not None:
				item = qti.Item(_("random question, slot {0}").format(_v(qi, "slot")), None)
				item.skip = _("random question from a category")
				items.append(item)
				continue
			ref = first(qi, "question_reference")
			question = self._question(_v(ref, "questionbankentryid"), _v(ref, "version"))
			if question is None:
				item = qti.Item(_("slot {0}").format(_v(qi, "slot")), None)
				item.skip = _("the question is not in the backup")
				items.append(item)
				continue
			item = self.item(question)
			item.points = flt(_v(qi, "maxmark")) or item.points
			items.append(item)
		method = cint(_v(el, "grademethod") or 1)
		settings = {
			"duration": cint(_v(el, "timelimit")),
			"attempts": cint(_v(el, "attempts_number") or _v(el, "attempts")),
			"shuffle": any(
				_v(sec, "shufflequestions") == "1" for sec in desc(kid(el, "sections"), "section")
			),
			"grading_basis": "Latest Attempt" if method == 4 else "Highest Score",
		}
		if method in (2, 3):
			self.b.note(name, _("Moodle graded the average or first attempt; the quiz keeps the highest"))
		made = self.b.quiz(name, items, lambda src: None, settings, graded=flt(_v(el, "grade")) != 0)
		intro = self.intro_blocks(el, ctx, "mod_quiz")
		for doctype, src in made:
			self.b.activity_lesson(chapter, self.b.activities[src]["fields"]["title"], doctype, src, intro)
			intro = None

	# --- questions ----------------------------------------------------------------------
	def _index_questions(self):
		root = self.a.xml("questions.xml")
		for cat in desc(root, "question_category"):
			ctx = _v(cat, "contextid")
			for entry in desc(cat, "question_bank_entry"):
				versions = []
				for ver in desc(entry, "question_versions"):
					q = first(ver, "question")
					if q is not None:
						q.set("_contextid", ctx)
						versions.append((cint(_v(ver, "version")), _v(ver, "status"), q))
				self.entries[entry.get("id")] = versions

	def _question(self, entry_id, version):
		versions = self.entries.get(entry_id) or []
		if version:
			found = [q for v, _s, q in versions if v == cint(version)]
			if found:
				return found[0]
		ready = [(v, q) for v, s, q in versions if s in ("ready", "")] or [(v, q) for v, _s, q in versions]
		return max(ready, key=lambda pair: pair[0])[1] if ready else None

	def item(self, q):
		"""A Moodle question as a ``qti.Item``, so quizzes from both formats share
		one set of rules for what can be imported."""
		qid, ctx = q.get("id"), q.get("_contextid")
		qtype = _v(q, "qtype")
		item = qti.Item(_v(q, "name"), None)
		item.points = flt(_v(q, "defaultmark")) or 1.0
		resolve = self.resolver(ctx, "question", "questiontext", qid)
		item.html = _resolve_html(_v(q, "questiontext"), resolve)
		if qtype in _QTYPE_SKIP:
			item.skip = _(_QTYPE_SKIP[qtype])
			return item
		answers = [
			(_v(a, "answertext"), flt(_v(a, "fraction")))
			for a in desc(first(q, f"plugin_qtype_{qtype}_question"), "answer")
		]
		if qtype in ("multichoice", "truefalse"):
			item.kind = qti.CHOICE
			single = _v(first(q, "multichoice"), "single", "1") if qtype == "multichoice" else "1"
			item.multiple = single == "0"
			item.options = [(qti._plain(t), f > 0) for t, f in answers]
		elif qtype == "shortanswer":
			item.kind = qti.SHORT
			item.answers = [a for a in dict.fromkeys(qti._plain(t) for t, f in answers if f > 0) if a]
			if any("*" in a for a in item.answers):
				item.skip = _("short answer with a * wildcard")
		elif qtype == "essay":
			item.kind = qti.ESSAY
		else:
			item.skip = _("Moodle question type {0}").format(qtype)
		return item


def _resolve_html(html, resolve):
	def swap(match):
		found = resolve(htmllib.unescape(match.group(2)))
		return f'{match.group(1)}"{htmllib.escape(found)}"' if found else match.group(0)

	return re.sub(r"""(\b(?:src|href)=)["']([^"']+)["']""", swap, html or "", flags=re.I)


def read(archive):
	return Reader(archive).read()
