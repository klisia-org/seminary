# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

"""What a student may open in a section, and why not (decisions/107).

Three locks can close a chapter: its release date, its prerequisites, and,
in a competency-based section, the self-assessment lock (ADR 065/079). They
are combined here and nowhere else. The outline, the lesson endpoints,
progress, SCORM launch and the submission guard all ask this module, because
a lock the Vue layer enforces alone is not a lock.

Course staff, mentors and readers are never locked: only a student on the
section's roster walks through it.
"""

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	cint,
	flt,
	format_datetime,
	get_datetime,
	getdate,
	now_datetime,
)

ALWAYS_OPEN = "Always open"
ON_A_DATE = "On a date"
DAYS_AFTER_START = "Days after start"

COMPLETE_CHAPTER = "Complete chapter"
PASS_QUIZ = "Pass quiz"  # nosec B105 -- a prerequisite kind, not a password

# How far back the notice job looks for release dates that passed. A date
# older than this sends nothing, so turning the feature on in a running term
# does not announce every chapter that opened weeks ago.
NOTICE_WINDOW_DAYS = 7

CLOSED_STATES = ("Closed", "Cancelled")

_CHAPTER_FIELDS = (
	"name",
	"chapter_title",
	"course_competency",
	"release_type",
	"release_on",
	"release_offset_days",
)


# ---------------------------------------------------------------- reading the outline


def outline_chapters(course_schedule):
	"""Chapters in outline order with their release settings and
	prerequisites. Order comes from the section's chapter references, as the
	student walks it."""
	refs = frappe.get_all(
		"Course Schedule Chapter Reference",
		filters={"parent": course_schedule, "parenttype": "Course Schedule"},
		fields=["chapter", "idx"],
		order_by="idx asc",
	)
	names = [r.chapter for r in refs if r.chapter]
	if not names:
		return []
	rows = {
		r.name: r
		for r in frappe.get_all(
			"Course Schedule Chapter",
			filters={"name": ("in", names)},
			fields=list(_CHAPTER_FIELDS),
		)
	}
	prereqs = {}
	for p in frappe.get_all(
		"Chapter Prerequisite",
		filters={"parent": ("in", names), "parenttype": "Course Schedule Chapter"},
		fields=["parent", "kind", "chapter", "quiz", "min_percentage", "idx"],
		order_by="idx asc",
	):
		prereqs.setdefault(p.parent, []).append(p)
	out = []
	for ref in refs:
		row = rows.get(ref.chapter)
		if not row:
			continue
		row["idx"] = ref.idx
		row["prerequisites"] = prereqs.get(row.name, [])
		out.append(row)
	return out


def _section(course_schedule):
	return frappe.db.get_value(
		"Course Schedule",
		course_schedule,
		["name", "c_datestart", "open_ended"],
		as_dict=True,
	)


def _anchor(section, roster_doc=None):
	"""The moment 'days after start' counts from: the section's start date,
	or in an open-ended section the student's own enrolment."""
	if cint(section.open_ended):
		if not roster_doc:
			return None
		return get_datetime(getdate(roster_doc.creation))
	return get_datetime(section.c_datestart) if section.c_datestart else None


def opens_at(chapter, section, roster_doc=None):
	"""When `chapter` opens for this student, or None if a date never holds it."""
	kind = chapter.get("release_type") or ALWAYS_OPEN
	if kind == ON_A_DATE and chapter.get("release_on"):
		return get_datetime(chapter.release_on)
	if kind == DAYS_AFTER_START:
		anchor = _anchor(section, roster_doc)
		if anchor is None:
			return None
		return add_days(anchor, cint(chapter.get("release_offset_days")))
	return None


def describe_release(chapter, section):
	"""A staff-facing line for the badge: when students get this chapter."""
	kind = chapter.get("release_type") or ALWAYS_OPEN
	if kind == ON_A_DATE and chapter.get("release_on"):
		return _("Students: opens {0}").format(format_datetime(chapter.release_on, "EEE d MMM, HH:mm"))
	if kind == DAYS_AFTER_START:
		days = cint(chapter.get("release_offset_days"))
		if cint(section.open_ended):
			return _("Students: opens {0} days after they enrol").format(days)
		at = opens_at(chapter, section)
		if at:
			return _("Students: opens {0}").format(format_datetime(at, "EEE d MMM, HH:mm"))
	return None


