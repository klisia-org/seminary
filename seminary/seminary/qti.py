"""Import quiz and exam questions from a QTI 1.2 or 2.1 package (decisions/106).

Canvas, Blackboard and Brightspace export a quiz as a zip of XML files, or a
single XML file. Choice and short-answer items go into a quiz as Questions;
essay items go into an exam as Open Questions. Anything else is listed in the
report with the reason and nothing is created for it.

A package is untrusted input: the XML is parsed with defusedxml, and the zip
is checked against size, entry and item limits before anything is read."""

import html
import io
import mimetypes
import posixpath
import re
import zipfile
from urllib.parse import unquote

import frappe
from defusedxml import DefusedXmlException, ElementTree
from frappe import _, _lt
from frappe.utils import cint, flt, strip_html
from frappe.utils.html_utils import sanitize_html

# Each can be raised in site_config.json.
MAX_QTI_BYTES = 100 * 1024**2  # qti_max_bytes: the upload itself
MAX_QTI_UNCOMPRESSED_BYTES = 300 * 1024**2  # qti_max_uncompressed_bytes
MAX_QTI_ENTRIES = 5000  # qti_max_entries
MAX_QTI_ITEMS = 1000  # qti_max_items

ESSAY = "essay"
CHOICE = "choice"
SHORT = "short"

TARGETS = {"Quiz": "Quiz", "Exam Activity": "Exam Activity"}


def _limit(key, default):
	return int(frappe.conf.get(key) or default)


# --- reading the package ----------------------------------------------------------------------


class Package:
	"""The XML documents and other files of an upload, by path."""

	def __init__(self, content, filename=""):
		if len(content) > _limit("qti_max_bytes", MAX_QTI_BYTES):
			frappe.throw(_("The file is too large to import."))
		self.files = {}
		if zipfile.is_zipfile(io.BytesIO(content)):
			self._read_zip(content)
		else:
			self.files[posixpath.basename(filename or "questions.xml")] = content

	def _read_zip(self, content):
		zf = zipfile.ZipFile(io.BytesIO(content))
		infos = [i for i in zf.infolist() if not i.is_dir()]
		if len(infos) > _limit("qti_max_entries", MAX_QTI_ENTRIES):
			frappe.throw(_("The package has too many files to import."))
		if sum(i.file_size for i in infos) > _limit("qti_max_uncompressed_bytes", MAX_QTI_UNCOMPRESSED_BYTES):
			frappe.throw(_("The package is too large to import once unpacked."))
		for info in infos:
			name = posixpath.normpath(info.filename.replace("\\", "/")).lstrip("/")
			if name.startswith("..") or name.startswith("__MACOSX/"):
				continue
			self.files[name] = zf.read(info)

	def xml_documents(self):
		for name in sorted(self.files):
			if name.lower().endswith(".xml"):
				try:
					root = ElementTree.fromstring(self.files[name])
				except ElementTree.ParseError:
					continue
				except DefusedXmlException:
					frappe.throw(_("{0} declares XML entities, which are not allowed.").format(name))
				yield name, root

	def find(self, src, base):
		"""The package file an <img src> points at, or None."""
		src = unquote(src.split("?", 1)[0].split("#", 1)[0])
		src = src.replace("$IMS-CC-FILEBASE$/", "").replace("$IMS_CC_FILEBASE$/", "")
		if not src or re.match(r"^[a-z][a-z0-9+.-]*:", src, re.I):
			return None
		candidates = [
			posixpath.normpath(posixpath.join(posixpath.dirname(base), src)),
			posixpath.normpath(src.lstrip("/")),
			posixpath.normpath(posixpath.join("web_resources", src.lstrip("/"))),
		]
		for c in candidates:
			if c in self.files:
				return c
		return None


def _ln(tag):
	"""Local name of an XML tag, without its namespace."""
	return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _children(el, name):
	return [c for c in el if _ln(c.tag) == name]


def _descendants(el, name):
	return [c for c in el.iter() if _ln(c.tag) == name]


def _first(el, name):
	found = _descendants(el, name)
	return found[0] if found else None


def _text(el):
	return "".join(el.itertext()).strip() if el is not None else ""


# --- one parsed item --------------------------------------------------------------------------


class Item:
	def __init__(self, title, source):
		self.title = title or ""
		self.source = source  # the XML file it came from, for images
		self.kind = None
		self.html = ""
		self.options = []  # [(text, is_correct)]
		self.multiple = False
		self.answers = []
		self.points = 1.0
		self.skip = None  # reason, when the item cannot be imported

	def label(self):
		return self.title or strip_html(self.html)[:80] or _("Untitled question")


