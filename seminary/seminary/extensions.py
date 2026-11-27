# Copyright (c) 2026, Murilo R. Melo and contributors
# For license information, please see license.txt
"""Places another installed app can add to the course pages (privatedocs p028).

Each slot reads a hook list. With no app registering anything, every endpoint answers empty
and the pages render as they always have.

* ``seminary_course_tabs``: ``fn(course_schedule, access) -> [{"key", "label", "order"}]``.
  The course page shows a tab per row whose key the portal knows how to render.
* ``seminary_lesson_panels``: ``fn(lesson) -> [{"title", "html"}]``, shown above the body.
* ``seminary_question_panels``: ``fn(question, quiz) -> [{"title", "html"}]``, shown under a
  Reading Report question.
* ``seminary_enrollment_notice``: ``fn(course_schedule) -> {"title", "html"} | None``. The first
  answer is shown before the student enrolls.
* ``course_pack_exported`` / ``course_pack_imported``: see `seminary.seminary.course_pack`.
"""

import frappe
from frappe import _
from frappe.utils import cint

from seminary.seminary import guards


def _call_all(hook, *args):
	out = []
	for path in frappe.get_hooks(hook):
		try:
			result = frappe.get_attr(path)(*args)
		except frappe.PermissionError:
			continue
		if result:
			out.extend(result if isinstance(result, list) else [result])
	return out


def _panels(rows):
	return [
		{"title": r.get("title") or "", "html": r.get("html") or ""}
		for r in rows
		if isinstance(r, dict) and (r.get("html") or r.get("title"))
	]


def _access(course_schedule):
	if guards.is_course_staff(course_schedule):
		return "instructor"
	return "student"


@frappe.whitelist()
def course_tabs(course_schedule: str):
	guards.require_content_reader(course_schedule)
	access = _access(course_schedule)
	rows = [
		{"key": r["key"], "label": r.get("label") or r["key"], "order": cint(r.get("order"))}
		for r in _call_all("seminary_course_tabs", course_schedule, access)
		if isinstance(r, dict) and r.get("key")
	]
	return sorted(rows, key=lambda r: r["order"])


@frappe.whitelist()
def lesson_panels(lesson: str):
	course_schedule = frappe.db.get_value("Course Lesson", lesson, "course_sc")
	if not course_schedule:
		return []
	guards.require_content_reader(course_schedule)
	return _panels(_call_all("seminary_lesson_panels", lesson))


@frappe.whitelist()
def question_panels(question: str, quiz: str):
	if not frappe.db.exists("Quiz Question", {"parent": quiz, "question": question}):
		return []
	if not frappe.has_permission("Quiz", "read", doc=quiz):
		frappe.throw(_("You can't open this quiz."), frappe.PermissionError)
	return _panels(_call_all("seminary_question_panels", question, quiz))


@frappe.whitelist()
def enrollment_notice(course_schedule: str):
	if not frappe.db.exists("Course Schedule", course_schedule):
		return None
	if not guards.current_student() and not guards.is_school_role():
		frappe.throw(_("Only students enroll in courses."), frappe.PermissionError)
	for path in frappe.get_hooks("seminary_enrollment_notice"):
		notice = frappe.get_attr(path)(course_schedule)
		if isinstance(notice, dict) and notice.get("html"):
			return {"title": notice.get("title") or "", "html": notice["html"]}
	return None