# ---------------------------------------------------------------- prerequisites


def chapter_complete(member, chapter):
	"""Every lesson in `chapter` is Complete for this user. An empty chapter
	asks nothing."""
	lessons = frappe.get_all(
		"Course Schedule Lesson Reference",
		filters={"parent": chapter, "parenttype": "Course Schedule Chapter"},
		pluck="lesson",
	)
	lessons = [lesson for lesson in lessons if lesson]
	if not lessons:
		return True
	done = frappe.db.count(
		"Course Schedule Progress",
		{"member": member, "lesson": ("in", lessons), "status": "Complete"},
	)
	return done >= len(set(lessons))


def quiz_threshold(row):
	if row.get("min_percentage"):
		return flt(row.min_percentage)
	return flt(frappe.db.get_value("Quiz", row.quiz, "passing_percentage"))


def quiz_passed(member, course_schedule, row):
	scores = frappe.get_all(
		"Quiz Submission",
		filters={"member": member, "course": course_schedule, "quiz": row.quiz},
		pluck="percentage",
	)
	if not scores:
		return False
	return max(flt(s) for s in scores) >= quiz_threshold(row)


def prerequisite_reason(row, titles):
	if row.kind == COMPLETE_CHAPTER:
		return _("Finish {0} first.").format(titles.get(row.chapter) or row.chapter)
	quiz_title = frappe.db.get_value("Quiz", row.quiz, "title") or row.quiz
	threshold = quiz_threshold(row)
	if threshold:
		return _("Score at least {0}% on {1} first.").format(f"{threshold:g}", quiz_title)
	return _("Submit {0} first.").format(quiz_title)


def unmet_prerequisites(member, course_schedule, chapter, titles):
	reasons = []
	for row in chapter.get("prerequisites") or []:
		if row.kind == COMPLETE_CHAPTER and row.chapter:
			met = chapter_complete(member, row.chapter)
		elif row.kind == PASS_QUIZ and row.quiz:
			met = quiz_passed(member, course_schedule, row)
		else:
			met = True
		if not met:
			reasons.append(prerequisite_reason(row, titles))
	return reasons


# ---------------------------------------------------------------- the combined rule


def _overrides(course_schedule, student):
	return {
		o.chapter: o
		for o in frappe.get_all(
			"Student Chapter Release Override",
			filters={"course_schedule": course_schedule, "student": student},
			fields=["chapter", "open_from", "waive_prerequisites"],
		)
	}


def visible_outline(roster, at=None):
	"""Which chapters and activities are open to this student, and why not.

	Returns ``{"mode", "gated", "chapters": {name: state}}``; each state has
	``locked``, ``activities_locked``, ``reason`` (one line), ``reasons`` (each
	lock that applies), ``opens_at`` and ``unlock_competency``. The CBE keys
	keep the shape `cbe_api.get_outline_competencies` has always read.
	"""
	from seminary.seminary import cbe

	roster_doc = (
		roster
		if isinstance(roster, frappe.model.document.Document)
		else frappe.get_doc("Scheduled Course Roster", roster)
	)
	at = get_datetime(at) if at else now_datetime()
	course_schedule = roster_doc.course_sc
	section = _section(course_schedule)
	chapters = outline_chapters(course_schedule)
	titles = {c.name: c.chapter_title for c in chapters}
	overrides = _overrides(course_schedule, roster_doc.student)
	member = roster_doc.stuemail_rc or frappe.db.get_value("Student", roster_doc.student, "user")
	competency = cbe.competency_locks(roster_doc, chapters)

	result = {"mode": competency["mode"], "gated": competency["gated"], "chapters": {}}
	for c in chapters:
		override = overrides.get(c.name)
		waived = bool(override and cint(override.waive_prerequisites))
		reasons = []
		locked = activities_locked = False
		opening = get_datetime(override.open_from) if override and override.open_from else None
		opening = opening or opens_at(c, section, roster_doc)
		if opening and at < opening:
			locked = True
			reasons.append(_("Opens {0}").format(format_datetime(opening, "EEE d MMM, HH:mm")))
		if not waived:
			unmet = unmet_prerequisites(member, course_schedule, c, titles)
			if unmet:
				locked = True
				reasons.extend(unmet)
		cbe_state = competency["chapters"].get(c.name) or {}
		unlock_competency = None
		if not waived and (cbe_state.get("locked") or cbe_state.get("activities_locked")):
			locked = locked or bool(cbe_state.get("locked"))
			activities_locked = True
			unlock_competency = cbe_state.get("unlock_competency")
			if cbe_state.get("reason"):
				reasons.append(cbe_state["reason"])
		if locked:
			activities_locked = True
			result["gated"] = True
		result["chapters"][c.name] = {
			"chapter_title": c.chapter_title,
			"competency": c.course_competency,
			"locked": locked,
			"activities_locked": activities_locked,
			"reason": " ".join(reasons) or None,
			"reasons": reasons,
			"opens_at": opening if (opening and at < opening) else None,
			"unlock_competency": unlock_competency,
		}
	return result


