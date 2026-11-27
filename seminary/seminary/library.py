# Copyright (c) 2026, Murilo R. Melo and contributors
# For license information, please see license.txt
"""The lesson library, shared questions and quizzes, and required lessons (decisions/122).

A Library Lesson belongs to the school. A section places it with a Course Lesson whose
`library_lesson` points at it: the library content is read through on every view, and the
Course Lesson's own `content` holds only the section's activity blocks (quiz, assignment,
exam, discussion, oral), which are shown after the library's blocks. Grading stays with
the section.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, now_datetime, nowdate

from seminary.seminary import guards

#: EditorJS blocks that name one section's activity. A library lesson never holds them;
#: a placed lesson holds nothing else.
ACTIVITY_TYPES = frozenset(
	{
		"quiz",
		"exam",
		"assignment",
		"discussion",
		"discussionActivity",
		"discussionactivity",
		"oralActivity",
	}
)
#: Competency reflection blocks (decisions/079): they read the lesson they sit in, so a lesson
#: shared across sections can't hold them either.
REFLECTION_TYPES = frozenset({"selfAssessment", "developmentPlan"})
#: Fields a placed lesson reads from the library.
CONTENT_FIELDS = ("body", "youtube", "instructor_content", "instructor_notes", "preview", "transcript")
CLOSED_STATES = ("Closed", "Cancelled")
START = "Start of the first chapter"


# ------------------------------------------------------------------------ blocks


def _doc(content):
	if not content:
		return {"blocks": []}
	if isinstance(content, dict):
		return content
	try:
		data = json.loads(content)
	except (TypeError, ValueError):
		return {"blocks": []}
	if not isinstance(data, dict):
		return {"blocks": []}
	data.setdefault("blocks", [])
	return data


def activity_blocks(content):
	return [b for b in _doc(content)["blocks"] if isinstance(b, dict) and b.get("type") in ACTIVITY_TYPES]


def merged_content(library_content, local_content):
	"""The library's blocks, then the section's own activity blocks, as one EditorJS document."""
	lib = _doc(library_content)
	blocks = list(lib["blocks"]) + activity_blocks(local_content)
	if not blocks:
		return None
	out = {k: v for k, v in lib.items() if k != "blocks"}
	out["blocks"] = blocks
	return json.dumps(out)


# ------------------------------------------------------------------------ reads


def _library(name):
	cache = getattr(frappe.local, "library_lessons", None)
	if cache is None:
		cache = frappe.local.library_lessons = {}
	if name not in cache:
		cache[name] = frappe.db.get_value(
			"Library Lesson", name, ["name", "title", "content", *CONTENT_FIELDS], as_dict=True
		)
	return cache[name]


def library_captions(name):
	from seminary.language import native_choices

	rows = frappe.get_all(
		"Course Lesson Caption",
		filters={"parent": name, "parenttype": "Library Lesson", "parentfield": "captions"},
		fields=["language", "label", "caption_file"],
		order_by="idx asc",
	)
	names = dict(native_choices([r.language for r in rows])) if rows else {}
	return [
		{
			"language": r.language,
			"label": r.label or names.get(r.language) or r.language,
			"file": r.caption_file,
		}
		for r in rows
		if r.caption_file
	]


def overlay(details):
	"""Replace a placed lesson's content fields with the library's, in place, for any read
	(`get_lesson`, the outline, the lesson form). A lesson with no library link is untouched."""
	if not details or not details.get("library_lesson"):
		return details
	lib = _library(details.library_lesson)
	if not lib:
		return details
	local = details.get("content")
	details["section_content"] = json.dumps({"blocks": activity_blocks(local)})
	details["library_content"] = lib.content
	details["content"] = merged_content(lib.content, local)
	for field in CONTENT_FIELDS:
		if field in details or field in ("body", "youtube"):
			details[field] = lib.get(field)
	details["lesson_title"] = lib.title
	if "captions" in details:
		details["captions"] = library_captions(lib.name)
	requirement = details.get("required_by")
	if requirement is None and details.get("name"):
		requirement = frappe.db.get_value("Course Lesson", details.name, "required_by")
	reason = frappe.db.get_value("Library Lesson Requirement", requirement, "reason") if requirement else None
	details["library"] = {
		"name": lib.name,
		"title": lib.title,
		"required": bool(requirement and _requirement_active(requirement)),
		"reason": reason,
		"can_edit": _can_edit(lib.name),
	}
	return details


def inline(doc):
	"""Put the library content into a Course Lesson document in memory (course packs, a copy to
	a course that may not place the lesson). The caller decides whether to save it."""
	if not doc.get("library_lesson"):
		return doc
	lib = _library(doc.library_lesson)
	if lib:
		doc.content = merged_content(lib.content, doc.content)
		for field in CONTENT_FIELDS:
			doc.set(field, lib.get(field))
		doc.lesson_title = lib.title
	doc.library_lesson = None
	return doc


# ------------------------------------------------------------------------ rules


def available_for(library_lesson, course):
	courses = frappe.get_all(
		"Library Lesson Course",
		filters={"parent": library_lesson, "parenttype": "Library Lesson"},
		pluck="course",
	)
	return not courses or course in courses


def _requirement_active(name):
	return bool(cint(frappe.db.get_value("Library Lesson Requirement", name, "active")))


def _is_manager(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(
		{"Seminary Manager", "System Manager"} & set(frappe.get_roles(user))
	)


def _can_edit(library_lesson, user=None):
	if _is_manager(user):
		return True
	instructor = guards.current_instructor(user)
	return bool(
		instructor
		and frappe.db.exists(
			"Library Lesson Maintainer",
			{"parent": library_lesson, "parenttype": "Library Lesson", "instructor": instructor},
		)
	)


def has_permission(doc, ptype=None, user=None):
	"""Instructors browse the whole library and edit what they maintain. A student reads a
	library lesson only when a section they may read places it."""
	user = user or frappe.session.user
	if guards.is_school_role(user):
		return True
	roles = set(frappe.get_roles(user))
	if "Instructor" in roles:
		if ptype in (None, "read", "select", "print", "report"):
			return True
		if ptype == "create" or doc.is_new():
			return True
		return _can_edit(doc.name, user)
	if ptype not in (None, "read", "print"):
		return False
	sections = frappe.get_all("Course Lesson", {"library_lesson": doc.name}, pluck="course_sc", distinct=True)
	return any(guards.may_view_content(cs, user) for cs in sections if cs)


def validate_library_lesson(doc, method=None):
	from seminary.seminary.doctype.course_lesson.course_lesson import CourseLesson
	from seminary.seminary.editorjs_safety import sanitize_content

	for fieldname in ("content", "instructor_content"):
		cleaned, _found = sanitize_content(doc.get(fieldname))
		doc.set(fieldname, cleaned)
	if activity_blocks(doc.content):
		frappe.throw(
			_(
				"A library lesson can't hold a quiz, assignment, exam, discussion or oral activity, "
				"because those belong to one section. Add them to the lesson in each section."
			)
		)
	for content in (doc.content, doc.instructor_content):
		if any(isinstance(b, dict) and b.get("type") in REFLECTION_TYPES for b in _doc(content)["blocks"]):
			frappe.throw(
				_(
					"A library lesson can't hold a self-assessment or development plan block, because "
					"each reads its own section's lesson. Add it to the lesson in each section."
				)
			)
	CourseLesson.validate_captions(doc)
	instructor = guards.current_instructor()
	if doc.is_new() and instructor and not doc.get("maintainers"):
		doc.append("maintainers", {"instructor": instructor})


def on_library_lesson_update(doc, method=None):
	"""Placed lessons keep the library title, so the outline and reports need no join."""
	if doc.has_value_changed("title"):
		for name in frappe.get_all("Course Lesson", {"library_lesson": doc.name}, pluck="name"):
			frappe.db.set_value("Course Lesson", name, "lesson_title", doc.title, update_modified=False)
	(getattr(frappe.local, "library_lessons", None) or {}).pop(doc.name, None)


def validate_course_lesson(doc, method=None):
	"""Placement rules on the section's lesson."""
	before = doc.get_doc_before_save()
	if doc.library_lesson:
		course = frappe.db.get_value("Course Schedule", doc.course_sc, "course") if doc.course_sc else None
		changed = not before or before.library_lesson != doc.library_lesson
		if (
			changed
			and course
			and not doc.flags.from_requirement
			and not available_for(doc.library_lesson, course)
		):
			frappe.throw(_("That library lesson isn't available to this course."))
		others = [
			b
			for b in _doc(doc.content)["blocks"]
			if isinstance(b, dict) and b.get("type") not in ACTIVITY_TYPES
		]
		if others:
			frappe.throw(
				_(
					"A lesson from the library shows the library's content. Its own content can hold only "
					"this section's activities. Detach it from the library to edit its content."
				)
			)
		doc.lesson_title = (
			frappe.db.get_value("Library Lesson", doc.library_lesson, "title") or doc.lesson_title
		)
	if (
		before
		and before.required_by
		and before.library_lesson
		and not doc.library_lesson
		and not doc.flags.library_detach
		and not _is_manager()
		and _requirement_active(before.required_by)
	):
		frappe.throw(_("The school requires this lesson, so it can't be detached from the library."))


