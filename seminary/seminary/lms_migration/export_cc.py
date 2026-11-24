"""Export a Course Schedule as a Common Cartridge 1.3 (decisions/108 §3).

The content is gathered by the Course Pack exporter (decisions/041), so the two
exports carry the same things; this module only writes them in the cartridge's
terms. Chapters become modules and lessons web pages; quizzes and exams become
QTI 1.2 assessments, assignments the 1.3 assignment extension, and discussions
discussion topics. Each quiz's questions are also written as QTI 2.1 items,
which LMSs that read only QTI 2.1 can take.

What a cartridge has no place for is named in the section's comment trail."""

import html as htmllib
import io
import posixpath
import re
import zipfile
from urllib.parse import quote
from xml.sax.saxutils import escape, quoteattr  # nosec B406 -- writing only, nothing is parsed

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate, strip_html

from seminary.seminary.course_pack import editorjs
from seminary.seminary.course_pack.constants import ACTIVITY_BLOCKS
from seminary.seminary.course_pack.export import _Exporter, _validate_export

from . import html_blocks
from .builder import safe_name

NS = "http://www.imsglobal.org/xsd/imsccv1p3/imscp_v1p1"
LOM = "http://ltsc.ieee.org/xsd/imsccv1p3/LOM/manifest"
QTI_TYPE = "imsqti_xmlv1p2/imscc_xmlv1p3/assessment"
FILEBASE = "$IMS-CC-FILEBASE$"


def _x(value):
	return escape(str(value if value is not None else ""))


def _a(value):
	return quoteattr(str(value if value is not None else ""))