def student_roster(course_schedule, user=None):
	"""The current user's active roster row on this section, unless they are
	staff or another non-student reader, who are never locked."""
	from seminary.seminary.guards import instructor_tier, is_course_staff

	user = user or frappe.session.user
	if user in ("Guest", "Administrator"):
		return None
	if is_course_staff(course_schedule, include_registrar=True, user=user):
		return None
	if instructor_tier(user) == "record":
		return None
	return frappe.db.get_value(
		"Scheduled Course Roster",
		{"course_sc": course_schedule, "stuemail_rc": user, "active": 1},
		"name",
	)


def outline_for_user(course_schedule, user=None):
	"""visible_outline for a student, or None for anyone who sees everything."""
	roster = student_roster(course_schedule, user)
	return visible_outline(roster) if roster else None


def chapter_state(course_schedule, chapter, user=None):
	"""This user's lock state on one chapter, or None when nothing locks it."""
	outline = outline_for_user(course_schedule, user)
	if not outline:
		return None
	state = outline["chapters"].get(chapter)
	return state if state and (state["locked"] or state["activities_locked"]) else None


def chapter_locked(course_schedule, chapter, user=None):
	state = chapter_state(course_schedule, chapter, user)
	return state if state and state["locked"] else None


def require_chapter_open(course_schedule, chapter, user=None):
	state = chapter_locked(course_schedule, chapter, user)
	if state:
		frappe.throw(
			_("This chapter is not open yet. {0}").format(state.get("reason") or ""),
			frappe.PermissionError,
		)


# ---------------------------------------------------------------- submission guard

_LESSON_CRITERIA_FIELDS = (
	"assessment_criteria_quiz",
	"assessment_criteria_assignment",
	"assessment_criteria_exam",
	"assessment_criteria_discussion",
)


def _chapters_for_criteria(course_schedule, criteria):
	"""Chapters whose lessons hold this assessment, plus the chapter that
	delivers its competency."""
	from seminary.seminary import cbe

	chapters = set()
	for field in _LESSON_CRITERIA_FIELDS:
		chapters.update(
			c
			for c in frappe.get_all(
				"Course Lesson",
				filters={"course_sc": course_schedule, field: criteria},
				pluck="chapter",
			)
			if c
		)
	competency = frappe.db.get_value("Scheduled Course Assess Criteria", criteria, "course_competency")
	if competency:
		chapter = cbe._chapter_for_competency(course_schedule, competency)
		if chapter:
			chapters.add(chapter)
	return chapters


def assert_activity_unlocked(doc, method=None):
	"""Refuse a submission for an activity the student has not unlocked.

	Hooked onto every submission doctype. Without it the locks would live only
	in the outline, and a direct call would walk straight past them.
	"""
	course_schedule = getattr(doc, "coursesc", None) or getattr(doc, "course", None)
	criteria = getattr(doc, "course_assess", None)
	student = getattr(doc, "student", None)
	if not (course_schedule and criteria and student):
		return
	chapters = _chapters_for_criteria(course_schedule, criteria)
	if not chapters:
		return
	roster = frappe.db.get_value(
		"Scheduled Course Roster",
		{"course_sc": course_schedule, "student": student},
		"name",
	)
	if not roster:
		return
	outline = visible_outline(roster)
	for chapter in chapters:
		state = outline["chapters"].get(chapter) or {}
		if state.get("activities_locked"):
			frappe.throw(
				_("This activity is not open yet. {0}").format(state.get("reason") or ""),
				frappe.PermissionError,
			)