def guard_course_lesson_trash(doc, method=None):
	if doc.required_by and not doc.flags.from_requirement and not _is_manager():
		if _requirement_active(doc.required_by):
			frappe.throw(_("The school requires this lesson, so it can't be deleted."))


# ------------------------------------------------------------------------ placing


def _chapter_lessons(chapter):
	return frappe.get_all(
		"Course Schedule Lesson Reference",
		filters={"parent": chapter, "parenttype": "Course Schedule Chapter"},
		pluck="lesson",
		order_by="idx asc",
	)


def _place(library_lesson, chapter, at_start=False, required_by=None):
	chapter_doc = frappe.get_doc("Course Schedule Chapter", chapter)
	lesson = frappe.new_doc("Course Lesson")
	lesson.chapter = chapter
	lesson.course_sc = chapter_doc.coursesc
	lesson.lesson_title = frappe.db.get_value("Library Lesson", library_lesson, "title")
	lesson.library_lesson = library_lesson
	lesson.required_by = required_by
	lesson.flags.ignore_permissions = True
	lesson.flags.from_requirement = bool(required_by)
	lesson.insert()
	rows = [r.lesson for r in chapter_doc.lessons if r.lesson]
	if at_start:
		rows.insert(0, lesson.name)
	else:
		rows.append(lesson.name)
	chapter_doc.set("lessons", [{"lesson": n} for n in rows])
	chapter_doc.flags.ignore_permissions = True
	chapter_doc.save()
	return lesson.name