class CartridgeWriter:
	def __init__(self, cs_name):
		self.exporter = _Exporter(cs_name)
		self.m = self.exporter.build()
		self.files = {}  # path in the cartridge -> bytes, or ("file", File docname)
		self.resources = []  # xml strings
		self.url_paths = {}  # media url -> web_resources path
		self.left_out = []
		self._n = 0

	def uid(self, prefix):
		self._n += 1
		return f"{prefix}{self._n:04d}"

	# --- files --------------------------------------------------------------
	def _media(self):
		used = set()
		for url, meta in (self.m.get("media") or {}).items():
			name = safe_name(meta.get("file_name") or posixpath.basename(url))
			stem, ext = posixpath.splitext(name)
			path, n = f"web_resources/{name}", 2
			while path in used:
				path, n = f"web_resources/{stem}-{n}{ext}", n + 1
			used.add(path)
			self.url_paths[url] = path
			self.files[path] = ("file", self.exporter.media_sources.get(meta["key"]))
			rid = self.uid("RES")
			self.resources.append(
				f'<resource identifier="{rid}" type="webcontent" href={_a(path)}><file href={_a(path)}/></resource>'
			)

	def _html(self, html):
		"""HTML with this site's file URLs pointed at the cartridge's files."""
		for url in sorted(self.url_paths, key=len, reverse=True):
			if url in (html or ""):
				rel = quote(self.url_paths[url][len("web_resources/") :])
				html = html.replace(url, f"{FILEBASE}/{rel}")
		return html or ""

	# --- activities -----------------------------------------------------------
	def activity(self, src):
		"""The resource id for an activity, written once."""
		if src in self._written:
			return self._written[src]
		rec = (self.m.get("activities") or {}).get(src)
		if not rec:
			return None
		dt, f = rec["doctype"], rec.get("fields") or {}
		rid = self.uid("ACT")
		if dt in ("Quiz", "Exam Activity"):
			self._assessment(rid, rec)
		elif dt == "Assignment Activity":
			body = self._html(f.get("question"))
			formats = {"PDF": "file", "Document": "file", "Image": "file", "URL": "url", "Text": "text"}
			fmt = formats.get(f.get("type"), "file")
			graded = "true" if cint(f.get("grade_assignment")) else "false"
			self.files[f"{rid}/assignment.xml"] = (
				'<?xml version="1.0" encoding="UTF-8"?>\n'
				'<assignment xmlns="http://www.imsglobal.org/xsd/imscc_extensions/assignment" '
				f'identifier="{rid}"><title>{_x(f.get("title"))}</title>'
				f'<text texttype="text/html">{_x(body)}</text>'
				f'<gradable points_possible="100">{graded}</gradable>'
				f'<submission_formats><format type="{fmt}"/></submission_formats></assignment>'
			).encode()
			self.resources.append(
				f'<resource identifier="{rid}" type="assignment_xmlv1p0" href="{rid}/assignment.xml">'
				f'<file href="{rid}/assignment.xml"/></resource>'
			)
		elif dt == "Discussion Activity":
			self.files[f"{rid}/topic.xml"] = (
				'<?xml version="1.0" encoding="UTF-8"?>\n'
				'<topic xmlns="http://www.imsglobal.org/xsd/imsccv1p3/imsdt_v1p3">'
				f"<title>{_x(f.get('discussion_name'))}</title>"
				f'<text texttype="text/html">{_x(self._html(f.get("prompt")))}</text></topic>'
			).encode()
			self.resources.append(
				f'<resource identifier="{rid}" type="imsdt_xmlv1p3"><file href="{rid}/topic.xml"/></resource>'
			)
		else:
			self.left_out.append(
				_("{0} '{1}': no Common Cartridge type").format(_(dt), f.get("title") or src)
			)
			rid = None
		self._written[src] = rid
		return rid

	def _assessment(self, rid, rec):
		f = rec.get("fields") or {}
		items, items21 = [], []
		for n, row in enumerate(rec.get("questions") or [], start=1):
			q = (self.m.get("questions") or {}).get(row.get("question"))
			if not q:
				continue
			points = flt((row.get("fields") or {}).get("points")) or 1
			item = self._qti_item(f"{rid}_Q{n}", q, points)
			if item:
				items.append(item)
				items21.append((f"{rid}_Q{n}", q, points))
			else:
				self.left_out.append(
					_("{0}: question {1} ({2}) has no Common Cartridge type").format(
						f.get("title"), n, (q.get("fields") or {}).get("type")
					)
				)
		attempts = cint(f.get("max_attempts")) or "unlimited"
		meta = (
			"<qtimetadata>"
			"<qtimetadatafield><fieldlabel>cc_profile</fieldlabel><fieldentry>cc.exam.v0p1</fieldentry></qtimetadatafield>"
			f"<qtimetadatafield><fieldlabel>cc_maxattempts</fieldlabel><fieldentry>{attempts}</fieldentry></qtimetadatafield>"
			"</qtimetadata>"
		)
		self.files[f"{rid}/assessment.xml"] = (
			'<?xml version="1.0" encoding="UTF-8"?>\n'
			'<questestinterop xmlns="http://www.imsglobal.org/xsd/ims_qtiasiv1p2">'
			f"<assessment ident={_a(rid)} title={_a(f.get('title'))}>{meta}"
			f'<section ident="root_section">{"".join(items)}</section></assessment></questestinterop>'
		).encode()
		self.resources.append(
			f'<resource identifier="{rid}" type="{QTI_TYPE}"><file href="{rid}/assessment.xml"/></resource>'
		)
		for ident, q, points in items21:
			path = f"question_bank/{rid}/{ident}.xml"
			xml = self._qti21_item(ident, q, points)
			if xml:
				self.files[path] = xml.encode()
				self.resources.append(
					f'<resource identifier="{ident}_21" type="imsqti_item_xmlv2p1" href="{path}">'
					f'<file href="{path}"/></resource>'
				)

	def _qti_item(self, ident, q, points):
		f = q.get("fields") or {}
		text = self._html(f.get("question"))
		meta = lambda profile: (  # noqa: E731
			"<itemmetadata><qtimetadata>"
			f"<qtimetadatafield><fieldlabel>cc_profile</fieldlabel><fieldentry>{profile}</fieldentry></qtimetadatafield>"
			f"<qtimetadatafield><fieldlabel>cc_weighting</fieldlabel><fieldentry>{points:g}</fieldentry></qtimetadatafield>"
			f"<qtimetadatafield><fieldlabel>points_possible</fieldlabel><fieldentry>{points:g}</fieldentry></qtimetadatafield>"
			"</qtimetadata></itemmetadata>"
		)
		material = f'<material><mattext texttype="text/html">{_x(text)}</mattext></material>'
		title = _a(strip_html(text)[:80] or ident)
		score = '<outcomes><decvar varname="SCORE" vartype="Decimal" minvalue="0" maxvalue="100"/></outcomes>'
		if q.get("doctype") == "Open Question":
			return (
				f"<item ident={_a(ident)} title={title}>{meta('cc.essay.v0p1')}<presentation>{material}"
				'<response_str ident="response1" rcardinality="Single"><render_fib/></response_str>'
				f"</presentation><resprocessing>{score}</resprocessing></item>"
			)
		if f.get("type") == "Choices":
			choices = q.get("choices") or []
			multiple = cint(f.get("multiple"))
			labels = "".join(
				f'<response_label ident="{ident}_A{i}"><material><mattext texttype="text/plain">{_x(c.get("option"))}'
				"</mattext></material></response_label>"
				for i, c in enumerate(choices, start=1)
			)
			right = [f"{ident}_A{i}" for i, c in enumerate(choices, start=1) if cint(c.get("is_correct"))]
			wrong = [f"{ident}_A{i}" for i, c in enumerate(choices, start=1) if not cint(c.get("is_correct"))]
			if multiple:
				cond = (
					"<and>"
					+ "".join(f'<varequal respident="response1">{r}</varequal>' for r in right)
					+ "".join(f'<not><varequal respident="response1">{w}</varequal></not>' for w in wrong)
					+ "</and>"
				)
				profile, card = "cc.multiple_response.v0p1", "Multiple"
			else:
				cond = "".join(f'<varequal respident="response1">{r}</varequal>' for r in right[:1])
				profile, card = "cc.multiple_choice.v0p1", "Single"
			return (
				f"<item ident={_a(ident)} title={title}>{meta(profile)}<presentation>{material}"
				f'<response_lid ident="response1" rcardinality="{card}"><render_choice>{labels}</render_choice>'
				f"</response_lid></presentation><resprocessing>{score}"
				f'<respcondition continue="No"><conditionvar>{cond}</conditionvar>'
				'<setvar varname="SCORE" action="Set">100</setvar></respcondition></resprocessing></item>'
			)
		if f.get("type") == "User Input":
			answers = [a.get("answer") for a in q.get("accepted_answers") or [] if a.get("answer")]
			conds = "".join(
				f'<respcondition continue="No"><conditionvar><varequal respident="response1" case="No">{_x(a)}'
				'</varequal></conditionvar><setvar varname="SCORE" action="Set">100</setvar></respcondition>'
				for a in answers
			)
			return (
				f"<item ident={_a(ident)} title={title}>{meta('cc.fib.v0p1')}<presentation>{material}"
				'<response_str ident="response1" rcardinality="Single"><render_fib/></response_str>'
				f"</presentation><resprocessing>{score}{conds}</resprocessing></item>"
			)
		return None

	def _qti21_item(self, ident, q, points):
		f = q.get("fields") or {}
		body = self._html(f.get("question"))
		head = (
			'<?xml version="1.0" encoding="UTF-8"?>\n'
			'<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1" '
			f'identifier={_a(ident)} title={_a(strip_html(body)[:80] or ident)} adaptive="false" timeDependent="false">'
		)
		outcome = (
			f'<outcomeDeclaration identifier="SCORE" cardinality="single" baseType="float" normalMaximum="{points:g}">'
			"<defaultValue><value>0</value></defaultValue></outcomeDeclaration>"
		)
		prompt = f"<div>{_xhtml(body)}</div>"
		if q.get("doctype") == "Open Question":
			return (
				f'{head}<responseDeclaration identifier="RESPONSE" cardinality="single" baseType="string"/>'
				f'{outcome}<itemBody>{prompt}<extendedTextInteraction responseIdentifier="RESPONSE"/></itemBody>'
				"</assessmentItem>"
			)
		if f.get("type") == "Choices":
			choices = q.get("choices") or []
			multiple = cint(f.get("multiple"))
			right = "".join(
				f"<value>C{i}</value>" for i, c in enumerate(choices, start=1) if cint(c.get("is_correct"))
			)
			simple = "".join(
				f'<simpleChoice identifier="C{i}">{_x(c.get("option"))}</simpleChoice>'
				for i, c in enumerate(choices, start=1)
			)
			card = "multiple" if multiple else "single"
			return (
				f'{head}<responseDeclaration identifier="RESPONSE" cardinality="{card}" baseType="identifier">'
				f"<correctResponse>{right}</correctResponse></responseDeclaration>{outcome}"
				f'<itemBody>{prompt}<choiceInteraction responseIdentifier="RESPONSE" shuffle="false" '
				f'maxChoices="{0 if multiple else 1}">{simple}</choiceInteraction></itemBody>'
				'<responseProcessing template="http://www.imsglobal.org/question/qti_v2p1/rptemplates/match_correct"/>'
				"</assessmentItem>"
			)
		if f.get("type") == "User Input":
			answers = [a.get("answer") for a in q.get("accepted_answers") or [] if a.get("answer")]
			if not answers:
				return None
			mapping = "".join(f'<mapEntry mapKey={_a(a)} mappedValue="{points:g}"/>' for a in answers)
			return (
				f'{head}<responseDeclaration identifier="RESPONSE" cardinality="single" baseType="string">'
				f"<correctResponse><value>{_x(answers[0])}</value></correctResponse>"
				f'<mapping defaultValue="0">{mapping}</mapping></responseDeclaration>{outcome}'
				f'<itemBody>{prompt}<p><textEntryInteraction responseIdentifier="RESPONSE"/></p></itemBody>'
				'<responseProcessing template="http://www.imsglobal.org/question/qti_v2p1/rptemplates/map_response"/>'
				"</assessmentItem>"
			)
		return None

	# --- the outline ------------------------------------------------------------
	def _lesson(self, lesson_src):
		"""``(page resource id or None, [activity resource ids])`` for a lesson."""
		rec = (self.m.get("lessons") or {}).get(lesson_src) or {}
		f = rec.get("fields") or {}
		data = editorjs.load_blocks(f.get("content"))
		blocks = data["blocks"] if data else []
		activities = []
		for b in blocks:
			spec = ACTIVITY_BLOCKS.get(b.get("type")) if isinstance(b, dict) else None
			if spec and spec[1] != "Course Folder":
				d = b.get("data") or {}
				ref = d.get(spec[0]) or d.get("discussion")
				rid = self.activity(ref) if ref else None
				if rid:
					activities.append(rid)
		html = html_blocks.blocks_to_html(blocks) if data else (f.get("body") or "")
		if strip_html(html).strip() or "<img" in html or "<iframe" in html or "<video" in html:
			title = f.get("lesson_title") or ""
			path = f"pages/{self.uid('P')}-{safe_name(title)[:40] or 'page'}.html".replace(" ", "-")
			doc = (
				'<!DOCTYPE html>\n<html><head><meta charset="utf-8">'
				f"<title>{_x(title)}</title></head><body>{self._html(html)}</body></html>"
			)
			self.files[path] = doc.encode()
			rid = self.uid("PAGE")
			self.resources.append(
				f'<resource identifier="{rid}" type="webcontent" href={_a(path)}><file href={_a(path)}/></resource>'
			)
			return rid, activities
		return None, activities

	def build(self):
		self._written = {}
		self._media()
		modules = []
		for ch in self.m.get("chapters") or []:
			if (ch.get("fields") or {}).get("is_scorm_package"):
				self.left_out.append(_("SCORM chapter '{0}'").format(ch["fields"].get("chapter_title")))
				continue
			items = []
			for lsrc in ch.get("lessons") or []:
				title = ((self.m["lessons"].get(lsrc) or {}).get("fields") or {}).get("lesson_title") or ""
				page, activities = self._lesson(lsrc)
				if page:
					items.append((title, page))
				for rid in activities:
					items.append((self._activity_title(rid) or title, rid))
			modules.append(((ch.get("fields") or {}).get("chapter_title") or "", items))
		# Graded work no lesson shows still belongs in the course.
		extra = []
		for row in self.m.get("scac") or []:
			for field in ("quiz", "exam", "assignment", "discussion", "oral"):
				src = row.get(field)
				if src and src not in self._written:
					rid = self.activity(src)
					if rid:
						extra.append((self._activity_title(rid), rid))
		if extra:
			modules.append((_("Assessments"), extra))
		for _key, folder in (self.m.get("folders") or {}).items():
			self._folder(folder)
		return self._manifest(modules)

	def _activity_title(self, rid):
		for src, written in self._written.items():
			if written == rid:
				f = (self.m["activities"].get(src) or {}).get("fields") or {}
				return f.get("title") or f.get("discussion_name")
		return None

	def _folder(self, folder):
		"""A course folder's files, under web_resources/<folder name>/."""
		base = f"web_resources/{safe_name(folder.get('foldername'))}"

		def walk(nodes, prefix):
			for node in nodes:
				if node.get("type") == "folder":
					walk(node.get("children") or [], f"{prefix}/{safe_name(node.get('file_name'))}")
				else:
					meta = (self.m.get("media") or {}).get(node.get("media"))
					if not meta:
						continue
					path = f"{prefix}/{safe_name(node.get('file_name'))}"
					self.files[path] = ("file", self.exporter.media_sources.get(meta["key"]))
					rid = self.uid("RES")
					self.resources.append(
						f'<resource identifier="{rid}" type="webcontent" href={_a(path)}><file href={_a(path)}/></resource>'
					)

		walk(folder.get("files") or [], base)

	def _manifest(self, modules):
		title = (self.m.get("source") or {}).get("title") or (self.m.get("source") or {}).get("course") or ""
		org = []
		for ch_title, items in modules:
			inner = "".join(
				f'<item identifier="{self.uid("I")}" identifierref="{rid}"><title>{_x(t)}</title></item>'
				for t, rid in items
			)
			org.append(f'<item identifier="{self.uid("M")}"><title>{_x(ch_title)}</title>{inner}</item>')
		return (
			'<?xml version="1.0" encoding="UTF-8"?>\n'
			f'<manifest identifier="{self.uid("MAN")}" xmlns="{NS}" xmlns:lomimscc="{LOM}">'
			"<metadata><schema>IMS Common Cartridge</schema><schemaversion>1.3.0</schemaversion>"
			"<lomimscc:lom><lomimscc:general><lomimscc:title>"
			f"<lomimscc:string>{_x(title)}</lomimscc:string></lomimscc:title></lomimscc:general></lomimscc:lom>"
			"</metadata>"
			'<organizations><organization identifier="ORG" structure="rooted-hierarchy">'
			f'<item identifier="ROOT">{"".join(org)}</item></organization></organizations>'
			f"<resources>{''.join(self.resources)}</resources></manifest>"
		)

	def write(self, fileobj):
		from seminary.storage.files import open_stream

		manifest = self.build()
		with zipfile.ZipFile(fileobj, "w", zipfile.ZIP_DEFLATED) as zf:
			zf.writestr("imsmanifest.xml", manifest)
			for path, content in self.files.items():
				if isinstance(content, tuple):
					if not content[1]:
						continue
					with open_stream(content[1]) as chunks, zf.open(path, "w") as target:
						for chunk in chunks:
							target.write(chunk)
				else:
					zf.writestr(path, content)

	def filename(self):
		slug = frappe.scrub((self.m.get("source") or {}).get("course") or "course")
		return f"{slug}-{nowdate().replace('-', '')}.imscc"