# ---------------------------------------------------------------- chapter validation


def validate_chapter(doc):
	"""Release settings and prerequisites on a Course Schedule Chapter."""
	kind = doc.get("release_type") or ALWAYS_OPEN
	if kind == ON_A_DATE and not doc.get("release_on"):
		frappe.throw(_("Choose the date this chapter opens, or set Opens to Always open."))
	if kind == DAYS_AFTER_START and cint(doc.get("release_offset_days")) < 0:
		frappe.throw(_("Days after start cannot be negative."))
	if kind != ON_A_DATE:
		doc.release_on = None
	if kind != DAYS_AFTER_START:
		doc.release_offset_days = 0

	seen = set()
	for row in doc.get("prerequisites") or []:
		if row.kind == COMPLETE_CHAPTER:
			row.quiz = None
			row.min_percentage = None
			if not row.chapter:
				frappe.throw(_("Prerequisite row {0}: choose a chapter.").format(row.idx))
			if row.chapter == doc.name:
				frappe.throw(_("A chapter cannot be its own prerequisite."))
			if frappe.db.get_value("Course Schedule Chapter", row.chapter, "coursesc") != doc.coursesc:
				frappe.throw(
					_("Prerequisite row {0}: {1} is not a chapter of this section.").format(
						row.idx, row.chapter
					)
				)
			key = ("c", row.chapter)
		elif row.kind == PASS_QUIZ:
			row.chapter = None
			if not row.quiz:
				frappe.throw(_("Prerequisite row {0}: choose a quiz.").format(row.idx))
			if row.quiz not in section_quizzes(doc.coursesc):
				frappe.throw(
					_("Prerequisite row {0}: {1} is not a quiz of this section.").format(
						row.idx, frappe.db.get_value("Quiz", row.quiz, "title") or row.quiz
					)
				)
			if row.min_percentage is not None and not (0 <= flt(row.min_percentage) <= 100):
				frappe.throw(_("Prerequisite row {0}: the minimum score is a percentage.").format(row.idx))
			key = ("q", row.quiz)
		else:
			frappe.throw(_("Prerequisite row {0}: choose what it requires.").format(row.idx))
		if key in seen:
			frappe.throw(_("Prerequisite row {0} repeats an earlier row.").format(row.idx))
		seen.add(key)

	_refuse_loop(doc)


def section_quizzes(course_schedule):
	"""Quizzes this section uses, through an assessment row or a lesson."""
	quizzes = set(
		frappe.get_all(
			"Scheduled Course Assess Criteria",
			filters={"parent": course_schedule, "parenttype": "Course Schedule", "quiz": ("is", "set")},
			pluck="quiz",
		)
	)
	quizzes.update(
		q
		for q in frappe.get_all(
			"Course Lesson",
			filters={"course_sc": course_schedule, "quiz_id": ("is", "set")},
			pluck="quiz_id",
		)
		if q
	)
	return quizzes


def _refuse_loop(doc):
	"""A chapter may not wait, however indirectly, on itself."""
	if not doc.name:
		return
	graph = {}
	for p in frappe.get_all(
		"Chapter Prerequisite",
		filters={"parenttype": "Course Schedule Chapter", "kind": COMPLETE_CHAPTER},
		fields=["parent", "chapter"],
	):
		graph.setdefault(p.parent, set()).add(p.chapter)
	graph[doc.name] = {r.chapter for r in doc.get("prerequisites") or [] if r.kind == COMPLETE_CHAPTER}

	stack = list(graph[doc.name])
	seen = set()
	while stack:
		node = stack.pop()
		if node == doc.name:
			frappe.throw(
				_(
					"These prerequisites make a loop: {0} would wait on a chapter that waits on it. "
					"Remove one of them."
				).format(doc.chapter_title)
			)
		if node in seen:
			continue
		seen.add(node)
		stack.extend(graph.get(node, ()))