@frappe.whitelist()
def place(library_lesson: str, chapter: str, at_start: int | str = 0):
	"""*Add to chapter* from the library page or the lesson form."""
	_require_instructor()
	course_schedule = frappe.db.get_value("Course Schedule Chapter", chapter, "coursesc")
	if not course_schedule:
		frappe.throw(_("Chapter not found."))
	guards.require_section_capability(course_schedule, guards.CONTENT)
	if not frappe.has_permission("Library Lesson", "read", doc=library_lesson):
		frappe.throw(_("You can't use that library lesson."), frappe.PermissionError)
	course = frappe.db.get_value("Course Schedule", course_schedule, "course")
	if not available_for(library_lesson, course):
		frappe.throw(_("That library lesson isn't available to this course."))
	return {"lesson": _place(library_lesson, chapter, at_start=cint(at_start))}


def _detach(doc, frozen=False):
	lib = frappe.get_doc("Library Lesson", doc.library_lesson)
	doc.content = merged_content(lib.content, doc.content)
	for field in CONTENT_FIELDS:
		doc.set(field, lib.get(field))
	doc.lesson_title = lib.title
	doc.set("captions", [])
	for row in lib.captions:
		doc.append(
			"captions", {"language": row.language, "label": row.label, "caption_file": row.caption_file}
		)
	doc.detached_from = lib.name
	doc.detached_on = now_datetime()
	doc.frozen_at_close = 1 if frozen else 0
	doc.library_lesson = None
	doc.flags.library_detach = True
	doc.flags.ignore_permissions = True
	doc.save()


@frappe.whitelist()
def detach(lesson: str):
	"""Make a placed lesson the section's own copy. It stops receiving library edits."""
	_require_instructor()
	doc = frappe.get_doc("Course Lesson", lesson)
	guards.require_section_capability(doc.course_sc, guards.CONTENT)
	if not doc.library_lesson:
		frappe.throw(_("This lesson isn't from the library."))
	if doc.required_by and _requirement_active(doc.required_by) and not _is_manager():
		frappe.throw(_("The school requires this lesson, so it can't be detached from the library."))
	_detach(doc)
	return {"lesson": doc.name}


def freeze_on_close(doc, method=None):
	"""A section reaching Closed keeps what its students saw: every placed lesson is detached."""
	if doc.get("workflow_state") != "Closed" or not doc.has_value_changed("workflow_state"):
		return
	for name in frappe.get_all(
		"Course Lesson", {"course_sc": doc.name, "library_lesson": ("is", "set")}, pluck="name"
	):
		_detach(frappe.get_doc("Course Lesson", name), frozen=True)