def _mattext_html(material):
	"""HTML for a QTI 1.2 <material>: its mattext, escaped when it is plain text."""
	parts = []
	for mt in _descendants(material, "mattext"):
		raw = mt.text or ""
		if "html" in (mt.get("texttype") or "").lower():
			parts.append(raw)
		else:
			parts.append(html.escape(raw).replace("\n", "<br>"))
	return "".join(parts).strip()


def _plain(value):
	"""Option and answer text: plain, since students choose by the text itself."""
	return html.unescape(strip_html(value or "")).strip()


# QTI 1.2 question types, as Canvas (question_type) and Blackboard (bbmd_questiontype) name them
_V1_SKIP = {
	"matching_question": _lt("matching"),
	"multiple_dropdowns_question": _lt("several drop-downs"),
	"fill_in_multiple_blanks_question": _lt("several blanks"),
	"numerical_question": _lt("numeric"),
	"calculated_question": _lt("numeric"),
	"file_upload_question": _lt("file upload"),
	"text_only_question": _lt("text only, no question"),
	"matching": _lt("matching"),
	"numeric": _lt("numeric"),
	"calculated": _lt("numeric"),
	"file upload": _lt("file upload"),
	"fill in the blank plus": _lt("several blanks"),
	"jumbled sentence": _lt("several drop-downs"),
	"ordering": _lt("ordering"),
	"hot spot": _lt("hot spot"),
	"quiz bowl": _lt("quiz bowl"),
}
_V1_ESSAY = {"essay_question", "essay", "short response"}


def _v1_items(root, source):
	items = []
	for el in _descendants(root, "item"):
		item = Item(el.get("title"), source)
		meta = {
			_text(_first(f, "fieldlabel")).lower(): _text(_first(f, "fieldentry"))
			for f in _descendants(el, "qtimetadatafield")
		}
		qtype = (meta.get("question_type") or meta.get("bbmd_questiontype") or "").strip().lower()
		item.points = flt(meta.get("points_possible")) or 1.0

		presentation = _first(el, "presentation")
		if presentation is None:
			item.skip = _("no question text")
			items.append(item)
			continue
		inside_response = set()
		for resp in (
			_descendants(presentation, "response_lid")
			+ _descendants(presentation, "response_str")
			+ _descendants(presentation, "response_num")
		):
			inside_response.update(id(m) for m in _descendants(resp, "material"))
		item.html = "".join(
			_mattext_html(m) for m in _descendants(presentation, "material") if id(m) not in inside_response
		)

		correct = set()
		for cond in _descendants(el, "respcondition"):
			setvar = _first(cond, "setvar")
			value = _text(setvar)
			positive = (
				flt(value) > 0 or ".max" in value.lower() or (cond.get("title") or "").lower() == "correct"
			)
			if not positive:
				continue
			conditionvar = _first(cond, "conditionvar")
			if conditionvar is None:
				continue
			negated = {id(v) for n in _descendants(conditionvar, "not") for v in _descendants(n, "varequal")}
			correct.update(_text(v) for v in _descendants(conditionvar, "varequal") if id(v) not in negated)

		lids = _descendants(presentation, "response_lid")
		strs = _descendants(presentation, "response_str")
		if qtype in _V1_SKIP:
			item.skip = _V1_SKIP[qtype]
		elif _descendants(presentation, "response_num"):
			item.skip = _("numeric")
		elif len(lids) > 1 or len(strs) > 1:
			item.skip = _("several blanks")
		elif lids:
			item.kind = CHOICE
			lid = lids[0]
			for label in _descendants(lid, "response_label"):
				material = _first(label, "material")
				text = _plain(_mattext_html(material) if material is not None else "")
				item.options.append((text, label.get("ident") in correct))
			item.multiple = (lid.get("rcardinality") or "").lower() == "multiple"
		elif strs:
			if qtype in _V1_ESSAY or not correct:
				item.kind = ESSAY
			else:
				item.kind = SHORT
				item.answers = sorted({_plain(c) for c in correct if _plain(c)})
		else:
			item.skip = _("no answer to give")
		items.append(item)
	return items