# ---------------------------------------------------------------- copying


def copy_release(src, target, day_shift):
	"""Copy release settings from one chapter doc/dict onto a new chapter.
	A fixed date moves with the section; days after start travel as they are."""
	target.release_type = src.get("release_type") or ALWAYS_OPEN
	target.release_offset_days = cint(src.get("release_offset_days"))
	if src.get("release_on"):
		target.release_on = add_days(get_datetime(src.get("release_on")), day_shift or 0)


def start_shift(source_start, target_start):
	"""Days between two sections' start dates, or 0 if either is missing."""
	if not (source_start and target_start):
		return 0
	return (getdate(target_start) - getdate(source_start)).days


def insert_prerequisites(new_chapter_name, rows, chapter_map, quiz_ok):
	"""Write prerequisite rows on a copied chapter. `chapter_map` turns a
	source chapter into its copy; `quiz_ok(quiz)` returns the quiz to use on
	the target, or None. Returns a message for every row that was dropped."""
	dropped = []
	title = frappe.db.get_value("Course Schedule Chapter", new_chapter_name, "chapter_title")
	idx = 0
	for row in rows:
		kind = row.get("kind")
		values = {"kind": kind}
		if kind == COMPLETE_CHAPTER:
			target = chapter_map.get(row.get("chapter"))
			if not target:
				dropped.append(
					_("Chapter {0}: a prerequisite on a chapter that was not copied was dropped.").format(
						title
					)
				)
				continue
			values["chapter"] = target
		elif kind == PASS_QUIZ:
			target = quiz_ok(row.get("quiz"))
			if not target:
				dropped.append(
					_("Chapter {0}: a prerequisite on a quiz this section does not have was dropped.").format(
						title
					)
				)
				continue
			values["quiz"] = target
			values["min_percentage"] = row.get("min_percentage")
		else:
			continue
		idx += 1
		child = frappe.get_doc(
			{
				"doctype": "Chapter Prerequisite",
				"parent": new_chapter_name,
				"parenttype": "Course Schedule Chapter",
				"parentfield": "prerequisites",
				"idx": idx,
				**values,
			}
		)
		child.flags.ignore_permissions = True
		child.insert()
	return dropped


# ---------------------------------------------------------------- notices


def notify_opened_chapters(at=None):
	"""Hourly job: tell each student when a chapter's release date passes.

	Looks back NOTICE_WINDOW_DAYS. A student still held by a prerequisite or
	the CBE lock gets nothing until that clears; the dedupe key makes every
	later run a no-op for a notice already queued.
	"""
	from seminary.seminary import comms

	at = get_datetime(at) if at else now_datetime()
	since = add_days(at, -NOTICE_WINDOW_DAYS)
	sections = frappe.get_all(
		"Course Schedule",
		filters={
			"published": 1,
			"notify_on_release": 1,
			"workflow_state": ("not in", CLOSED_STATES),
		},
		pluck="name",
	)
	for course_schedule in sections:
		names = set(
			frappe.get_all(
				"Course Schedule Chapter",
				filters={"coursesc": course_schedule, "release_type": ("in", (ON_A_DATE, DAYS_AFTER_START))},
				pluck="name",
			)
		)
		names.update(
			frappe.get_all(
				"Student Chapter Release Override",
				filters={"course_schedule": course_schedule, "open_from": ("is", "set")},
				pluck="chapter",
			)
		)
		if not names:
			continue
		chapters = frappe.get_all(
			"Course Schedule Chapter",
			filters={"name": ("in", list(names))},
			fields=list(_CHAPTER_FIELDS),
		)
		section = _section(course_schedule)
		title = frappe.db.get_value("Course Schedule", course_schedule, "title") or course_schedule
		for roster in frappe.get_all(
			"Scheduled Course Roster",
			filters={"course_sc": course_schedule, "active": 1},
			fields=["name", "student", "creation"],
		):
			person = frappe.db.get_value("Student", roster.student, "person")
			if not person:
				continue
			overrides = _overrides(course_schedule, roster.student)
			due = []
			for chapter in chapters:
				override = overrides.get(chapter.name)
				opening = (
					get_datetime(override.open_from)
					if override and override.open_from
					else opens_at(chapter, section, roster)
				)
				if opening and since <= opening <= at:
					due.append(chapter)
			if not due:
				continue
			outline = visible_outline(roster.name, at=at)
			for chapter in due:
				state = outline["chapters"].get(chapter.name)
				if not state or state["locked"]:
					continue
				try:
					comms.send_message(
						channel="In-App",
						subject=_("{0} is now open").format(chapter.chapter_title),
						message=_("{0} in {1} is now open.").format(chapter.chapter_title, title),
						person=person,
						category="Academic",
						reference_doctype="Course Schedule",
						reference_name=course_schedule,
						dedupe_key=f"chapter-open-{roster.name}-{chapter.name}",
					)
				except Exception:
					frappe.log_error(frappe.get_traceback(), "Chapter release notice failed")