# ------------------------------------------------------------------------ requirements


def _programs(req):
	return [r.program for r in req.programs if r.program]


def _terms(req):
	return [r.academic_term for r in req.academic_terms if r.academic_term]


def _courses_of(programs):
	if not programs:
		return []
	return frappe.get_all(
		"Program Course",
		filters={"parent": ("in", programs), "parenttype": "Program"},
		pluck="course",
		distinct=True,
	)


def sections_for(req, include_closed=False):
	"""The sections a requirement applies to: their course is in one of its programs, and they
	are in one of its terms (any section not yet closed when it names none)."""
	courses = _courses_of(_programs(req))
	if not courses:
		return []
	filters = {"course": ("in", courses)}
	terms = _terms(req)
	if terms:
		filters["academic_term"] = ("in", terms)
	excluded = ("Cancelled",) if include_closed and terms else CLOSED_STATES
	filters["workflow_state"] = ("not in", excluded)
	return frappe.get_all("Course Schedule", filters=filters, pluck="name")


def _ensure_required(req, course_schedule):
	"""One required lesson in the section. A lesson the section already placed from the same
	library lesson becomes the required one instead of a second copy. Returns the new lesson's
	name, or None when nothing was placed."""
	if frappe.db.exists("Course Lesson", {"course_sc": course_schedule, "required_by": req.name}):
		return None
	existing = frappe.db.get_value(
		"Course Lesson", {"course_sc": course_schedule, "library_lesson": req.library_lesson}, "name"
	)
	if existing:
		frappe.db.set_value("Course Lesson", existing, "required_by", req.name, update_modified=False)
		return None
	chapters = frappe.get_all(
		"Course Schedule Chapter Reference",
		filters={"parent": course_schedule, "parenttype": "Course Schedule"},
		pluck="chapter",
		order_by="idx asc",
	)
	chapters = [c for c in chapters if c]
	if not chapters:
		return None
	at_start = req.position == START
	return _place(req.library_lesson, chapters[0] if at_start else chapters[-1], at_start, req.name)