# QTI 2.1 interactions that have no seminary question type
_V2_SKIP = {
	"matchInteraction": _lt("matching"),
	"associateInteraction": _lt("matching"),
	"gapMatchInteraction": _lt("matching"),
	"graphicGapMatchInteraction": _lt("matching"),
	"inlineChoiceInteraction": _lt("several drop-downs"),
	"orderInteraction": _lt("ordering"),
	"graphicOrderInteraction": _lt("ordering"),
	"hotspotInteraction": _lt("hot spot"),
	"selectPointInteraction": _lt("hot spot"),
	"graphicAssociateInteraction": _lt("hot spot"),
	"hottextInteraction": _lt("hot spot"),
	"sliderInteraction": _lt("numeric"),
	"uploadInteraction": _lt("file upload"),
	"drawingInteraction": _lt("drawing"),
	"mediaInteraction": _lt("media"),
	"customInteraction": _lt("custom"),
	"positionObjectInteraction": _lt("hot spot"),
}
_V2_SUPPORTED = {"choiceInteraction", "textEntryInteraction", "extendedTextInteraction"}


def _strip_ns(el):
	for e in el.iter():
		if isinstance(e.tag, str):
			e.tag = _ln(e.tag)
		for k in list(e.attrib):
			if "}" in k:
				e.attrib[_ln(k)] = e.attrib.pop(k)


def _inner_html(el):
	from xml.etree.ElementTree import tostring  # nosec B405 -- serialising only; parsing stays in defusedxml

	out = html.escape(el.text or "")
	for child in el:
		out += tostring(child, encoding="unicode", method="html")
	return out.strip()


def _remove(root, el, replacement=""):
	"""Take el out of the tree, keeping the text that followed it."""
	parent = next((p for p in root.iter() if el in list(p)), None)
	if parent is None:
		return
	kept = replacement + (el.tail or "")
	siblings = list(parent)
	i = siblings.index(el)
	if i:
		siblings[i - 1].tail = (siblings[i - 1].tail or "") + kept
	else:
		parent.text = (parent.text or "") + kept
	parent.remove(el)


def _v2_item(root, source):
	_strip_ns(root)
	item = Item(root.get("title"), source)
	body = _first(root, "itemBody")
	if body is None:
		item.skip = _("no question text")
		return item

	interactions = [e for e in body.iter() if isinstance(e.tag, str) and e.tag.endswith("Interaction")]
	unsupported = [e.tag for e in interactions if e.tag not in _V2_SUPPORTED]
	if unsupported:
		item.skip = _V2_SKIP.get(unsupported[0], unsupported[0])
		return item
	if len(interactions) != 1:
		item.skip = _("several blanks") if interactions else _("no answer to give")
		return item
	interaction = interactions[0]

	declarations = {d.get("identifier"): d for d in _descendants(root, "responseDeclaration")}
	decl = declarations.get(interaction.get("responseIdentifier"))
	correct = []
	if decl is not None:
		response = _first(decl, "correctResponse")
		correct = [_text(v) for v in _descendants(response, "value")] if response is not None else []
		for entry in _descendants(decl, "mapEntry"):
			if flt(entry.get("mappedValue")) > 0 and entry.get("mapKey") not in correct:
				correct.append(entry.get("mapKey"))

	for outcome in _descendants(root, "outcomeDeclaration"):
		if outcome.get("identifier") in ("MAXSCORE", "SCORE") and flt(outcome.get("normalMaximum")):
			item.points = flt(outcome.get("normalMaximum"))
			break
		if outcome.get("identifier") == "MAXSCORE":
			value = _first(outcome, "value")
			if flt(_text(value)):
				item.points = flt(_text(value))
				break

	prompt = _first(interaction, "prompt")
	parts = [_inner_html(prompt)] if prompt is not None else []
	if interaction.tag == "choiceInteraction":
		item.kind = CHOICE
		item.multiple = cint(interaction.get("maxChoices") or 1) != 1
		for choice in _descendants(interaction, "simpleChoice"):
			item.options.append((_plain(_inner_html(choice)), choice.get("identifier") in correct))
	elif interaction.tag == "textEntryInteraction":
		item.kind = SHORT
		item.answers = [a for a in dict.fromkeys(_plain(c) for c in correct) if a]
	else:
		item.kind = ESSAY

	# the question text: the item body without the interaction; an inline blank stays a blank
	_remove(body, interaction, "_____" if interaction.tag == "textEntryInteraction" else "")
	item.html = (_inner_html(body) + "".join(parts)).strip()
	if item.kind == SHORT and not item.answers:
		item.kind = ESSAY
	return item