def _xhtml(html):
	"""Question HTML well formed enough for a QTI 2.1 item body."""
	from bs4 import BeautifulSoup

	soup = BeautifulSoup(html or "", "html.parser")
	out = soup.decode(formatter="minimal")
	return re.sub(r"<(br|img|hr)([^>]*?)\s*/?>", r"<\1\2/>", out)


def build_cartridge_bytes(cs_name):
	"""``(filename, bytes, left_out)``: the cartridge for a section. For tests."""
	_validate_export(cs_name)
	writer = CartridgeWriter(cs_name)
	buf = io.BytesIO()
	writer.write(buf)
	return writer.filename(), buf.getvalue(), writer.left_out


@frappe.whitelist(methods=["GET"])
def export_common_cartridge(course_schedule: str):
	"""Download the section as a Common Cartridge 1.3 (.imscc)."""
	_validate_export(course_schedule)
	frappe.local.flags.commit = True  # keep the comment trail on a GET
	writer = CartridgeWriter(course_schedule)
	buf = io.BytesIO()
	writer.write(buf)
	lines = [_("Exported Common Cartridge {0}.").format(writer.filename())]
	lines.append(
		_(
			"A cartridge does not carry rubrics, release dates and prerequisites, assessment weights and "
			"categories, oral activities, SCORM chapters, competencies or reflection blocks."
		)
	)
	lines.extend(writer.left_out)
	frappe.get_doc("Course Schedule", course_schedule).add_comment(
		"Info", "<br>".join(htmllib.escape(str(line)) for line in lines)
	)
	frappe.local.response.filename = writer.filename()
	frappe.local.response.filecontent = buf.getvalue()
	frappe.local.response.type = "download"
	frappe.local.response.display_content_as = "attachment"