def _notify_required(req, course_schedule):
	from seminary.seminary import comms

	title = frappe.db.get_value("Course Schedule", course_schedule, "title") or course_schedule
	for person in _section_people(course_schedule):
		try:
			comms.send_message(
				channel="In-App",
				subject=_("A required lesson was added to {0}").format(title),
				message=_(
					"The school added {0} to {1}: {2} It follows its chapter's release date and "
					"prerequisites, and counts when a chapter must be completed."
				).format(req.lesson_title, title, req.reason or ""),
				person=person,
				category="Academic",
				reference_doctype="Course Schedule",
				reference_name=course_schedule,
				dedupe_key=f"library-required-{req.name}-{course_schedule}-{person}",
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Required lesson notice failed")


def place_requirement(req):
	for course_schedule in sections_for(req):
		if _ensure_required(req, course_schedule):
			_notify_required(req, course_schedule)


def place_for_section(course_schedule):
	"""Every active requirement that covers this section, after it gains chapters."""
	section = frappe.db.get_value(
		"Course Schedule", course_schedule, ["course", "academic_term", "workflow_state"], as_dict=True
	)
	if not section or section.workflow_state in CLOSED_STATES:
		return
	for name in frappe.get_all("Library Lesson Requirement", {"active": 1}, pluck="name"):
		req = frappe.get_doc("Library Lesson Requirement", name)
		terms = _terms(req)
		if terms and section.academic_term not in terms:
			continue
		if section.course not in _courses_of(_programs(req)):
			continue
		if _ensure_required(req, course_schedule):
			_notify_required(req, course_schedule)


def on_chapter_reference_insert(doc, method=None):
	"""Copies (template import, course packs) set `in_course_copy` and place once at the end,
	so a requirement for the last chapter isn't put in the first one copied."""
	if frappe.flags.in_course_copy or doc.parenttype != "Course Schedule" or not doc.parent:
		return
	place_for_section(doc.parent)


def _completed(lesson):
	return frappe.db.exists("Course Schedule Progress", {"lesson": lesson, "status": "Complete"})


def release(req):
	"""Take a requirement's lessons out of open sections. A lesson a student completed stays,
	no longer required."""
	for row in frappe.get_all(
		"Course Lesson", {"required_by": req.name}, ["name", "course_sc", "chapter", "library_lesson"]
	):
		state = frappe.db.get_value("Course Schedule", row.course_sc, "workflow_state")
		if state in CLOSED_STATES or not row.library_lesson or _completed(row.name):
			frappe.db.set_value("Course Lesson", row.name, "required_by", None, update_modified=False)
			continue
		chapter = frappe.get_doc("Course Schedule Chapter", row.chapter)
		chapter.set("lessons", [{"lesson": r.lesson} for r in chapter.lessons if r.lesson != row.name])
		chapter.flags.ignore_permissions = True
		chapter.save()
		doc = frappe.get_doc("Course Lesson", row.name)
		doc.flags.from_requirement = True
		doc.flags.ignore_permissions = True
		doc.delete()


def on_requirement_update(doc, method=None):
	if cint(doc.active):
		place_requirement(doc)
	elif doc.has_value_changed("active"):
		release(doc)


def on_requirement_trash(doc, method=None):
	release(doc)


# ------------------------------------------------------------------------ change notices


def _section_people(course_schedule):
	instructors = frappe.get_all(
		"Course Schedule Instructors",
		filters={"parent": course_schedule, "parenttype": "Course Schedule"},
		pluck="instructor",
	)
	people = frappe.get_all("Instructor", {"name": ("in", instructors or [""])}, pluck="person")
	return sorted({p for p in people if p})


def _changed_labels(name, since):
	meta = frappe.get_meta("Library Lesson")
	labels = set()
	for v in frappe.get_all(
		"Version",
		filters={"ref_doctype": "Library Lesson", "docname": name, "creation": (">=", since)},
		pluck="data",
	):
		try:
			data = json.loads(v or "{}")
		except ValueError:
			continue
		for row in data.get("changed") or []:
			labels.add(_(meta.get_label(row[0])))
		for key in ("added", "removed", "row_changed"):
			for row in data.get(key) or []:
				labels.add(_(meta.get_label(row[0])))
	return sorted(labels)


def notify_changes():
	"""Daily: the instructors of open sections that place a library lesson changed since
	yesterday hear about it once."""
	from seminary.seminary import comms

	since = add_days(now_datetime(), -1)
	today = nowdate()
	for lib in frappe.get_all(
		"Library Lesson", {"modified": (">=", since)}, ["name", "title", "creation", "modified"]
	):
		labels = _changed_labels(lib.name, since)
		if not labels:
			continue
		sections = frappe.get_all(
			"Course Lesson", {"library_lesson": lib.name}, pluck="course_sc", distinct=True
		)
		for course_schedule in sections:
			section = frappe.db.get_value(
				"Course Schedule", course_schedule, ["title", "workflow_state"], as_dict=True
			)
			if not section or section.workflow_state in CLOSED_STATES:
				continue
			for person in _section_people(course_schedule):
				try:
					comms.send_message(
						channel="In-App",
						subject=_("{0} was changed in the library").format(lib.title),
						message=_("{0}, placed in {1}, was changed in the library: {2}.").format(
							lib.title, section.title or course_schedule, ", ".join(labels)
						),
						person=person,
						category="Academic",
						reference_doctype="Library Lesson",
						reference_name=lib.name,
						dedupe_key=f"library-change-{lib.name}-{course_schedule}-{person}-{today}",
					)
				except Exception:
					frappe.log_error(frappe.get_traceback(), "Library change notice failed")


# ------------------------------------------------------------------------ shared questions


SHARED_QUERIES = {
	# The course's own quizzes and those shared with it.
	"Quiz": """select t.name, t.title from `tabQuiz` t
		where (t.name like %(txt)s or t.title like %(txt)s)
		and (%(course)s = '' or t.course = %(course)s or exists (select 1 from `tabShared With Course` s
			where s.parent = t.name and s.parenttype = 'Quiz' and s.course = %(course)s))
		order by t.modified desc limit %(start)s, %(len)s""",
	# Most questions name no course; they stay available everywhere, as before.
	"Question": """select t.name, t.question from `tabQuestion` t
		where (t.name like %(txt)s or t.question like %(txt)s)
		and (%(course)s = '' or t.course = %(course)s or ifnull(t.course, '') = ''
			or exists (select 1 from `tabShared With Course` s
			where s.parent = t.name and s.parenttype = 'Question' and s.course = %(course)s))
		order by t.modified desc limit %(start)s, %(len)s""",
}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def shared_query(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict | None = None
):
	"""Link search for Quiz and Question: the course's own items and those shared with it."""
	_require_instructor()
	if doctype not in SHARED_QUERIES or not frappe.has_permission(doctype, "read"):
		return []
	course = (filters or {}).get("course") if isinstance(filters, dict) else None
	return frappe.db.sql(
		SHARED_QUERIES[doctype],
		{
			"txt": f"%{txt or ''}%",
			"course": course or "",
			"start": cint(start),
			"len": cint(page_len) or 20,
		},
	)


# ------------------------------------------------------------------------ portal


def _require_instructor():
	if not (guards.current_instructor() or guards.is_school_role()):
		frappe.throw(_("Only teaching staff can use the library."), frappe.PermissionError)


def _placements(library_lesson):
	rows = frappe.db.sql(
		"""select l.name as lesson, l.course_sc, l.required_by, cs.title as section,
		cs.academic_term, cs.workflow_state, ch.chapter_title
		from `tabCourse Lesson` l
		join `tabCourse Schedule` cs on cs.name = l.course_sc
		left join `tabCourse Schedule Chapter` ch on ch.name = l.chapter
		where l.library_lesson = %s order by cs.modified desc""",
		library_lesson,
		as_dict=True,
	)
	return rows


@frappe.whitelist()
def search(txt: str | None = None, course_schedule: str | None = None):
	"""The library page: lessons by title or tag. With a section, only lessons it may place."""
	_require_instructor()
	filters = {}
	or_filters = None
	if txt:
		or_filters = {"title": ("like", f"%{txt}%"), "tags": ("like", f"%{txt}%")}
	rows = frappe.get_all(
		"Library Lesson",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "title", "tags", "preview", "modified"],
		order_by="title asc",
		limit_page_length=200,
	)
	course = frappe.db.get_value("Course Schedule", course_schedule, "course") if course_schedule else None
	out = []
	for r in rows:
		if course and not available_for(r.name, course):
			continue
		r.placements = frappe.db.count("Course Lesson", {"library_lesson": r.name})
		r.required = frappe.db.count("Library Lesson Requirement", {"library_lesson": r.name, "active": 1})
		r.can_edit = _can_edit(r.name)
		out.append(r)
	return out