def parse_document(name, root):
	"""The items of one parsed QTI document: a 1.2 questestinterop or a 2.1 item.
	Course migration (decisions/108) reads one quiz's file out of a cartridge."""
	tag = _ln(root.tag)
	if tag == "questestinterop":
		return _v1_items(root, name)
	if tag == "assessmentItem":
		return [_v2_item(root, name)]
	return []


def parse(package):
	items = []
	for name, root in package.xml_documents():
		items += parse_document(name, root)
		if len(items) > _limit("qti_max_items", MAX_QTI_ITEMS):
			frappe.throw(_("The package has too many questions to import."))
	return items


# --- writing ----------------------------------------------------------------------------------


def _store_images(item, package, target):
	"""Package images in the question text become private files on the quiz or
	exam, which students may read; a Question is not readable by students."""
	missing = []

	def swap(match):
		src = html.unescape(match.group(2))
		found = package.find(src, item.source)
		if not found:
			if not re.match(r"^(https?:|data:|/)", src, re.I):
				missing.append(src)
			return match.group(0)
		mime = mimetypes.guess_type(found)[0] or ""
		if not mime.startswith("image/"):
			return match.group(0)
		f = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": posixpath.basename(found),
				"content": package.files[found],
				"is_private": 1,
				"attached_to_doctype": target.doctype,
				"attached_to_name": target.name,
			}
		)
		f.save()
		return f'{match.group(1)}"{f.file_url}"'

	item.html = re.sub(r"""(<img\b[^>]*?\bsrc=)["']([^"']+)["']""", swap, item.html, flags=re.I)
	return missing


def _question(item, course):
	doc = frappe.new_doc("Question")
	doc.question = item.html
	doc.course = course
	if item.kind == CHOICE:
		doc.type = "Choices"
		doc.multiple = 1 if item.multiple else 0
		for text, is_correct in item.options:
			doc.append("choices", {"option": text, "is_correct": 1 if is_correct else 0})
	else:
		doc.type = "User Input"
		for answer in item.answers:
			doc.append("accepted_answers", {"answer": answer})
	doc.insert()
	return doc.name


def check_choice(item):
	options = [t for t, _c in item.options]
	if len([t for t in options if t]) < 2:
		return _("fewer than two options")
	if any(not t for t in options):
		return _("an option has no text, only an image")
	if len(set(options)) != len(options):
		return _("two options have the same text")
	if not any(c for _t, c in item.options):
		return _("no correct option marked")
	return None


def import_into(target, package):
	"""Add the package's questions to a Quiz or Exam Activity. Returns the report."""
	items = parse(package)
	created, skipped, notes = 0, [], []
	is_quiz = target.doctype == "Quiz"
	for item in items:
		reason = item.skip
		if not reason and is_quiz and item.kind == ESSAY:
			reason = _("essay; import it into an exam")
		if not reason and not is_quiz and item.kind != ESSAY:
			reason = _("not an essay; import it into a quiz")
		if not reason and item.kind == CHOICE:
			reason = check_choice(item)
		if not reason and not strip_html(item.html).strip() and "<img" not in item.html.lower():
			reason = _("no question text")
		if reason:
			skipped.append({"title": item.label(), "reason": str(reason)})
			continue

		for src in _store_images(item, package, target):
			notes.append({"title": item.label(), "note": _("image not in the package: {0}").format(src)})
		item.html = sanitize_html(item.html)
		if is_quiz:
			target.append(
				"questions",
				{"question": _question(item, target.course), "points": max(1, round(item.points))},
			)
		else:
			oq = frappe.new_doc("Open Question")
			oq.question = item.html
			oq.insert()
			target.append(
				"questions", {"question": oq.name, "points": item.points, "response_mode": "Written"}
			)
		created += 1

	if created:
		target.save()
	return {"created": created, "skipped": skipped, "notes": notes, "found": len(items)}


@frappe.whitelist()
def import_questions(doctype: str, name: str, file_url: str) -> dict:
	"""Import a QTI package, uploaded as a private File, into a quiz or exam. The
	upload is deleted afterwards; the package is not kept."""
	if doctype not in TARGETS:
		frappe.throw(_("Questions can only be imported into a quiz or an exam."))
	target = frappe.get_doc(doctype, name)
	target.check_permission("write")
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		frappe.throw(_("The uploaded file was not found."))
	f = frappe.get_doc("File", file_name)
	if f.owner != frappe.session.user:
		frappe.throw(_("Upload the package yourself to import it."), frappe.PermissionError)
	package = Package(f.get_content(), f.file_name)
	report = import_into(target, package)
	f.delete(ignore_permissions=True)
	return report