# ---------------------------------------------------------------- portal endpoints


def _require_staff(course_schedule, action=None):
	from seminary.seminary.deadlines import _require_staff as require

	require(course_schedule, action)


@frappe.whitelist()
def get_release_options(course: str):
	"""What the chapter editor offers: the section's chapters and quizzes."""
	from seminary.seminary.guards import CONTENT

	_require_staff(course, CONTENT)
	return {
		"chapters": [
			{"name": c.name, "chapter_title": c.chapter_title, "idx": c.idx} for c in outline_chapters(course)
		],
		"quizzes": [
			{"name": q.name, "title": q.title, "passing_percentage": q.passing_percentage}
			for q in frappe.get_all(
				"Quiz",
				filters={"name": ("in", list(section_quizzes(course)) or ["\x00"])},
				fields=["name", "title", "passing_percentage"],
				order_by="title asc",
			)
		],
	}


@frappe.whitelist()
def get_chapter_overrides(chapter: str):
	course = frappe.db.get_value("Course Schedule Chapter", chapter, "coursesc")
	_require_staff(course)
	return {
		"overrides": frappe.get_all(
			"Student Chapter Release Override",
			filters={"chapter": chapter},
			fields=[
				"name",
				"student",
				"student_name",
				"open_from",
				"waive_prerequisites",
				"reason",
				"source",
			],
			order_by="student_name asc",
		),
		"roster": frappe.get_all(
			"Scheduled Course Roster",
			filters={"course_sc": course, "active": 1},
			fields=["student", "stuname_roster as student_name"],
			order_by="stuname_roster asc",
		),
	}


@frappe.whitelist()
def save_chapter_override(data: str | dict):
	"""Create or edit one student's opening on one chapter. The doctype's
	validate checks the section, the roster and the caller."""
	from seminary.seminary.guards import GRADE

	data = frappe.parse_json(data) if isinstance(data, str) else (data or {})
	chapter = data.get("chapter")
	course = frappe.db.get_value("Course Schedule Chapter", chapter, "coursesc")
	_require_staff(course, GRADE)
	if data.get("name"):
		doc = frappe.get_doc("Student Chapter Release Override", data["name"])
		if doc.chapter != chapter:
			frappe.throw(_("This override belongs to another chapter."))
	else:
		doc = frappe.new_doc("Student Chapter Release Override")
		doc.chapter = chapter
		doc.course_schedule = course
		doc.student = data.get("student")
		from seminary.seminary.deadlines import _is_registrar_only

		doc.source = "Registrar" if _is_registrar_only(course) else "Instructor"
	for f in ("open_from", "waive_prerequisites", "reason"):
		if f in data:
			doc.set(f, data.get(f) or None)
	doc.save(ignore_permissions=True)
	return doc.as_dict()


@frappe.whitelist()
def delete_chapter_override(name: str):
	from seminary.seminary.guards import GRADE

	course = frappe.db.get_value("Student Chapter Release Override", name, "course_schedule")
	_require_staff(course, GRADE)
	if not course:
		frappe.throw(_("That override no longer exists."))
	frappe.delete_doc("Student Chapter Release Override", name, ignore_permissions=True)
	return {"deleted": name}