@frappe.whitelist()
def get(name: str):
	_require_instructor()
	doc = frappe.get_doc("Library Lesson", name)
	doc.check_permission("read")
	data = doc.as_dict()
	data.can_edit = _can_edit(name)
	data.placements = _placements(name)
	data.captions = library_captions(name)
	return data


@frappe.whitelist(methods=["POST"])
def save(
	title: str,
	name: str | None = None,
	tags: str | None = None,
	preview: str | None = None,
	content: str | None = None,
	instructor_content: str | None = None,
):
	_require_instructor()
	doc = frappe.get_doc("Library Lesson", name) if name else frappe.new_doc("Library Lesson")
	doc.update(
		{
			"title": title,
			"tags": tags,
			"preview": preview,
			"content": content,
			"instructor_content": instructor_content,
		}
	)
	doc.save()
	return {"name": doc.name}


@frappe.whitelist()
def my_chapters(library_lesson: str | None = None):
	"""Open sections the user may add content to, with their chapters, for *Add to chapter*."""
	_require_instructor()
	instructor = guards.current_instructor()
	if guards.is_school_role():
		sections = frappe.get_all(
			"Course Schedule",
			{"workflow_state": ("not in", CLOSED_STATES)},
			["name", "title", "course", "academic_term"],
			order_by="c_datestart desc",
			limit_page_length=100,
		)
	else:
		names = frappe.get_all(
			"Course Schedule Instructors",
			{"instructor": instructor, "parenttype": "Course Schedule"},
			pluck="parent",
		)
		sections = frappe.get_all(
			"Course Schedule",
			{"name": ("in", names or [""]), "workflow_state": ("not in", CLOSED_STATES)},
			["name", "title", "course", "academic_term"],
			order_by="c_datestart desc",
		)
	out = []
	for s in sections:
		if library_lesson and not available_for(library_lesson, s.course):
			continue
		if not guards.may_act(s.name, guards.CONTENT):
			continue
		s.chapters = frappe.db.sql(
			"""select ch.name, ch.chapter_title from `tabCourse Schedule Chapter Reference` r
			join `tabCourse Schedule Chapter` ch on ch.name = r.chapter
			where r.parent = %s and r.parenttype = 'Course Schedule' order by r.idx""",
			s.name,
			as_dict=True,
		)
		if s.chapters:
			out.append(s)
	return out
