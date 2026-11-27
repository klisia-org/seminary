# Copyright (c) 2026, Murilo R. Melo and contributors
# For license information, please see license.txt
"""Library Lesson Use: where each library lesson is placed, whether the school requires it,
and how many students completed it (decisions/122 §10). The message lists the sections an
active requirement covers that don't hold its lesson."""

import frappe
from frappe import _
from frappe.utils import escape_html

from seminary.seminary import library


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return columns(), data(filters), missing_message(filters)


def columns():
	def col(fieldname, label, fieldtype="Data", options=None, width=150):
		c = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, "width": width}
		if options:
			c["options"] = options
		return c

	return [
		col("library_lesson", _("Library Lesson"), "Link", "Library Lesson", 220),
		col("academic_term", _("Term"), "Link", "Academic Term", 120),
		col("programs", _("Programs"), width=180),
		col("course_schedule", _("Section"), "Link", "Course Schedule", 220),
		col("instructors", _("Instructors"), width=180),
		col("kind", _("Required or Chosen"), width=130),
		col("state", _("State"), width=130),
		col("placed_on", _("Placed On"), "Date", width=100),
		col("completed", _("Completed"), "Int", width=90),
		col("enrolled", _("Enrolled"), "Int", width=90),
		col("lesson", _("Lesson"), "Link", "Course Lesson", 180),
	]


def _programs_of(course, cache):
	if course not in cache:
		cache[course] = frappe.get_all(
			"Program Course", {"course": course, "parenttype": "Program"}, pluck="parent", distinct=True
		)
	return cache[course]


def data(filters):
	rows = frappe.db.sql(
		"""select l.name as lesson, coalesce(l.library_lesson, l.detached_from) as library_lesson,
			l.library_lesson as placed, l.required_by, l.frozen_at_close, l.creation,
			cs.name as course_schedule, cs.course, cs.academic_term
		from `tabCourse Lesson` l join `tabCourse Schedule` cs on cs.name = l.course_sc
		where (l.library_lesson is not null or l.detached_from is not null)
			and (%(lib)s = '' or coalesce(l.library_lesson, l.detached_from) = %(lib)s)
			and (%(term)s = '' or cs.academic_term = %(term)s)
			and (%(required)s = 0 or l.required_by is not null)
		order by cs.academic_term desc, cs.name""",
		{
			"lib": filters.library_lesson or "",
			"term": filters.academic_term or "",
			"required": 1 if filters.required_only else 0,
		},
		as_dict=True,
	)
	cache = {}
	out = []
	for r in rows:
		programs = _programs_of(r.course, cache)
		if filters.program and filters.program not in programs:
			continue
		instructors = frappe.get_all(
			"Course Schedule Instructors",
			{"parent": r.course_schedule, "parenttype": "Course Schedule"},
			pluck="instructor",
		)
		if r.placed:
			state = _("Placed")
		elif r.frozen_at_close:
			state = _("Frozen at close")
		else:
			state = _("Detached")
		out.append(
			{
				"library_lesson": r.library_lesson,
				"academic_term": r.academic_term,
				"programs": ", ".join(programs),
				"course_schedule": r.course_schedule,
				"instructors": ", ".join(
					frappe.db.get_value("Instructor", i, "instructor_name") or i for i in instructors
				),
				"kind": _("Required") if r.required_by else _("Chosen"),
				"state": state,
				"placed_on": r.creation,
				"completed": frappe.db.count(
					"Course Schedule Progress", {"lesson": r.lesson, "status": "Complete"}
				),
				"enrolled": frappe.db.count(
					"Scheduled Course Roster", {"course_sc": r.course_schedule, "active": 1}
				),
				"lesson": r.lesson,
			}
		)
	return out


def missing(filters=None):
	"""(requirement, section) pairs where an active requirement's lesson is absent."""
	filters = frappe._dict(filters or {})
	req_filters = {"active": 1}
	if filters.library_lesson:
		req_filters["library_lesson"] = filters.library_lesson
	out = []
	for name in frappe.get_all("Library Lesson Requirement", req_filters, pluck="name"):
		req = frappe.get_doc("Library Lesson Requirement", name)
		for cs in library.sections_for(req, include_closed=True):
			if (
				filters.academic_term
				and frappe.db.get_value("Course Schedule", cs, "academic_term") != filters.academic_term
			):
				continue
			if frappe.db.exists("Course Lesson", {"course_sc": cs, "required_by": req.name}):
				continue
			out.append((req, cs))
	return out


def missing_message(filters):
	pairs = missing(filters)
	if not pairs:
		return None
	items = "".join(
		"<li>{0}: {1}</li>".format(
			escape_html(req.lesson_title or req.library_lesson),
			escape_html(frappe.db.get_value("Course Schedule", cs, "title") or cs),
		)
		for req, cs in pairs
	)
	return "<p>{0}</p><ul>{1}</ul>".format(
		escape_html(
			_(
				"These sections should hold a required lesson but don't. Their chapters may have been "
				"deleted, or the requirement was added after they closed."
			)
		),
		items,
	)
